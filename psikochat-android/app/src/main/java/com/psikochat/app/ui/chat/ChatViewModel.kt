package com.psikochat.app.ui.chat

import android.util.Log
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
import com.psikochat.app.data.repository.PrivacyRepository
import java.text.SimpleDateFormat
import java.util.Locale
import java.util.Date
import java.util.UUID

class ChatViewModel(
    private val repository: ChatRepository,
    private val wsManager: RealtimeWebSocketManager,
    private val tokenManager: TokenManager,
    private val syncManager: SyncManager,
    private val privacyRepository: PrivacyRepository
) : ViewModel() {

    // ─── UI State Flows ────────────────────────────────────────────────────
    private val _messages = MutableStateFlow<List<HistoryItem>>(emptyList())
    val messages: StateFlow<List<HistoryItem>> = _messages

    private val _activeConversationId = MutableStateFlow<String>("")
    val activeConversationId: StateFlow<String> = _activeConversationId.asStateFlow()

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

    // ─── AI Consent State ─────────────────────────────────────────────────
    private val _aiConsentGranted = MutableStateFlow<Boolean?>(null)
    val aiConsentGranted: StateFlow<Boolean?> = _aiConsentGranted

    private val _isConsentOffline = MutableStateFlow(false)
    val isConsentOffline: StateFlow<Boolean> = _isConsentOffline

    // ─── Typing Debounce ──────────────────────────────────────────────────
    private var typingJob: Job? = null
    private val TYPING_DEBOUNCE_MS = 1500L

    // ─── Timeout Handling ──────────────────────────────────────────────────
    private var activeTimeoutJob: Job? = null

    // Tracks the localId of the message currently awaiting a WS response.
    // Set before wsManager.sendMessage(), cleared in handleChatResponse() or fallback.
    // Guards against race: WS response arriving before activeTimeoutJob assignment.
    @Volatile
    private var activeMessageLocalId: String? = null

    // ─── In-flight Guard: prevents same localId from being sent twice ──────
    // Stores localIds that have already been dispatched to sendResilient.
    // Cleared when the message is confirmed delivered or ultimately failed.
    private val _inFlightLocalIds = mutableSetOf<String>()

    // ─── Internal ─────────────────────────────────────────────────────────
    private var lastSendTime = 0L
    private var historyCollectionJob: Job? = null
    private var clearTimeMillis: Long = 0L

    init {
        // Gelen server event'lerini dinle
        observeWsEvents()
        // Gizlilik iznini kontrol et ve bağlan
        checkConsentAndConnect()
    }

    fun checkConsentAndConnect() {
        viewModelScope.launch {
            if (syncManager.isOnline.value) {
                _isConsentOffline.value = false
                when (val res = privacyRepository.getPrivacyConsent()) {
                    is Resource.Success -> {
                        val consent = res.data?.aiProcessingConsent ?: true
                        _aiConsentGranted.value = consent
                        if (consent) {
                            wsManager.connect()
                        } else {
                            wsManager.disconnect()
                        }
                    }
                    is Resource.Error -> {
                        _aiConsentGranted.value = true
                        _isConsentOffline.value = true
                        wsManager.connect()
                    }
                    else -> {}
                }
            } else {
                _aiConsentGranted.value = true
                _isConsentOffline.value = true
                wsManager.connect()
            }
        }
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
        // Discard stale WS responses: only process if we have an active WS message in flight.
        // Using activeMessageLocalId (set before sendMessage) avoids the race where
        // a fast WS response arrives before activeTimeoutJob coroutine assignment is visible.
        val pendingLocalId = activeMessageLocalId
        if (pendingLocalId == null) {
            Log.d("ChatViewModel", "WS_RESPONSE | discarded | no active message in flight")
            return
        }

        // Cancel the safety timeout — WS responded in time
        activeTimeoutJob?.cancel()
        activeTimeoutJob = null
        activeMessageLocalId = null
        // Remove from in-flight guard so the localId is not blocked for future retries
        _inFlightLocalIds.remove(pendingLocalId)

        Log.d("ChatViewModel", "WS_RESPONSE | accepted | localId=${pendingLocalId.take(8)}")

        viewModelScope.launch {
            val username = tokenManager.getUsername().first()
            val activeId = _activeConversationId.value
            repository.saveAssistantMessageLocally(username, event.response, conversationId = activeId)
            _isLoading.value = false
            _isAssistantTyping.value = false
        }

        if (!event.emergencyContact.isNullOrBlank()) {
            _crisisAlert.value = event.emergencyContact
        }
    }

    fun loadHistory(conversationId: String?) {
        viewModelScope.launch {
            _isLoading.value = true
            val username = tokenManager.getUsername().first()
            
            val activeId = if (conversationId.isNullOrBlank()) {
                UUID.randomUUID().toString()
            } else {
                conversationId
            }
            _activeConversationId.value = activeId
            
            // 1. Observe Room local database cache reactively filtered by activeConversationId
            historyCollectionJob?.cancel()
            historyCollectionJob = repository.getCachedHistory(username, activeId)
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
        if (_aiConsentGranted.value == false) return
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
        viewModelScope.launch {
            val username = tokenManager.getUsername().first()
            val activeId = _activeConversationId.value
            if (isWsConnected) {
                _isLoading.value = true

                // Save user message locally (Optimistically show as synced)
                val localId = repository.saveUserMessageLocally(username, trimmed, state = "synced", conversationId = activeId)

                // Register the active message BEFORE sendMessage() so handleChatResponse
                // never sees a null activeMessageLocalId even if WS replies instantly.
                activeMessageLocalId = localId

                Log.d("ChatViewModel", "SEND | WS path | localId=${localId.take(8)}")

                // Start an 8-second safety timeout for WebSocket response
                activeTimeoutJob?.cancel()
                activeTimeoutJob = launch {
                    delay(8000L) // 8-second safety threshold
                    activeTimeoutJob = null
                    activeMessageLocalId = null
                    _isLoading.value = false
                    _isAssistantTyping.value = false
                    Log.d("ChatViewModel", "TIMEOUT | fired | localId=${localId.take(8)} | falling back to REST")
                    // Guard: only fall back if this localId hasn't already been dispatched
                    if (_inFlightLocalIds.add(localId)) {
                        sendResilient(trimmed, isFallback = true, localId = localId)
                    }
                }

                val sent = wsManager.sendMessage(trimmed, conversationId = activeId)
                if (!sent) {
                    // WebSocket failed immediately: cancel safety timeout and fall back to REST
                    activeTimeoutJob?.cancel()
                    activeTimeoutJob = null
                    activeMessageLocalId = null
                    Log.d("ChatViewModel", "SEND | WS failed immediately | localId=${localId.take(8)} | falling back to REST")
                    // Guard: only dispatch once even if both timeout and immediate failure fire
                    if (_inFlightLocalIds.add(localId)) {
                        sendResilient(trimmed, isFallback = true, localId = localId)
                    }
                }
            } else {
                Log.d("ChatViewModel", "SEND | REST path (WS not connected)")
                sendResilient(trimmed, isFallback = false, localId = null)
            }
        }
    }

    private fun sendResilient(text: String, isFallback: Boolean = false, localId: String? = null) {
        viewModelScope.launch {
            try {
                _isLoading.value = true
                val username = tokenManager.getUsername().first()
                val isOnline = syncManager.isOnline.value
                val activeId = _activeConversationId.value
                Log.d("ChatViewModel", "RESILIENT | isFallback=$isFallback | isOnline=$isOnline | localId=${localId?.take(8)}")
                val res = repository.sendMessageResilient(
                    userId = username,
                    text = text,
                    isOnline = isOnline,
                    isFallback = isFallback,
                    fallbackLocalId = localId,
                    conversationId = activeId
                )
                when (res) {
                    is Resource.Success -> Log.d("ChatViewModel", "RESILIENT | success | localId=${localId?.take(8)}")
                    is Resource.Error -> {
                        Log.w("ChatViewModel", "RESILIENT | error | ${res.message} | localId=${localId?.take(8)}")
                        _error.value = res.message
                        _lastFailedMessage.value = text
                    }
                    else -> {}
                }
            } catch (e: Exception) {
                Log.e("ChatViewModel", "RESILIENT | exception | ${e.message}")
                _error.value = "Sistemsel bir hata oluştu: ${e.message}"
            } finally {
                _isLoading.value = false
                _isAssistantTyping.value = false
                // Remove from in-flight guard after processing completes
                if (localId != null) _inFlightLocalIds.remove(localId)
            }
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

    fun clearCrisisAlert() {
        _crisisAlert.value = null
    }

    private fun parseTimestampToMillis(timestamp: String?): Long {
        if (timestamp.isNullOrBlank()) return 0L
        val formats = listOf(
            "yyyy-MM-dd'T'HH:mm:ss",
            "yyyy-MM-dd HH:mm:ss"
        )
        for (format in formats) {
            try {
                val sdf = SimpleDateFormat(format, Locale.getDefault())
                val date = sdf.parse(timestamp)
                if (date != null) return date.time
            } catch (e: Exception) {
                // Try next format
            }
        }
        return 0L
    }

    fun startNewChat() {
        viewModelScope.launch {
            val username = tokenManager.getUsername().first()
            val newId = UUID.randomUUID().toString()
            _activeConversationId.value = newId
            
            historyCollectionJob?.cancel()
            historyCollectionJob = repository.getCachedHistory(username, newId)
                .onEach { list ->
                    _messages.value = list
                }
                .launchIn(viewModelScope)
        }
    }

    override fun onCleared() {
        super.onCleared()
        wsManager.disconnect()
    }
}
