package com.psikochat.app.data.repository
import com.psikochat.app.data.api.PsikoApi
import com.psikochat.app.data.model.LoginRequest
import com.psikochat.app.data.model.RegisterRequest
import com.psikochat.app.data.model.AuthResponse
import com.psikochat.app.data.model.Resource

import retrofit2.HttpException
import java.io.IOException
import org.json.JSONObject

class AuthRepository(private val api: PsikoApi) {
    suspend fun login(user: String, pass: String): Resource<AuthResponse> {
        return try {
            val res = api.login(LoginRequest(user, pass))
            Resource.Success(res)
        } catch (e: Exception) {
            parseError(e, "Giriş başarısız")
        }
    }
    
    suspend fun register(user: String, pass: String): Resource<Boolean> {
        return try {
            api.register(RegisterRequest(user, pass))
            Resource.Success(true)
        } catch (e: Exception) {
            parseError(e, "Kayıt başarısız")
        }
    }

    private fun <T> parseError(e: Exception, defaultMessage: String): Resource<T> {
        return when (e) {
            is HttpException -> {
                val errorBody = e.response()?.errorBody()?.string()
                val parsedMessage = try {
                    if (!errorBody.isNullOrBlank()) {
                        val json = JSONObject(errorBody)
                        if (json.has("detail")) json.getString("detail") else defaultMessage
                    } else defaultMessage
                } catch (ex: Exception) {
                    defaultMessage
                }
                Resource.Error(parsedMessage)
            }
            is IOException -> Resource.Error("Sunucuya bağlanılamadı. Lütfen internet bağlantınızı kontrol edin.")
            else -> Resource.Error(e.message ?: defaultMessage)
        }
    }
}
