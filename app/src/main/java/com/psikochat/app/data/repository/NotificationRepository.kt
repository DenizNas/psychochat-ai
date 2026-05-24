package com.psikochat.app.data.repository

import com.psikochat.app.data.api.PsikoApi
import com.psikochat.app.data.model.Resource
import com.psikochat.app.data.model.NotificationEvent
import retrofit2.HttpException
import java.io.IOException
import org.json.JSONObject

class NotificationRepository(private val api: PsikoApi) {

    suspend fun getNotifications(): Resource<List<NotificationEvent>> {
        return try {
            val response = api.getNotifications()
            Resource.Success(response)
        } catch (e: Exception) {
            parseError(e, "Bildirimler alınamadı")
        }
    }

    suspend fun refreshNotifications(): Resource<List<NotificationEvent>> {
        return try {
            val response = api.refreshNotifications()
            Resource.Success(response)
        } catch (e: Exception) {
            parseError(e, "Bildirim takvimi yenilenemedi")
        }
    }

    suspend fun markNotificationDelivered(notificationId: Int): Resource<String> {
        return try {
            val response = api.markNotificationDelivered(notificationId)
            Resource.Success(response["detail"] ?: "Bildirim iletildi")
        } catch (e: Exception) {
            parseError(e, "Bildirim durumu güncellenemedi")
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
            is IOException -> Resource.Error("Bağlantı hatası. İnternet bağlantınızı kontrol edin.")
            else -> Resource.Error(e.message ?: defaultMessage)
        }
    }
}
