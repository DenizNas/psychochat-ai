package com.psikochat.app.ui.chat

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.psikochat.app.data.local.TokenManager
import com.psikochat.app.data.model.HistoryItem
import com.psikochat.app.data.model.Resource
import com.psikochat.app.data.realtime.ConnectionState
import com.psikochat.app.data.realtime.RealtimeWebSocketManager
import com.psikochat.app.data.realtime.WsEvent
import com.psikochat.app.data.repository.ChatRepository
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.*

/**
 * ChatViewModel — Real-Time Upgraded
 * ====================================
 * WebSocket üzerinden gerçek zamanlı sohbet.
 * WS bağlı değilse → REST fallback otomatik devreye girer.
 *
 * Privacy: token, raw mesaj içeriği, journal notu loglanmaz.
 */
import com.psikochat.app.data.sync.SyncManager

class ChatViewModel(
    private val repository: ChatRepository,
    private val wsManager: RealtimeWebSocketManager,
    private val tokenManager: TokenManager,
    private val syncManager: SyncManager
) : ViewModel() {

    // ─── UI State Flows ────────────────────────────────────────────────────
    private val _messages = MutableStateFlow<List<HistoryItem>>(emptyList())
    val messages: StateFlow<List<HistoryItem>> = _messages

    private val _isLoading = MutableStateFlow(false)
    val isLoading: StateFlow<Boolean> = _isLoading

    private val _error = MutableStateFlow<String?>(null)
    val error: StateFlow<String?> = _error

    private val _crisisAlert = MutableStateFlow<String?>(null)
    val crisisAlert: StateFlow<String?> = _crisisAlert

    private val _lastFailedMessage = MutableStateFlow<String?>(null)
    val lastFailedMessage: StateFlow<String?> = _lastFailedMessage

    /** Assistant'ın şu an yazdığını gösterir (WebSocket typing indicator). */
    private val _isAssistantTyping = MutableStateFlow(false)
    val isAssistantTyping: StateFlow<Boolean> = _isAssistantTyping

    /** WebSocket bağlantı durumu (UI banner için). */
    val connectionState: StateFlow<ConnectionState> = wsManager.connectionState

    // ─── Typing Debounce ──────────────────────────────────────────────────
    private var typingJob: Job? = null
    private val TYPING_DEBOUNCE_MS = 1500L

    // ─── Internal ─────────────────────────────────────────────────────────
    private var lastSendTime = 0L

    init {
        // WebSocket bağlantısını başlat
        wsManager.connect()
        // Gelen server event'lerini dinle
        observeWsEvents()
    }

    // ─── WebSocket Event Listener ─────────────────────────────────────────
    private fun observeWsEvents() {
        viewModelScope.launch {
            wsManager.incomingEvents.collect { event ->
                when (event) {
                    is WsEvent.ChatResponse -> handleChatResponse(event)
                    is WsEvent.TypingIndicator -> _isAssistantTyping.value = event.isTyping
                    is WsEvent.Intervention -> {
                        // Kriz durumu — acil müdahale popup'ı
                        _crisisAlert.value = event.body
                    }
                    is WsEvent.Error -> {
                        _isLoading.value = false
                        _isAssistantTyping.value = false
                        _error.value = event.message
                    }
                    else -> { /* Connected, Pong, PresenceUpdate — UI'da gösterilmez */ }
                }
            }
        }
    }

    private fun handleChatResponse(event: WsEvent.ChatResponse) {
        val updated = _messages.value.toMutableList()
        updated.add(HistoryItem(role = "assistant", text = event.response))
        _messages.value = updated
        _isLoading.value = false
        _isAssistantTyping.value = false

        if (!event.emergencyContact.isNullOrBlank()) {
            _crisisAlert.value = event.emergencyContact
        }
    }

    // ─── Chat History ──────────────────────────────────────────────────────
    fun loadHistory() {
        viewModelScope.launch {
            _isLoading.value = true
            val username = tokenManager.getUsername().first()
            
            // 1. Observe Room local database cache reactively (always responds instantly!)
            repository.getCachedHistory(username)
                .onEach { list ->
                    _messages.value = list
                }
                .launchIn(viewModelScope)
            
            // 2. Perform background network refresh to update local Room cache if online
            if (syncManager.isOnline.value) {
                when (val res = repository.refreshHistory(username)) {
                    is Resource.Error -> {
                        _error.value = res.message
                    }
                    else -> {}
                }
            }
            _isLoading.value = false
        }
    }

    // ─── Send Message ─────────────────────────────────────────────────────
    fun sendMessage(text: String) {
        val trimmed = text.trim()
        if (trimmed.isEmpty()) return
        if (trimmed.length > 1000) {
            _error.value = "Mesaj çok uzun (maksimum 1000 karakter)"
            return
        }
        if (_isLoading.value) return

        val currentTime = System.currentTimeMillis()
        if (currentTime - lastSendTime < 1000) return // 1 sn throttle
        lastSendTime = currentTime

        _error.value = null
        _lastFailedMessage.value = null

        // Typing stop
        stopTypingDebounce()

        val isWsConnected = wsManager.connectionState.value is ConnectionState.Connected
        if (isWsConnected) {
            _isLoading.value = true
            // Save locally first so history matches instantly
            viewModelScope.launch {
                val username = tokenManager.getUsername().first()
                repository.sendMessageResilient(username, trimmed, isOnline = true)
            }
            val sent = wsManager.sendMessage(trimmed)
            if (!sent) {
                // WebSocket failed: fall back to resilient queueing
                sendResilient(trimmed)
            }
        } else {
            sendResilient(trimmed)
        }
    }

    private fun sendResilient(text: String) {
        viewModelScope.launch {
            _isLoading.value = true
            val username = tokenManager.getUsername().first()
            val isOnline = syncManager.isOnline.value
            val res = repository.sendMessageResilient(username, text, isOnline = isOnline)
            if (res is Resource.Error) {
                _error.value = res.message
                _lastFailedMessage.value = text
            }
            _isLoading.value = false
        }
    }

    // ─── Typing Indicator ─────────────────────────────────────────────────
    fun onUserTyping() {
        val isConnected = wsManager.connectionState.value is ConnectionState.Connected
        if (!isConnected) return

        typingJob?.cancel()
        wsManager.sendTypingStart()

        typingJob = viewModelScope.launch {
            delay(TYPING_DEBOUNCE_MS)
            wsManager.sendTypingStop()
        }
    }

    private fun stopTypingDebounce() {
        typingJob?.cancel()
        typingJob = null
        val isConnected = wsManager.connectionState.value is ConnectionState.Connected
        if (isConnected) wsManager.sendTypingStop()
    }

    // ─── Utility ──────────────────────────────────────────────────────────
    fun retryLastMessage() {
        val msg = _lastFailedMessage.value
        if (!msg.isNullOrBlank()) sendMessage(msg)
    }

    fun clearError() {
        _error.value = null
    }

    override fun onCleared() {
        super.onCleared()
        wsManager.disconnect()
    }
}
