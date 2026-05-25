package com.psikochat.app.data.api
import com.psikochat.app.data.model.*
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.PUT
import retrofit2.http.DELETE
import retrofit2.http.Multipart
import retrofit2.http.Part
import okhttp3.MultipartBody

import retrofit2.http.HTTP

interface PsikoApi {
    @POST("/login")
    suspend fun login(@Body request: LoginRequest): AuthResponse
    
    @POST("/register")
    suspend fun register(@Body request: RegisterRequest): RegisterResponse

    @POST("/predict")
    suspend fun sendMessage(
        @Body request: ChatRequest,
        @retrofit2.http.Header("X-Idempotency-Key") idempotencyKey: String? = null
    ): ChatResponse

    @GET("/history")
    suspend fun getHistory(): List<HistoryItem>

    @GET("/profile")
    suspend fun getProfile(): ProfileResponse

    @PUT("/profile")
    suspend fun updateProfile(@Body request: UpdateProfileRequest): ProfileResponse

    @Multipart
    @POST("/profile/photo")
    suspend fun uploadProfilePhoto(@Part file: MultipartBody.Part): ProfileResponse

    @GET("/analytics/scheduled-interventions")
    suspend fun getScheduledInterventions(): List<ScheduledIntervention>

    @POST("/analytics/scheduled-interventions/refresh")
    suspend fun refreshScheduledInterventions(): List<ScheduledIntervention>

    @GET("/analytics/reports/wellness")
    suspend fun getWellnessReport(
        @retrofit2.http.Query("period") period: String,
        @retrofit2.http.Query("days") days: Int
    ): WellnessReport

    @GET("/journal/mood")
    suspend fun getMoodJournals(
        @retrofit2.http.Query("days") days: Int
    ): List<MoodJournalEntry>

    @POST("/journal/mood")
    suspend fun createMoodJournal(
        @retrofit2.http.Body request: CreateMoodJournalRequest,
        @retrofit2.http.Header("X-Idempotency-Key") idempotencyKey: String? = null
    ): MoodJournalEntry

    @DELETE("/journal/mood/{journal_id}")
    suspend fun deleteMoodJournal(
        @retrofit2.http.Path("journal_id") journalId: Int
    ): Map<String, String>

    @GET("/notifications")
    suspend fun getNotifications(): List<NotificationEvent>

    @POST("/notifications/refresh")
    suspend fun refreshNotifications(): List<NotificationEvent>

    @POST("/notifications/{notification_id}/mark-delivered")
    suspend fun markNotificationDelivered(
        @retrofit2.http.Path("notification_id") notificationId: Int
    ): Map<String, String>

    @GET("/analytics/dashboard")
    suspend fun getWellnessDashboard(
        @retrofit2.http.Query("days") days: Int
    ): WellnessDashboardResponse

    @GET("/memory")
    suspend fun getMemories(): List<UserMemory>

    @DELETE("/memory/{memory_id}")
    suspend fun deleteMemory(@retrofit2.http.Path("memory_id") memoryId: Int): Map<String, String>

    @POST("/memory/refresh")
    suspend fun refreshMemories(): MemoryConsolidationResponse

    @GET("/privacy/consent")
    suspend fun getPrivacyConsent(): UserConsentResponse

    @POST("/privacy/consent")
    suspend fun updatePrivacyConsent(@Body request: UpdateConsentRequest): UserConsentResponse

    @GET("/privacy/export")
    suspend fun exportPrivacyData(): Map<String, @JvmSuppressWildcards Any>

    @HTTP(method = "DELETE", path = "/privacy/delete", hasBody = true)
    suspend fun deletePrivacyAccount(@Body request: DeleteDataRequest): Map<String, String>

    // ── Faz 10 Prompt 7: Recommendation Engine Endpoints ──────────────────

    @GET("/analytics/recommendations")
    suspend fun getRecommendations(): List<WellnessRecommendation>

    @POST("/analytics/recommendations/refresh")
    suspend fun refreshRecommendations(): RecommendationRefreshResponse

    @POST("/analytics/recommendations/{rec_id}/feedback")
    suspend fun submitRecommendationFeedback(
        @retrofit2.http.Path("rec_id") recId: String,
        @Body request: RecommendationFeedbackRequest
    ): Map<String, String>
}
