package com.psikochat.app.data.repository
import com.psikochat.app.data.api.PsikoApi
import com.psikochat.app.data.model.ChatRequest
import com.psikochat.app.data.model.ChatResponse
import com.psikochat.app.data.model.HistoryItem
import com.psikochat.app.data.model.Resource

import retrofit2.HttpException
import java.io.IOException
import java.net.SocketTimeoutException
import org.json.JSONObject

class ChatRepository(private val api: PsikoApi) {
    suspend fun getHistory(): Resource<List<HistoryItem>> {
        return try {
            val res = api.getHistory()
            Resource.Success(res)
        } catch (e: Exception) {
            parseError(e, "Geçmiş yüklenemedi")
        }
    }
    
    suspend fun sendMessage(text: String, language: String = "tr"): Resource<ChatResponse> {
        return try {
            val res = api.sendMessage(ChatRequest(text = text, language = language))
            Resource.Success(res)
        } catch (e: Exception) {
            parseError(e, "Mesaj gönderilemedi")
        }
    }

    private fun <T> parseError(e: Exception, defaultMessage: String): Resource<T> {
        return when (e) {
            is HttpException -> {
                if (e.code() == 401 || e.code() == 403) {
                    return Resource.Error("Oturumunuzun süresi doldu. Lütfen tekrar giriş yapın.")
                }
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
            is SocketTimeoutException -> Resource.Error("Yanıt alınamadı, lütfen tekrar deneyin")
            is IOException -> Resource.Error("Sunucuya bağlanılamadı. İnternet bağlantınızı kontrol edin.")
            else -> Resource.Error(e.message ?: defaultMessage)
        }
    }
}
