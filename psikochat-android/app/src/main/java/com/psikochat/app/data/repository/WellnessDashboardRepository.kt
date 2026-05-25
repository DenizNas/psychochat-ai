package com.psikochat.app.data.repository

import com.psikochat.app.data.api.PsikoApi
import com.psikochat.app.data.model.Resource
import com.psikochat.app.data.model.WellnessDashboardResponse
import com.psikochat.app.data.local.dao.DashboardDao
import com.psikochat.app.data.local.entity.CachedDashboard
import com.google.gson.Gson
import retrofit2.HttpException
import java.io.IOException
import java.text.SimpleDateFormat
import java.util.*
import org.json.JSONObject

class WellnessDashboardRepository(
    private val api: PsikoApi,
    private val dashboardDao: DashboardDao
) {
    private val gson = Gson()

    /**
     * Resilient wellness dashboard retrieval.
     * If online, fetches fresh data from server and caches it.
     * If offline or fetch fails, falls back to the locally cached database entry.
     */
    suspend fun getWellnessDashboard(
        userId: String,
        days: Int,
        isOnline: Boolean
    ): Resource<WellnessDashboardResponse> {
        if (isOnline) {
            return try {
                val response = api.getWellnessDashboard(days)
                val timestamp = SimpleDateFormat("dd.MM.yyyy HH:mm", Locale.getDefault()).format(Date())
                
                // Cache successfully loaded response
                val jsonStr = gson.toJson(response)
                dashboardDao.insertCachedDashboard(
                    CachedDashboard(
                        userId = userId,
                        dashboardJson = jsonStr,
                        lastUpdated = timestamp
                    )
                )
                
                response.lastUpdated = null // fresh from server
                Resource.Success(response)
            } catch (e: Exception) {
                // If network/server failure occurs, fall back to cache
                getCachedDashboardResilient(userId, e)
            }
        } else {
            // Force offline cache retrieval
            return getCachedDashboardResilient(userId, IOException("Çevrimdışı mod etkin"))
        }
    }

    private suspend fun getCachedDashboardResilient(
        userId: String,
        originalException: Exception
    ): Resource<WellnessDashboardResponse> {
        val cached = dashboardDao.getCachedDashboard(userId)
        return if (cached != null) {
            try {
                val response = gson.fromJson(cached.dashboardJson, WellnessDashboardResponse::class.java)
                response.lastUpdated = cached.lastUpdated
                Resource.Success(response)
            } catch (ex: Exception) {
                parseError(originalException, "Wellness dashboard yüklenemedi")
            }
        } else {
            parseError(originalException, "İnternet bağlantısı yok ve yerel önbellek bulunamadı")
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
