package com.psikochat.app.data.repository

import android.util.Log
import com.psikochat.app.data.api.PsikoApi
import com.psikochat.app.data.model.*
import retrofit2.HttpException
import java.io.IOException
import org.json.JSONObject

class AuthRepository(private val api: PsikoApi) {
    companion object {
        private const val TAG = "AuthRepository"
    }

    suspend fun login(email: String, pass: String): Resource<AuthResponse> {
        Log.d(TAG, "LOGIN | Request başladı, e-posta: $email")
        return try {
            val res = api.login(LoginRequest(email, pass))
            Log.d(TAG, "LOGIN | İstek başarılı, token alındı.")
            Resource.Success(res)
        } catch (e: Exception) {
            val activeBaseUrl = com.psikochat.app.data.api.RetrofitClient.BASE_URL
            val fullUrl = "${activeBaseUrl.removeSuffix("/")}/login"
            val status = if (e is HttpException) e.code().toString() else "N/A"
            Log.e(TAG, "LOGIN | HATA. Active BASE_URL: $activeBaseUrl, Full URL: $fullUrl, Exception: ${e.javaClass.name} - ${e.message}, Status Code: $status", e)
            parseError(e, "Giriş başarısız")
        }
    }
    
    suspend fun register(
        fullName: String,
        email: String,
        pass: String,
        role: String = "user",
        title: String? = null,
        specialty: String? = null,
        bio: String? = null
    ): Resource<Boolean> {
        Log.d(TAG, "REGISTER | Request başladı, e-posta: $email, role: $role")
        return try {
            val res = api.register(RegisterRequest(fullName, email, pass, role, title, specialty, bio))
            Log.d(TAG, "REGISTER | İstek başarılı: ${res.message}")
            Resource.Success(true)
        } catch (e: Exception) {
            parseError(e, "Kayıt başarısız")
        }
    }

    suspend fun requestPasswordReset(email: String): Resource<Boolean> {
        Log.d(TAG, "PASSWORD_RESET_REQUEST_STARTED | E-posta: $email")
        return try {
            api.requestPasswordReset(PasswordResetRequest(email))
            Log.d(TAG, "PASSWORD_RESET_REQUEST_SUCCESS | E-posta: $email")
            Resource.Success(true)
        } catch (e: Exception) {
            Log.e(TAG, "PASSWORD_RESET_REQUEST_ERROR | Hata: ${e.message}")
            parseError(e, "Şifre sıfırlama talebi başarısız oldu.")
        }
    }
    
    suspend fun verifyPasswordResetCode(email: String, code: String): Resource<PasswordResetVerifyResponse> {
        Log.d(TAG, "PASSWORD_RESET_VERIFY_STARTED | E-posta: $email, Kod: $code")
        return try {
            val res = api.verifyPasswordResetCode(PasswordResetVerifyRequest(email, code))
            Log.d(TAG, "PASSWORD_RESET_VERIFY_SUCCESS | E-posta: $email")
            Resource.Success(res)
        } catch (e: Exception) {
            Log.e(TAG, "PASSWORD_RESET_VERIFY_ERROR | Hata: ${e.message}")
            parseError(e, "Kod doğrulama başarısız oldu.")
        }
    }
    
    suspend fun completePasswordReset(resetToken: String, newPass: String): Resource<Boolean> {
        Log.d(TAG, "PASSWORD_RESET_COMPLETE_STARTED")
        return try {
            api.completePasswordReset(PasswordResetCompleteRequest(resetToken, newPass))
            Log.d(TAG, "PASSWORD_RESET_COMPLETE_SUCCESS")
            Resource.Success(true)
        } catch (e: Exception) {
            Log.e(TAG, "PASSWORD_RESET_COMPLETE_ERROR | Hata: ${e.message}")
            parseError(e, "Şifre güncelleme başarısız oldu.")
        }
    }

    private fun <T>
 parseError(e: Exception, defaultMessage: String): Resource<T> {
        return when (e) {
            is HttpException -> {
                val code = e.code()
                val errorBody = e.response()?.errorBody()?.string()
                Log.w(TAG, "HTTP Exception | Status Code: $code, Error Body: $errorBody")
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
                Log.w(TAG, "Parsed Error Message: $parsedMessage")
                Resource.Error(parsedMessage)
            }
            is IOException -> {
                Log.e(TAG, "IO Exception | Sunucuya bağlanılamadı: ${e.message}")
                Resource.Error("Sunucuya bağlanılamadı. Lütfen internet bağlantınızı kontrol edin.")
            }
            else -> {
                Log.e(TAG, "Unknown Exception | Detay: ${e.message}")
                Resource.Error(e.message ?: defaultMessage)
            }
        }
    }
}
