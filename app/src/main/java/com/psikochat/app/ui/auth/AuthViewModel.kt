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

    fun login(user: String, pass: String) {
        if (user.isBlank() || pass.isBlank()) {
            _authState.value = Resource.Error("Kullanıcı adı ve şifre boş bırakılamaz")
            return
        }

        viewModelScope.launch {
            _authState.value = Resource.Loading()
            Log.d(TAG, "LOGIN | Giriş deneniyor, kullanıcı: $user")
            when (val res = repository.login(user, pass)) {
                is Resource.Success -> {
                    res.data?.let {
                        tokenManager.saveAuthData(it.access_token, it.username)
                        Log.d(TAG, "LOGIN | Başarılı. Token DataStore'a kaydedildi. Kullanıcı: ${it.username}")
                    }
                    _authState.value = Resource.Success(true)
                }
                is Resource.Error -> {
                    Log.w(TAG, "LOGIN | Başarısız: ${res.message}")
                    _authState.value = Resource.Error(res.message ?: "Giriş hatası")
                }
                else -> {}
            }
        }
    }

    /**
     * Kayıt işlemi: Başarılı olursa otomatik olarak giriş yapılır.
     * Token DataStore'a kaydedilir, kullanıcı login ekranına yönlendirilmez.
     * Otomatik login başarısız olursa Türkçe hata mesajı gösterilir.
     */
    fun register(user: String, pass: String) {
        if (user.isBlank() || pass.isBlank()) {
            _authState.value = Resource.Error("Kullanıcı adı ve şifre boş bırakılamaz")
            return
        }

        viewModelScope.launch {
            _authState.value = Resource.Loading()
            Log.d(TAG, "REGISTER | Kayıt deneniyor, kullanıcı: $user")
            when (val res = repository.register(user, pass)) {
                is Resource.Success -> {
                    Log.d(TAG, "REGISTER | Kayıt başarılı. Otomatik giriş yapılıyor...")
                    // Kayıt başarılı — otomatik giriş yap (UX iyileştirmesi)
                    when (val loginRes = repository.login(user, pass)) {
                        is Resource.Success -> {
                            loginRes.data?.let {
                                tokenManager.saveAuthData(it.access_token, it.username)
                                Log.d(TAG, "REGISTER+LOGIN | Token DataStore'a kaydedildi. Kullanıcı: ${it.username}")
                            }
                            _authState.value = Resource.Success(true)
                        }
                        is Resource.Error -> {
                            // Kayıt tamam ama otomatik giriş başarısız — kullanıcıya bildir
                            Log.w(TAG, "REGISTER | Otomatik giriş başarısız: ${loginRes.message}. Login sayfasına yönlendiriliyor.")
                            _authState.value = Resource.Error("Kayıt başarılı! Lütfen giriş yapın.")
                        }
                        else -> {}
                    }
                }
                is Resource.Error -> {
                    Log.w(TAG, "REGISTER | Başarısız: ${res.message}")
                    _authState.value = Resource.Error(res.message ?: "Kayıt hatası")
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
            Log.d(TAG, "LOGOUT | Kullanıcı çıkış yapıyor, auth verileri temizleniyor.")
            tokenManager.clearAuthData()
            resetState()
        }
    }
}
