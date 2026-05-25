package com.psikochat.app.data.model
import com.google.gson.annotations.SerializedName

data class LoginRequest(
    @SerializedName("username") val username: String,
    @SerializedName("password") val password: String
)
data class RegisterRequest(
    @SerializedName("username") val username: String,
    @SerializedName("password") val password: String
)
data class AuthResponse(
    @SerializedName("access_token") val access_token: String,
    @SerializedName("token_type") val token_type: String,
    @SerializedName("username") val username: String
)
data class RegisterResponse(
    @SerializedName("message") val message: String
)
data class ChatRequest(
    @SerializedName("text") val text: String, 
    @SerializedName("language") val language: String = "tr"
)
data class ChatResponse(
    @SerializedName("emotion") val emotion: String, 
    @SerializedName("risk") val risk: String, 
    @SerializedName("response") val response: String, 
    @SerializedName("emergency_contact") val emergencyContact: String?
)
data class HistoryItem(
    @SerializedName("id") val id: Int? = null,
    @SerializedName("role") val role: String, 
    @SerializedName("text") val text: String,
    @SerializedName("timestamp") val timestamp: String? = null,
    val state: String = "synced" // "synced", "pending", "failed"
)

data class ProfileResponse(
    @SerializedName("username") val username: String,
    @SerializedName("display_name") val displayName: String?,
    @SerializedName("bio") val bio: String?,
    @SerializedName("profile_photo_url") val profilePhotoUrl: String?,
    @SerializedName("preferred_language") val preferredLanguage: String,
    @SerializedName("response_style") val responseStyle: String,
    @SerializedName("theme_preference") val themePreference: String,
    @SerializedName("notifications_enabled") val notificationsEnabled: Boolean,
    @SerializedName("privacy_mode") val privacyMode: Boolean,
    @SerializedName("answer_length_preference") val answerLengthPreference: String,
    @SerializedName("created_at") val createdAt: String,
    @SerializedName("updated_at") val updatedAt: String
)

data class UpdateProfileRequest(
    @SerializedName("display_name") val displayName: String? = null,
    @SerializedName("bio") val bio: String? = null,
    @SerializedName("preferred_language") val preferredLanguage: String? = null,
    @SerializedName("response_style") val responseStyle: String? = null,
    @SerializedName("theme_preference") val themePreference: String? = null,
    @SerializedName("notifications_enabled") val notificationsEnabled: Boolean? = null,
    @SerializedName("privacy_mode") val privacyMode: Boolean? = null,
    @SerializedName("answer_length_preference") val answerLengthPreference: String? = null
)

data class ScheduledIntervention(
    @SerializedName("type") val type: String,
    @SerializedName("priority") val priority: String,
    @SerializedName("scheduled_for") val scheduledFor: String,
    @SerializedName("status") val status: String,
    @SerializedName("title") val title: String,
    @SerializedName("description") val description: String
)

data class WellnessReport(
    @SerializedName("period") val period: String,
    @SerializedName("summary_title") val summaryTitle: String,
    @SerializedName("summary_text") val summaryText: String,
    @SerializedName("dominant_emotion") val dominantEmotion: String,
    @SerializedName("total_messages") val totalMessages: Int,
    @SerializedName("crisis_count") val crisisCount: Int,
    @SerializedName("highlights") val highlights: List<String>,
    @SerializedName("suggestions") val suggestions: List<String>,
    @SerializedName("created_at") val createdAt: String,
    var lastUpdated: String? = null
)

data class CreateMoodJournalRequest(
    @SerializedName("mood") val mood: String,
    @SerializedName("intensity") val intensity: Int,
    @SerializedName("note") val note: String?
)

data class MoodJournalEntry(
    @SerializedName("id") val id: Int,
    @SerializedName("user_id") val userId: String,
    @SerializedName("mood") val mood: String,
    @SerializedName("intensity") val intensity: Int,
    @SerializedName("note") val note: String?,
    @SerializedName("created_at") val createdAt: String,
    @SerializedName("updated_at") val updatedAt: String,
    @SerializedName("source") val source: String
)

data class NotificationEvent(
    @SerializedName("id") val id: Int,
    @SerializedName("user_id") val userId: String,
    @SerializedName("notification_type") val notificationType: String,
    @SerializedName("title") val title: String,
    @SerializedName("body") val body: String,
    @SerializedName("scheduled_for") val scheduledFor: String,
    @SerializedName("status") val status: String,
    @SerializedName("created_at") val createdAt: String,
    @SerializedName("delivered_at") val deliveredAt: String?,
    @SerializedName("source") val source: String
)

sealed class Resource<T>(val data: T? = null, val message: String? = null) {
    class Success<T>(data: T) : Resource<T>(data)
    class Error<T>(message: String, data: T? = null) : Resource<T>(data, message)
    class Loading<T> : Resource<T>()
}

data class BehavioralInsight(
    @SerializedName("type") val type: String,
    @SerializedName("severity") val severity: String,
    @SerializedName("confidence") val confidence: Float,
    @SerializedName("title") val title: String,
    @SerializedName("description") val description: String,
    @SerializedName("created_at") val createdAt: String
)

