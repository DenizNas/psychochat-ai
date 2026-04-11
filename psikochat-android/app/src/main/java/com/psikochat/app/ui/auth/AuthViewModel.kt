package com.psikochat.app.ui.auth
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.psikochat.app.data.local.TokenManager
import com.psikochat.app.data.model.Resource
import com.psikochat.app.data.repository.AuthRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch

class AuthViewModel(private val repository: AuthRepository, private val tokenManager: TokenManager) : ViewModel() {
    private val _authState = MutableStateFlow<Resource<Boolean>>(Resource.Success(false))
    val authState: StateFlow<Resource<Boolean>> = _authState
    
    fun login(user: String, pass: String) {
        viewModelScope.launch {
            _authState.value = Resource.Loading()
            when (val res = repository.login(user, pass)) {
                is Resource.Success -> {
                    res.data?.let { tokenManager.saveToken(it) }
                    _authState.value = Resource.Success(true)
                }
                is Resource.Error -> _authState.value = Resource.Error(res.message ?: "Hata")
                else -> {}
            }
        }
    }
    
    fun register(user: String, pass: String) {
        viewModelScope.launch {
            _authState.value = Resource.Loading()
            when (val res = repository.register(user, pass)) {
                is Resource.Success -> login(user, pass) // Oto login
                is Resource.Error -> _authState.value = Resource.Error(res.message ?: "Hata")
                else -> {}
            }
        }
    }
}
