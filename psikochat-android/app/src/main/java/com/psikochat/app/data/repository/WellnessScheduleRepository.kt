package com.psikochat.app.data.repository

import com.psikochat.app.data.api.PsikoApi
import com.psikochat.app.data.model.Resource
import com.psikochat.app.data.model.ScheduledIntervention
import retrofit2.HttpException
import java.io.IOException
import org.json.JSONObject

class WellnessScheduleRepository(private val api: PsikoApi) {

    suspend fun getScheduledInterventions(): Resource<List<ScheduledIntervention>> {
        return try {
            val response = api.getScheduledInterventions()
            Resource.Success(response)
        } catch (e: Exception) {
            parseError(e, "Wellness programı yüklenemedi")
        }
    }

    suspend fun refreshScheduledInterventions(): Resource<List<ScheduledIntervention>> {
        return try {
            val response = api.refreshScheduledInterventions()
            Resource.Success(response)
        } catch (e: Exception) {
            parseError(e, "Wellness programı güncellenemedi")
        }
    }

    suspend fun getWellnessPlan(): Resource<com.psikochat.app.data.model.WellnessPlanResponse> {
        return try {
            val response = api.getWellnessPlan()
            Resource.Success(response)
        } catch (e: Exception) {
            parseError(e, "Wellness planı yüklenemedi")
        }
    }

    suspend fun refreshWellnessPlan(): Resource<com.psikochat.app.data.model.WellnessPlanResponse> {
        return try {
            val response = api.refreshWellnessPlan()
            Resource.Success(response)
        } catch (e: Exception) {
            parseError(e, "Wellness planı güncellenemedi")
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
            is IOException -> Resource.Error("Sunucuya bağlanılamadı. İnternet bağlantınızı kontrol edin.")
            else -> Resource.Error(e.message ?: defaultMessage)
        }
    }
}