data class SmartIntervention(
    @SerializedName("type") val type: String,
    @SerializedName("severity") val severity: String,
    @SerializedName("title") val title: String,
    @SerializedName("description") val description: String,
    @SerializedName("created_at") val createdAt: String
)

data class ReflectionResponse(
    @SerializedName("period") val period: String,
    @SerializedName("reflection_title") val reflectionTitle: String,
    @SerializedName("reflection_text") val reflectionText: String,
    @SerializedName("tone") val tone: String,
    @SerializedName("dominant_emotion") val dominantEmotion: String,
    @SerializedName("generated_from") val generatedFrom: List<String>,
    @SerializedName("created_at") val createdAt: String
)

data class DailyTrendItem(
    @SerializedName("date") val date: String,
    @SerializedName("emotions") val emotions: Map<String, Int>,
    @SerializedName("total_count") val totalCount: Int
)

data class DashboardOverview(
    @SerializedName("total_messages") val totalMessages: Int,
    @SerializedName("dominant_emotion") val dominantEmotion: String,
    @SerializedName("crisis_count") val crisisCount: Int,
    @SerializedName("journal_count") val journalCount: Int,
    @SerializedName("scheduled_intervention_count") val scheduledInterventionCount: Int,
    @SerializedName("notification_count") val notificationCount: Int
)

data class DashboardScore(
    @SerializedName("score") val score: Int?,
    @SerializedName("label") val label: String,
    @SerializedName("description") val description: String
)

data class DashboardSections(
    @SerializedName("emotion_distribution") val emotionDistribution: Map<String, Int>,
    @SerializedName("daily_trend") val dailyTrend: List<DailyTrendItem>,
    @SerializedName("top_insights") val topInsights: List<BehavioralInsight>,
    @SerializedName("active_interventions") val activeInterventions: List<SmartIntervention>,
    @SerializedName("latest_reflection") val latestReflection: ReflectionResponse?,
    @SerializedName("latest_report") val latestReport: WellnessReport?
)

data class WellnessDashboardResponse(
    @SerializedName("days") val days: Int,
    @SerializedName("overview") val overview: DashboardOverview,
    @SerializedName("wellness_score") val wellnessScore: DashboardScore,
    @SerializedName("sections") val sections: DashboardSections,
    @SerializedName("created_at") val createdAt: String,
    var lastUpdated: String? = null
)

data class UserMemory(
    @SerializedName("id") val id: Int,
    @SerializedName("memory_type") val memoryType: String,
    @SerializedName("memory_text") val memoryText: String,
    @SerializedName("confidence") val confidence: Float,
    @SerializedName("sensitivity") val sensitivity: String,
    @SerializedName("last_reinforced_at") val lastReinforcedAt: String?
)

data class MemoryConsolidationResponse(
    @SerializedName("status") val status: String,
    @SerializedName("processed") val processed: Int,
    @SerializedName("merged") val merged: Int,
    @SerializedName("decayed") val decayed: Int,
    @SerializedName("contradicted") val contradicted: Int
)

data class UserConsentResponse(
    @SerializedName("privacy_policy_version") val privacyPolicyVersion: String,
    @SerializedName("terms_version") val termsVersion: String,
    @SerializedName("analytics_consent") val analyticsConsent: Boolean,
    @SerializedName("wellness_insights_consent") val wellnessInsightsConsent: Boolean,
    @SerializedName("notifications_consent") val notificationsConsent: Boolean,
    @SerializedName("ai_processing_consent") val aiProcessingConsent: Boolean
)

data class UpdateConsentRequest(
    @SerializedName("analytics_consent") val analyticsConsent: Boolean,
    @SerializedName("wellness_insights_consent") val wellnessInsightsConsent: Boolean,
    @SerializedName("notifications_consent") val notificationsConsent: Boolean,
    @SerializedName("ai_processing_consent") val aiProcessingConsent: Boolean
)

data class DeleteDataRequest(
    @SerializedName("confirm") val confirm: String
)

// ── Faz 10 Prompt 7: Recommendation Engine Models ───────────────────────────

data class RecommendationAction(
    @SerializedName("label") val label: String,
    @SerializedName("action_type") val actionType: String
)

data class WellnessRecommendation(
    @SerializedName("id") val id: String,
    @SerializedName("recommendation_type") val recommendationType: String,
    @SerializedName("title") val title: String,
    @SerializedName("description") val description: String,
    @SerializedName("priority") val priority: String,           // "low" | "medium" | "high"
    @SerializedName("confidence") val confidence: Float,
    @SerializedName("reason") val reason: String,
    @SerializedName("actions") val actions: List<RecommendationAction>,
    @SerializedName("status") val status: String,               // "active" | "dismissed" | "completed" | "expired"
    @SerializedName("created_at") val createdAt: String?,
    @SerializedName("expires_at") val expiresAt: String?,
    @SerializedName("source") val source: String
)

data class RecommendationRefreshResponse(
    @SerializedName("generated") val generated: Int,
    @SerializedName("recommendations") val recommendations: List<WellnessRecommendation>,
    @SerializedName("privacy_mode") val privacyMode: Boolean,
    @SerializedName("wellness_insights_consent") val wellnessInsightsConsent: Boolean
)

data class RecommendationFeedbackRequest(
    @SerializedName("feedback") val feedback: String  // "helpful" | "not_helpful" | "dismissed"
)
