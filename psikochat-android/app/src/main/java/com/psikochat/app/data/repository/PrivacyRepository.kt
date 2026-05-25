package com.psikochat.app.data.repository

import com.psikochat.app.data.api.PsikoApi
import com.psikochat.app.data.model.UserConsentResponse
import com.psikochat.app.data.model.UpdateConsentRequest
import com.psikochat.app.data.model.DeleteDataRequest
import com.psikochat.app.data.model.Resource
import retrofit2.HttpException
import java.io.IOException
import org.json.JSONObject

class PrivacyRepository(private val api: PsikoApi) {

    suspend fun getPrivacyConsent(): Resource<UserConsentResponse> {
        return try {
            val response = api.getPrivacyConsent()
            Resource.Success(response)
        } catch (e: Exception) {
            parseError(e, "Gizlilik ve onay tercihleri alınamadı")
        }
    }

    suspend fun updatePrivacyConsent(request: UpdateConsentRequest): Resource<UserConsentResponse> {
        return try {
            val response = api.updatePrivacyConsent(request)
            Resource.Success(response)
        } catch (e: Exception) {
            parseError(e, "Gizlilik ve onay tercihleri güncellenemedi")
        }
    }

    suspend fun exportPrivacyData(): Resource<Map<String, Any>> {
        return try {
            val response = api.exportPrivacyData()
            Resource.Success(response)
        } catch (e: Exception) {
            parseError(e, "Kişisel veriler dışa aktarılamadı")
        }
    }

    suspend fun deletePrivacyAccount(confirm: String): Resource<Map<String, String>> {
        return try {
            val response = api.deletePrivacyAccount(DeleteDataRequest(confirm))
            Resource.Success(response)
        } catch (e: Exception) {
            parseError(e, "Hesap silme işlemi başarısız oldu")
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
            is IOException -> Resource.Error("Sunucuya bağlanılamadı. İnternet bağlantınızı kontrol edin.")
            else -> Resource.Error(e.message ?: defaultMessage)
        }
    }
}
