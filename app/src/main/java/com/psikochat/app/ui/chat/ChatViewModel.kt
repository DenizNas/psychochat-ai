package com.psikochat.app.ui.chat

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.psikochat.app.data.model.HistoryItem
import com.psikochat.app.data.model.Resource
import com.psikochat.app.data.repository.ChatRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch

class ChatViewModel(private val repository: ChatRepository) : ViewModel() {
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

    private var lastSendTime = 0L
    
    fun loadHistory() {
        viewModelScope.launch {
            _isLoading.value = true
            when(val res = repository.getHistory()) {
                is Resource.Success -> {
                    _messages.value = res.data ?: emptyList()
                }
                is Resource.Error -> _error.value = res.message
                else -> {}
            }
            _isLoading.value = false
        }
    }

    fun sendMessage(text: String) {
        val trimmed = text.trim()
        if (trimmed.isEmpty()) return
        if (trimmed.length > 1000) {
            _error.value = "Mesaj çok uzun (maksimum 1000 karakter)"
            return
        }
        if (_isLoading.value) return // Prevent duplicate requests while loading
        
        val currentTime = System.currentTimeMillis()
        if (currentTime - lastSendTime < 1000) return // 1 second throttle against double taps
        lastSendTime = currentTime
        
        _error.value = null
        _lastFailedMessage.value = null

        viewModelScope.launch {
            val currentList = _messages.value.toMutableList()
            currentList.add(HistoryItem(role = "user", text = trimmed))
            _messages.value = currentList
            _crisisAlert.value = null
            
            _isLoading.value = true
            when(val res = repository.sendMessage(trimmed)) {
                is Resource.Success -> {
                    val updated = _messages.value.toMutableList()
                    updated.add(HistoryItem(role = "assistant", text = res.data?.response ?: ""))
                    _messages.value = updated
                    
                    if (res.data?.emergencyContact != null) {
                        _crisisAlert.value = res.data.emergencyContact
                    }
                }
                is Resource.Error -> {
                    _error.value = res.message
                    _lastFailedMessage.value = trimmed
                    // Başarısız olan son kullanıcı mesajını listeden çıkar (tekrar gönderildiğinde çift gözükmesin)
                    _messages.value = currentList.dropLast(1)
                }
                else -> {}
            }
            _isLoading.value = false
        }
    }

    fun retryLastMessage() {
        val msg = _lastFailedMessage.value
        if (!msg.isNullOrBlank()) {
            sendMessage(msg)
        }
    }

    fun clearError() {
        _error.value = null
    }
}
