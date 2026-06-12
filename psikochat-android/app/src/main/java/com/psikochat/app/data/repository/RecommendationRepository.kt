package com.psikochat.app.data.repository

import android.util.Log
import com.psikochat.app.data.api.PsikoApi
import com.psikochat.app.data.model.RecommendationFeedbackRequest
import com.psikochat.app.data.model.RecommendationRefreshResponse
import com.psikochat.app.data.model.Resource
import com.psikochat.app.data.model.WellnessRecommendation
import retrofit2.HttpException
import java.io.IOException

/**
 * RecommendationRepository
 * ========================
 * Faz 10 Prompt 7 — Advanced Analytics & Recommendation Engine
 *
 * Data access layer for the privacy-safe Recommendation Engine.
 * All operations go through JWT-authenticated API endpoints.
 *
 * Privacy guarantees:
 *   - No raw text is requested or stored locally
 *   - Recommendations are metadata-derived wellness suggestions only
 *   - No medical diagnosis terminology in any field
 *
 * @param api Injected PsikoApi Retrofit instance (with auth interceptor)
 */
class RecommendationRepository(private val api: PsikoApi) {

    companion object {
        private const val TAG = "RecommendationRepo"
    }

    /**
     * Fetches currently active (non-expired) recommendations from the backend.
     * Returns cached active records — does NOT regenerate.
     */
    suspend fun getRecommendations(): Resource<List<WellnessRecommendation>> {
        return try {
            val recs = api.getRecommendations()
            Log.d(TAG, "GET recommendations success | count=${recs.size}")
            Resource.Success(recs)
        } catch (e: HttpException) {
            Log.e(TAG, "GET recommendations HTTP error: ${e.code()}")
            val isPremium = try {
                val errorBody = e.response()?.errorBody()?.string()
                errorBody?.contains("PREMIUM_MEMBER_REQUIRED") == true
            } catch (ex: Exception) {
                false
            }
            Resource.Error("Öneriler alınamadı (${e.code()})", isPremiumRequired = isPremium || e.code() == 403)
        } catch (e: IOException) {
            Log.e(TAG, "GET recommendations network error: ${e.message}")
            Resource.Error("Sunucuya bağlanılamadı.")
        } catch (e: Exception) {
            Log.e(TAG, "GET recommendations failed: ${e.message}")
            Resource.Error("Öneriler alınamadı.")
        }
    }

    /**
     * Requests the backend to generate fresh personalised recommendations.
     * Consent and privacy_mode checks are enforced server-side.
     * Duplicate guard: won't regenerate types already active within 48h.
     */
    suspend fun refreshRecommendations(): Resource<RecommendationRefreshResponse> {
        return try {
            val response = api.refreshRecommendations()
            Log.d(TAG, "Refresh recommendations success | generated=${response.generated}")
            Resource.Success(response)
        } catch (e: HttpException) {
            Log.e(TAG, "Refresh recommendations HTTP error: ${e.code()}")
            val isPremium = try {
                val errorBody = e.response()?.errorBody()?.string()
                errorBody?.contains("PREMIUM_MEMBER_REQUIRED") == true
            } catch (ex: Exception) {
                false
            }
            Resource.Error("Öneriler yenilenemedi (${e.code()})", isPremiumRequired = isPremium || e.code() == 403)
        } catch (e: IOException) {
            Log.e(TAG, "Refresh recommendations network error: ${e.message}")
            Resource.Error("Sunucuya bağlanılamadı.")
        } catch (e: Exception) {
            Log.e(TAG, "Refresh recommendations failed: ${e.message}")
            Resource.Error("Öneriler yenilenemedi.")
        }
    }

    /**
     * Submits user feedback for a specific recommendation.
     *
     * @param recId The recommendation ID (e.g. "rec_user_breathing_break_202605241200")
     * @param feedback One of: "helpful" | "not_helpful" | "dismissed"
     */
    suspend fun submitFeedback(recId: String, feedback: String): Resource<Map<String, String>> {
        return try {
            val result = api.submitRecommendationFeedback(
                recId = recId,
                request = RecommendationFeedbackRequest(feedback = feedback)
            )
            Log.d(TAG, "Feedback submitted | rec_id=$recId | feedback=$feedback")
            Resource.Success(result)
        } catch (e: HttpException) {
            Log.e(TAG, "Feedback submit HTTP error: ${e.code()}")
            Resource.Error("Geri bildirim gönderilemedi (${e.code()})")
        } catch (e: IOException) {
            Log.e(TAG, "Feedback submit network error: ${e.message}")
            Resource.Error("Sunucuya bağlanılamadı.")
        } catch (e: Exception) {
            Log.e(TAG, "Feedback submit failed: ${e.message}")
            Resource.Error("Geri bildirim gönderilemedi.")
        }
    }
}
