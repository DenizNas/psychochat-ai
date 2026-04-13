package com.psikochat.app.data.repository
import com.psikochat.app.data.api.PsikoApi
import com.psikochat.app.data.model.LoginRequest
import com.psikochat.app.data.model.RegisterRequest
import com.psikochat.app.data.model.Resource

class AuthRepository(private val api: PsikoApi) {
    suspend fun login(username: String, pass: String): Resource<String> {
        return try {
            val res = api.login(LoginRequest(username, pass))
            Resource.Success(res.access_token)
        } catch (e: Exception) {
            Resource.Error(e.message ?: "Bilinmeyen bir hata oluştu")
        }
    }
    suspend fun register(username: String, pass: String): Resource<Boolean> {
        return try {
            api.register(RegisterRequest(username, pass))
            Resource.Success(true)
        } catch (e: Exception) {
            Resource.Error(e.message ?: "Kayıt başarısız")
        }
    }
}
