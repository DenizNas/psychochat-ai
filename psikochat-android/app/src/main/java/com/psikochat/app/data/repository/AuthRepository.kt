package com.psikochat.app.data.repository

import android.util.Log
import com.psikochat.app.data.api.PsikoApi
import com.psikochat.app.data.model.LoginRequest
import com.psikochat.app.data.model.RegisterRequest
import com.psikochat.app.data.model.AuthResponse
import com.psikochat.app.data.model.Resource
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
            parseError(e, "Giriş başarısız")
        }
    }
    
    suspend fun register(fullName: String, email: String, pass: String): Resource<Boolean> {
        Log.d(TAG, "REGISTER | Request başladı, e-posta: $email")
        return try {
            val res = api.register(RegisterRequest(fullName, email, pass))
            Log.d(TAG, "REGISTER | İstek başarılı: ${res.message}")
            Resource.Success(true)
        } catch (e: Exception) {
            parseError(e, "Kayıt başarısız")
        }
    }

    private fun <T> parseError(e: Exception, defaultMessage: String): Resource<T> {
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
