package com.psikochat.app.data.api
import com.psikochat.app.data.model.*
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Query

interface PsikoApi {
    @POST("/login")
    suspend fun login(@Body request: LoginRequest): AuthResponse
    
    @POST("/register")
    suspend fun register(@Body request: RegisterRequest): RegisterResponse

    @POST("/predict")
    suspend fun sendMessage(@Body request: ChatRequest): ChatResponse

    @GET("/history")
    suspend fun getHistory(): List<HistoryItem>

    @GET("/analytics/emotions/timeline")
    suspend fun getEmotionTimeline(@Query("days") days: Int): List<EmotionTimelineItem>

    @GET("/analytics/emotions/summary")
    suspend fun getEmotionSummary(@Query("days") days: Int): EmotionSummaryResponse

    @GET("/analytics/insights")
    suspend fun getInsights(@Query("days") days: Int): List<BehavioralInsight>

    @GET("/analytics/interventions")
    suspend fun getInterventions(@Query("days") days: Int): List<SmartIntervention>

    @GET("/analytics/reports/wellness")
    suspend fun getWellnessReport(
        @Query("period") period: String,
        @Query("days") days: Int
    ): WellnessReportResponse

    @GET("/analytics/reflections")
    suspend fun getReflections(
        @Query("period") period: String
    ): ReflectionResponse
}
