package com.psikochat.app.data.model
import com.google.gson.annotations.SerializedName

data class LoginRequest(val username: String, val password: String)
data class RegisterRequest(val username: String, val password: String)
data class AuthResponse(val access_token: String, val token_type: String, val username: String)
data class RegisterResponse(val message: String)
data class ChatRequest(val text: String, val language: String = "tr")
data class ChatResponse(val emotion: String, val risk: String, val response: String, val emergency_contact: String?)
data class HistoryItem(val role: String, val text: String)

data class EmotionTimelineItem(
    val id: Int,
    val message_id: String,
    val emotion: String,
    val risk: String,
    val created_at: String,
    val source: String
)

data class DailyTrendItem(
    val date: String,
    val emotions: Map<String, Int>,
    val total_count: Int
)

data class EmotionSummaryResponse(
    val total_messages: Int,
    val emotion_distribution: Map<String, Int>,
    val dominant_emotion: String?,
    val crisis_count: Int,
    val daily_trend: List<DailyTrendItem>
)

data class BehavioralInsight(
    val type: String,
    val severity: String,
    val confidence: Double,
    val title: String,
    val description: String,
    val created_at: String
)

data class SmartIntervention(
    val type: String,
    val severity: String,
    val title: String,
    val description: String,
    val created_at: String
)

data class WellnessReportResponse(
    val period: String,
    val summary_title: String,
    val summary_text: String,
    val dominant_emotion: String,
    val total_messages: Int,
    val crisis_count: Int,
    val highlights: List<String>,
    val suggestions: List<String>,
    val created_at: String
)

data class ReflectionResponse(
    val period: String,
    val reflection_title: String,
    val reflection_text: String,
    val tone: String,
    val dominant_emotion: String,
    val generated_from: List<String>,
    val created_at: String
)

sealed class Resource<T>(val data: T? = null, val message: String? = null) {
    class Success<T>(data: T) : Resource<T>(data)
    class Error<T>(message: String, data: T? = null) : Resource<T>(data, message)
    class Loading<T> : Resource<T>()
}
