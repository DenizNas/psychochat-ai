package com.psikochat.app.data.repository
import com.psikochat.app.data.api.PsikoApi
import com.psikochat.app.data.model.AuthRequest
import com.psikochat.app.data.model.AuthResponse
import com.psikochat.app.data.model.Resource

class AuthRepository(private val api: PsikoApi) {
    suspend fun login(user: String, pass: String): Resource<AuthResponse> {
        return try {
            val res = api.login(AuthRequest(user, pass))
            Resource.Success(res)
        } catch (e: Exception) {
            Resource.Error(e.message ?: "Bilinmeyen bir hata oluştu")
        }
    }
    suspend fun register(user: String, pass: String): Resource<Boolean> {
        return try {
            api.register(AuthRequest(user, pass))
            Resource.Success(true)
        } catch (e: Exception) {
            Resource.Error(e.message ?: "Kayıt başarısız")
        }
    }
}
