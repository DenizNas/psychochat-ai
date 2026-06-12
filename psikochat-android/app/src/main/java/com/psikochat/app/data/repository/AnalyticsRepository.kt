package com.psikochat.app.data.repository

import com.psikochat.app.data.api.PsikoApi
import com.psikochat.app.data.model.WellnessDashboardResponse
import com.psikochat.app.data.model.BehavioralInsight
import com.psikochat.app.data.model.SmartIntervention
import com.psikochat.app.data.model.Resource
import retrofit2.HttpException

/**
 * AnalyticsRepository
 * ===================
 * Provides analytics data for the Insights screen.
 *
 * All data is derived from the existing /analytics/dashboard endpoint
 * (WellnessDashboardResponse), which includes:
 *   - overview.dominantEmotion, overview.crisisCount, overview.totalMessages
 *   - sections.emotionDistribution (Map<String, Int>)
 *   - sections.dailyTrend (List<DailyTrendItem>)
 *   - sections.topInsights (List<BehavioralInsight>)
 *   - sections.activeInterventions (List<SmartIntervention>)
 *
 * NOTE: EmotionSummaryResponse, EmotionTimelineItem, getEmotionSummary, getEmotionTimeline,
 * getInsights, and getInterventions as separate endpoints do not exist in PsikoApi.
 * All analytics data is fetched from the unified dashboard endpoint.
 */
class AnalyticsRepository(private val api: PsikoApi) {

    /**
     * Returns the full wellness dashboard response which carries
     * all the data that InsightsScreen needs for its summary state.
     */
    suspend fun getEmotionSummary(days: Int = 7): Resource<WellnessDashboardResponse> {
        return try {
            val response = api.getWellnessDashboard(days)
            Resource.Success(response)
        } catch (e: Exception) {
            val isPremium = e is HttpException && (e.code() == 403 || e.response()?.errorBody()?.string()?.contains("PREMIUM_MEMBER_REQUIRED") == true)
            Resource.Error(e.message ?: "Duygu özet verileri yüklenemedi.", isPremiumRequired = isPremium)
        }
    }

    /**
     * Returns behavioural insights extracted from the dashboard sections.
     * These are pre-computed server-side and returned in sections.topInsights.
     */
    suspend fun getInsights(days: Int = 7): Resource<List<BehavioralInsight>> {
        return try {
            val response = api.getWellnessDashboard(days)
            Resource.Success(response.sections.topInsights)
        } catch (e: Exception) {
            val isPremium = e is HttpException && (e.code() == 403 || e.response()?.errorBody()?.string()?.contains("PREMIUM_MEMBER_REQUIRED") == true)
            Resource.Error(e.message ?: "Davranışsal içgörüler yüklenemedi.", isPremiumRequired = isPremium)
        }
    }

    /**
     * Returns active smart interventions extracted from the dashboard sections.
     * These are pre-scheduled and returned in sections.activeInterventions.
     */
    suspend fun getInterventions(days: Int = 7): Resource<List<SmartIntervention>> {
        return try {
            val response = api.getWellnessDashboard(days)
            Resource.Success(response.sections.activeInterventions)
        } catch (e: Exception) {
            val isPremium = e is HttpException && (e.code() == 403 || e.response()?.errorBody()?.string()?.contains("PREMIUM_MEMBER_REQUIRED") == true)
            Resource.Error(e.message ?: "Wellness müdahaleleri yüklenemedi.", isPremiumRequired = isPremium)
        }
    }
}
