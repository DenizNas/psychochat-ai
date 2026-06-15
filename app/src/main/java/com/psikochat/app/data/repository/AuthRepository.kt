package com.psikochat.app.data.repository
import com.psikochat.app.data.api.PsikoApi
import com.psikochat.app.data.model.LoginRequest
import com.psikochat.app.data.model.RegisterRequest
import com.psikochat.app.data.model.AuthResponse
import com.psikochat.app.data.model.Resource
import com.psikochat.app.data.model.PasswordResetRequest
import com.psikochat.app.data.model.PasswordResetVerifyRequest
import com.psikochat.app.data.model.PasswordResetVerifyResponse
import com.psikochat.app.data.model.PasswordResetCompleteRequest

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

    suspend fun requestPasswordReset(email: String): Resource<Boolean> {
        return try {
            api.requestPasswordReset(PasswordResetRequest(email))
            Resource.Success(true)
        } catch (e: Exception) {
            parseError(e, "Şifre sıfırlama talebi başarısız oldu.")
        }
    }
    
    suspend fun verifyPasswordResetCode(email: String, code: String): Resource<PasswordResetVerifyResponse> {
        return try {
            val res = api.verifyPasswordResetCode(PasswordResetVerifyRequest(email, code))
            Resource.Success(res)
        } catch (e: Exception) {
            parseError(e, "Kod doğrulama başarısız oldu.")
        }
    }
    
    suspend fun completePasswordReset(resetToken: String, newPass: String): Resource<Boolean> {
        return try {
            api.completePasswordReset(PasswordResetCompleteRequest(resetToken, newPass))
            Resource.Success(true)
        } catch (e: Exception) {
            parseError(e, "Şifre güncelleme başarısız oldu.")
        }
    }

    private fun <T> parseError(e: Exception, defaultMessage: String): Resource<T> {
        return when (e) {
            is HttpException -> {
                val errorBody = e.response()?.errorBody()?.string()
                val parsedMessage = try {
                    if (!errorBody.isNullOrBlank()) {
                        val json = JSONObject(errorBody)
                        when {
                            json.has("message") -> json.getString("message")
                            json.has("detail") -> json.getString("detail")
                            else -> defaultMessage
                        }
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
