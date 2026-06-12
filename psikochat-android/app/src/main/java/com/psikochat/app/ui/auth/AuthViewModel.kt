package com.psikochat.app.ui.auth

import android.util.Log
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
    
    companion object {
        private const val TAG = "AuthViewModel"
    }
    
    fun login(email: String, pass: String) {
        if (email.isBlank() || pass.isBlank()) {
            _authState.value = Resource.Error("E-posta ve şifre boş bırakılamaz")
            return
        }
        
        viewModelScope.launch {
            _authState.value = Resource.Loading()
            Log.d(TAG, "LOGIN | Başlatıldı, e-posta: $email")
            when (val res = repository.login(email, pass)) {
                is Resource.Success -> {
                    res.data?.let { 
                        tokenManager.saveAuthData(it.access_token, it.username, it.email, it.fullName)
                        Log.d(TAG, "LOGIN | Başarılı, token DataStore'a kaydedildi. Kullanıcı: ${it.username}")
                    }
                    _authState.value = Resource.Success(true)
                }
                is Resource.Error -> {
                    Log.w(TAG, "LOGIN | Başarısız: ${res.message}")
                    _authState.value = Resource.Error(res.message ?: "Hata")
                }
                else -> {}
            }
        }
    }
    
    fun register(fullName: String, email: String, pass: String) {
        if (fullName.isBlank() || email.isBlank() || pass.isBlank()) {
            _authState.value = Resource.Error("Ad soyad, e-posta ve şifre boş bırakılamaz")
            return
        }
        
        viewModelScope.launch {
            _authState.value = Resource.Loading()
            Log.d(TAG, "REGISTER | Kayıt işlemi başlatıldı. E-posta: $email")
            when (val res = repository.register(fullName, email, pass)) {
                is Resource.Success -> {
                    Log.d(TAG, "REGISTER | Kayıt başarılı, otomatik giriş yapılmıyor.")
                    _authState.value = Resource.Success(true)
                }
                is Resource.Error -> {
                    Log.w(TAG, "REGISTER | Kayıt başarısız: ${res.message}")
                    _authState.value = Resource.Error(res.message ?: "Kayıt başarısız")
                }
                else -> {}
            }
        }
    }

    fun resetState() {
        _authState.value = Resource.Success(false)
    }

    fun logout() {
        viewModelScope.launch {
            Log.d(TAG, "LOGOUT | Kullanıcı çıkış yapıyor, token temizleniyor.")
            tokenManager.clearAuthData()
            resetState()
        }
    }
}
