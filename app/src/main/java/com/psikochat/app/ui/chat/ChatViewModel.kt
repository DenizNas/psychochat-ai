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
    
    fun loadHistory() {
        viewModelScope.launch {
            _isLoading.value = true
            when(val res = repository.getHistory()) {
                is Resource.Success -> {
                    _messages.value = res.data ?: emptyList()
                    if(_messages.value.isEmpty()) {
                        _messages.value = listOf(HistoryItem("assistant", "Merhaba! Ben sana destek olmak için tasarlanmış empatik bir yapay zekayım. Bugün nasıl hissediyorsun?"))
                    }
                }
                is Resource.Error -> _error.value = res.message
                else -> {}
            }
            _isLoading.value = false
        }
    }

    fun sendMessage(text: String) {
        if (text.isBlank()) return
        
        viewModelScope.launch {
            val currentList = _messages.value.toMutableList()
            currentList.add(HistoryItem("user", text))
            _messages.value = currentList
            _crisisAlert.value = null
            
            _isLoading.value = true
            when(val res = repository.sendMessage(text)) {
                is Resource.Success -> {
                    val updated = _messages.value.toMutableList()
                    updated.add(HistoryItem("assistant", res.data?.response ?: ""))
                    _messages.value = updated
                    
                    if (res.data?.emergency_contact != null) {
                        _crisisAlert.value = res.data.emergency_contact
                    }
                }
                is Resource.Error -> _error.value = res.message
                else -> {}
            }
            _isLoading.value = false
        }
    }
}
