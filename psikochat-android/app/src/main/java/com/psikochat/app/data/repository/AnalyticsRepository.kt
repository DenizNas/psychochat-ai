package com.psikochat.app.data.repository

import com.psikochat.app.data.api.PsikoApi
import com.psikochat.app.data.model.EmotionTimelineItem
import com.psikochat.app.data.model.EmotionSummaryResponse
import com.psikochat.app.data.model.BehavioralInsight
import com.psikochat.app.data.model.SmartIntervention
import com.psikochat.app.data.model.Resource

class AnalyticsRepository(private val api: PsikoApi) {

    suspend fun getEmotionTimeline(days: Int = 7): Resource<List<EmotionTimelineItem>> {
        return try {
            val response = api.getEmotionTimeline(days)
            Resource.Success(response)
        } catch (e: Exception) {
            Resource.Error(e.message ?: "Duygu zaman çizelgesi yüklenemedi.")
        }
    }

    suspend fun getEmotionSummary(days: Int = 7): Resource<EmotionSummaryResponse> {
        return try {
            val response = api.getEmotionSummary(days)
            Resource.Success(response)
        } catch (e: Exception) {
            Resource.Error(e.message ?: "Duygu özet verileri yüklenemedi.")
        }
    }

    suspend fun getInsights(days: Int = 7): Resource<List<BehavioralInsight>> {
        return try {
            val response = api.getInsights(days)
            Resource.Success(response)
        } catch (e: Exception) {
            Resource.Error(e.message ?: "Davranışsal içgörüler yüklenemedi.")
        }
    }

    suspend fun getInterventions(days: Int = 7): Resource<List<SmartIntervention>> {
        return try {
            val response = api.getInterventions(days)
            Resource.Success(response)
        } catch (e: Exception) {
            Resource.Error(e.message ?: "Wellness müdahaleleri yüklenemedi.")
        }
    }
}
