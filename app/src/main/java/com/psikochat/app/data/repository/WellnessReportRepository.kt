package com.psikochat.app.data.repository

import com.psikochat.app.data.api.PsikoApi
import com.psikochat.app.data.model.Resource
import com.psikochat.app.data.model.WellnessReport
import com.psikochat.app.data.local.dao.ReportDao
import com.psikochat.app.data.local.entity.CachedReport
import com.google.gson.Gson
import retrofit2.HttpException
import java.io.IOException
import java.text.SimpleDateFormat
import java.util.*
import org.json.JSONObject

class WellnessReportRepository(
    private val api: PsikoApi,
    private val reportDao: ReportDao
) {
    private val gson = Gson()

    /**
     * Resilient wellness report retrieval.
     * If online, fetches fresh report from server and caches it.
     * If offline or fetch fails, falls back to the locally cached database entry.
     */
    suspend fun getWellnessReport(
        userId: String,
        period: String,
        days: Int,
        isOnline: Boolean
    ): Resource<WellnessReport> {
        if (isOnline) {
            return try {
                val response = api.getWellnessReport(period, days)
                val timestamp = SimpleDateFormat("dd.MM.yyyy HH:mm", Locale.getDefault()).format(Date())
                
                // Cache successfully loaded response
                val jsonStr = gson.toJson(response)
                
                // Clean old cached report for this period/days before inserting new
                val cached = reportDao.getCachedReport(userId, period, days)
                val idToInsert = cached?.id ?: 0
                
                reportDao.insertCachedReport(
                    CachedReport(
                        id = idToInsert,
                        userId = userId,
                        period = period,
                        days = days,
                        reportJson = jsonStr,
                        lastUpdated = timestamp
                    )
                )
                
                response.lastUpdated = null // fresh from server
                Resource.Success(response)
            } catch (e: Exception) {
                // If network/server failure occurs, fall back to cache
                getCachedReportResilient(userId, period, days, e)
            }
        } else {
            // Force offline cache retrieval
            return getCachedReportResilient(userId, period, days, IOException("Çevrimdışı mod etkin"))
        }
    }

    private suspend fun getCachedReportResilient(
        userId: String,
        period: String,
        days: Int,
        originalException: Exception
    ): Resource<WellnessReport> {
        val cached = reportDao.getCachedReport(userId, period, days)
        return if (cached != null) {
            try {
                val response = gson.fromJson(cached.reportJson, WellnessReport::class.java)
                response.lastUpdated = cached.lastUpdated
                Resource.Success(response)
            } catch (ex: Exception) {
                parseError(originalException, "Wellness raporu yüklenemedi")
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
