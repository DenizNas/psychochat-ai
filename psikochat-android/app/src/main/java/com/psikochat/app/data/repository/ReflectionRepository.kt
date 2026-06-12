package com.psikochat.app.data.repository

import com.psikochat.app.data.api.PsikoApi
import com.psikochat.app.data.model.WellnessReport
import com.psikochat.app.data.model.ReflectionResponse
import com.psikochat.app.data.model.Resource
import retrofit2.HttpException

/**
 * ReflectionRepository
 * ====================
 * Provides wellness report and reflection data for the Reflection/Report screens.
 *
 * NOTE: PsikoApi has no standalone getReflections() endpoint.
 * ReflectionResponse is available via WellnessDashboardResponse.sections.latestReflection.
 * getWellnessReport() uses the existing /analytics/reports/wellness endpoint directly.
 */
class ReflectionRepository(private val api: PsikoApi) {

    /**
     * Fetches the wellness report for the given period and day window.
     * Uses the existing /analytics/reports/wellness endpoint.
     */
    suspend fun getWellnessReport(period: String, days: Int = 7): Resource<WellnessReport> {
        return try {
            val response = api.getWellnessReport(period, days)
            Resource.Success(response)
        } catch (e: Exception) {
            val isPremium = e is HttpException && (e.code() == 403 || e.response()?.errorBody()?.string()?.contains("PREMIUM_MEMBER_REQUIRED") == true)
            Resource.Error(e.message ?: "Zihinsel wellness raporu yüklenemedi.", isPremiumRequired = isPremium)
        }
    }

    /**
     * Fetches the latest AI reflection for the user.
     * Derived from WellnessDashboardResponse.sections.latestReflection,
     * since no standalone reflection endpoint exists in PsikoApi.
     *
     * @param period Used to select day window: "daily" = 1 day, otherwise 7 days.
     */
    suspend fun getReflections(period: String): Resource<ReflectionResponse> {
        return try {
            val days = if (period == "daily") 1 else 7
            val dashboard = api.getWellnessDashboard(days)
            val reflection = dashboard.sections.latestReflection
            if (reflection != null) {
                Resource.Success(reflection)
            } else {
                Resource.Error("Henüz bir refleksiyon özeti oluşturulmadı.")
            }
        } catch (e: Exception) {
            val isPremium = e is HttpException && (e.code() == 403 || e.response()?.errorBody()?.string()?.contains("PREMIUM_MEMBER_REQUIRED") == true)
            Resource.Error(e.message ?: "Zihinsel refleksiyon özeti yüklenemedi.", isPremiumRequired = isPremium)
        }
    }
}
