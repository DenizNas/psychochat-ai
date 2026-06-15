package com.psikochat.app.ui.auth

import android.util.Log
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.psikochat.app.data.local.TokenManager
import com.psikochat.app.data.model.*
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
                        tokenManager.saveAuthData(it.access_token, it.username, it.email, it.fullName, it.role)
                        Log.d(TAG, "LOGIN | Başarılı, token DataStore'a kaydedildi. Kullanıcı: ${it.username}, Rol: ${it.role}")
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
    
    fun register(
        fullName: String,
        email: String,
        pass: String,
        role: String = "user",
        title: String? = null,
        specialty: String? = null,
        bio: String? = null
    ) {
        if (fullName.isBlank() || email.isBlank() || pass.isBlank()) {
            _authState.value = Resource.Error("Ad soyad, e-posta ve şifre boş bırakılamaz")
            return
        }
        if (role == "psychologist") {
            if (title.isNullOrBlank() || specialty.isNullOrBlank() || bio.isNullOrBlank()) {
                _authState.value = Resource.Error("Psikolog kaydı için unvan, uzmanlık alanı ve biyografi boş bırakılamaz")
                return
            }
            if (bio.length < 20) {
                _authState.value = Resource.Error("Biyografi en az 20 karakter uzunluğunda olmalıdır")
                return
            }
        }
        
        viewModelScope.launch {
            _authState.value = Resource.Loading()
            Log.d(TAG, "REGISTER | Kayıt işlemi başlatıldı. E-posta: $email, Rol: $role")
            when (val res = repository.register(fullName, email, pass, role, title, specialty, bio)) {
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

    // Password reset state flows
    private val _resetRequestState = MutableStateFlow<Resource<Boolean>>(Resource.Success(false))
    val resetRequestState: StateFlow<Resource<Boolean>> = _resetRequestState

    private val _verifyCodeState = MutableStateFlow<Resource<String?>>(Resource.Success(null))
    val verifyCodeState: StateFlow<Resource<String?>> = _verifyCodeState

    private val _resetCompleteState = MutableStateFlow<Resource<Boolean>>(Resource.Success(false))
    val resetCompleteState: StateFlow<Resource<Boolean>> = _resetCompleteState

    fun requestPasswordReset(email: String) {
        if (email.isBlank()) {
            _resetRequestState.value = Resource.Error("E-posta adresi boş bırakılamaz")
            return
        }
        viewModelScope.launch {
            _resetRequestState.value = Resource.Loading()
            Log.d(TAG, "PASSWORD_RESET_REQUEST_STARTED | E-posta: $email")
            when (val res = repository.requestPasswordReset(email)) {
                is Resource.Success -> {
                    Log.d(TAG, "PASSWORD_RESET_REQUEST_SUCCESS | E-posta: $email")
                    _resetRequestState.value = Resource.Success(true)
                }
                is Resource.Error -> {
                    Log.w(TAG, "PASSWORD_RESET_REQUEST_ERROR | Hata: ${res.message}")
                    _resetRequestState.value = Resource.Error(res.message ?: "İstek hatası")
                }
                else -> {}
            }
        }
    }

    fun verifyPasswordResetCode(email: String, code: String) {
        if (email.isBlank() || code.isBlank()) {
            _verifyCodeState.value = Resource.Error("E-posta ve doğrulama kodu boş bırakılamaz")
            return
        }
        viewModelScope.launch {
            _verifyCodeState.value = Resource.Loading()
            Log.d(TAG, "PASSWORD_RESET_VERIFY_STARTED | E-posta: $email, Kod: $code")
            when (val res = repository.verifyPasswordResetCode(email, code)) {
                is Resource.Success -> {
                    Log.d(TAG, "PASSWORD_RESET_VERIFY_SUCCESS | E-posta: $email")
                    _verifyCodeState.value = Resource.Success(res.data?.reset_token)
                }
                is Resource.Error -> {
                    Log.w(TAG, "PASSWORD_RESET_VERIFY_ERROR | Hata: ${res.message}")
                    _verifyCodeState.value = Resource.Error(res.message ?: "Doğrulama hatası")
                }
                else -> {}
            }
        }
    }

    fun completePasswordReset(resetToken: String, newPass: String) {
        if (resetToken.isBlank() || newPass.isBlank()) {
            _resetCompleteState.value = Resource.Error("Yeni şifre boş bırakılamaz")
            return
        }
        viewModelScope.launch {
            _resetCompleteState.value = Resource.Loading()
            Log.d(TAG, "PASSWORD_RESET_COMPLETE_STARTED")
            when (val res = repository.completePasswordReset(resetToken, newPass)) {
                is Resource.Success -> {
                    Log.d(TAG, "PASSWORD_RESET_COMPLETE_SUCCESS")
                    _resetCompleteState.value = Resource.Success(true)
                }
                is Resource.Error -> {
                    Log.w(TAG, "PASSWORD_RESET_COMPLETE_ERROR | Hata: ${res.message}")
                    _resetCompleteState.value = Resource.Error(res.message ?: "Şifre sıfırlama hatası")
                }
                else -> {}
            }
        }
    }

    fun resetResetStates() {
        _resetRequestState.value = Resource.Success(false)
        _verifyCodeState.value = Resource.Success(null)
        _resetCompleteState.value = Resource.Success(false)
    }
}

