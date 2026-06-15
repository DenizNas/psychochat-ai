package com.psikochat.app.data.model
import com.google.gson.annotations.SerializedName

data class LoginRequest(
    @SerializedName("email") val email: String,
    @SerializedName("password") val password: String
)
data class RegisterRequest(
    @SerializedName("full_name") val fullName: String,
    @SerializedName("email") val email: String,
    @SerializedName("password") val password: String,
    @SerializedName("role") val role: String = "user",
    @SerializedName("title") val title: String? = null,
    @SerializedName("specialty") val specialty: String? = null,
    @SerializedName("bio") val bio: String? = null
)
data class AuthResponse(
    @SerializedName("access_token") val access_token: String,
    @SerializedName("token_type") val token_type: String,
    @SerializedName("username") val username: String,
    @SerializedName("email") val email: String? = null,
    @SerializedName("full_name") val fullName: String? = null,
    @SerializedName("role") val role: String? = "user"
)
data class RegisterResponse(
    @SerializedName("message") val message: String
)
data class ChatRequest(
    @SerializedName("text") val text: String, 
    @SerializedName("language") val language: String = "tr",
    @SerializedName("conversation_id") val conversationId: String? = null
)
data class ChatResponse(
    @SerializedName("emotion") val emotion: String, 
    @SerializedName("risk") val risk: String, 
    @SerializedName("response") val response: String, 
    @SerializedName("emergency_contact") val emergencyContact: String?,
    @SerializedName("is_crisis") val isCrisis: Boolean? = null,
    @SerializedName("crisis_level") val crisisLevel: String? = null,
    @SerializedName("show_emergency_support") val showEmergencySupport: Boolean? = null,
    @SerializedName("emergency_phone") val emergencyPhone: String? = null,
    @SerializedName("emergency_title") val emergencyTitle: String? = null,
    @SerializedName("emergency_message") val emergencyMessage: String? = null
)
data class HistoryItem(
    @SerializedName("id") val id: Int? = null,
    @SerializedName("role") val role: String, 
    @SerializedName("text") val text: String,
    @SerializedName("timestamp") val timestamp: String? = null,
    val state: String = "synced", // "synced", "pending", "failed"
    val conversationId: String = ""
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
    @SerializedName("updated_at") val updatedAt: String,
    @SerializedName("email") val email: String? = null,
    @SerializedName("full_name") val fullName: String? = null,
    @SerializedName("role") val role: String? = "user",
    @SerializedName("title") val title: String? = null,
    @SerializedName("specialty") val specialty: String? = null,
    @SerializedName("status") val status: String? = null
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
    class Error<T>(message: String, data: T? = null, val isPremiumRequired: Boolean = false) : Resource<T>(data, message)
    class Loading<T>(data: T? = null) : Resource<T>(data)
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

data class SubscriptionPlanDto(
    @SerializedName("id") val id: String,
    @SerializedName("name") val name: String,
    @SerializedName("price_lira") val price_lira: Double,
    @SerializedName("billing_interval") val billing_interval: String,
    @SerializedName("description") val description: String,
    @SerializedName("is_active") val is_active: Boolean
)

data class SubscriptionStatusDto(
    @SerializedName("has_premium") val has_premium: Boolean,
    @SerializedName("plan_name") val plan_name: String?,
    @SerializedName("status") val status: String?,
    @SerializedName("current_period_end") val current_period_end: String?,
    @SerializedName("cancel_at_period_end") val cancel_at_period_end: Boolean?
)

data class CheckoutRequestDto(
    @SerializedName("plan_id") val plan_id: String
)

data class CheckoutResponseDto(
    @SerializedName("checkout_url") val checkout_url: String,
    @SerializedName("transaction_id") val transaction_id: String,
    @SerializedName("status") val status: String
)

data class PaymentHistoryDto(
    @SerializedName("transaction_id") val transaction_id: String,
    @SerializedName("amount") val amount: Double,
    @SerializedName("currency") val currency: String,
    @SerializedName("status") val status: String,
    @SerializedName("created_at") val created_at: String
)

data class WellnessPlanGoal(
    @SerializedName("type") val type: String,
    @SerializedName("priority") val priority: String,
    @SerializedName("scheduled_for") val scheduledFor: String,
    @SerializedName("status") val status: String,
    @SerializedName("title") val title: String,
    @SerializedName("description") val description: String
)

data class WellnessPlanResponse(
    @SerializedName("today_focus") val todayFocus: String,
    @SerializedName("daily_goals") val dailyGoals: List<WellnessPlanGoal>,
    @SerializedName("emotional_trend_summary") val emotionalTrendSummary: String,
    @SerializedName("ai_wellness_summary") val aiWellnessSummary: String
)

data class PsychologistDto(
    @SerializedName("id") val id: Int? = null,
    @SerializedName("username") val username: String,
    @SerializedName("email") val email: String?,
    @SerializedName("full_name") val fullName: String?,
    @SerializedName("title") val title: String,
    @SerializedName("specialty") val specialty: String,
    @SerializedName("bio") val bio: String,
    @SerializedName("status") val status: String
)

data class CreateAppointmentRequest(
    @SerializedName("psychologist_username") val psychologistUsername: String,
    @SerializedName("appointment_date") val appointmentDate: String,
    @SerializedName("appointment_time") val appointmentTime: String
)

data class AppointmentDto(
    @SerializedName("id") val id: Int,
    @SerializedName("user_id") val userId: Int,
    @SerializedName("psychologist_id") val psychologistId: Int,
    @SerializedName("appointment_date") val appointmentDate: String,
    @SerializedName("appointment_time") val appointmentTime: String,
    @SerializedName("status") val status: String,
    @SerializedName("created_at") val createdAt: String? = null,
    @SerializedName("psychologist_name") val psychologistName: String? = null,
    @SerializedName("psychologist_specialty") val psychologistSpecialty: String? = null,
    @SerializedName("patient_name") val patientName: String? = null,
    @SerializedName("patient_username") val patientUsername: String? = null,
    @SerializedName("patient_email") val patientEmail: String? = null
)

data class AvailabilityDto(
    @SerializedName("id") val id: Int,
    @SerializedName("psychologist_id") val psychologistId: Int,
    @SerializedName("day_of_week") val dayOfWeek: Int,
    @SerializedName("start_time") val startTime: String,
    @SerializedName("end_time") val endTime: String,
    @SerializedName("slot_duration_minutes") val slotDurationMinutes: Int,
    @SerializedName("is_active") val isActive: Boolean,
    @SerializedName("created_at") val createdAt: String? = null,
    @SerializedName("updated_at") val updatedAt: String? = null
)

data class CreateAvailabilityRequest(
    @SerializedName("day_of_week") val dayOfWeek: Int,
    @SerializedName("start_time") val startTime: String,
    @SerializedName("end_time") val endTime: String,
    @SerializedName("slot_duration_minutes") val slotDurationMinutes: Int
)

data class UpdateAvailabilityRequest(
    @SerializedName("day_of_week") val dayOfWeek: Int? = null,
    @SerializedName("start_time") val startTime: String? = null,
    @SerializedName("end_time") val endTime: String? = null,
    @SerializedName("slot_duration_minutes") val slotDurationMinutes: Int? = null,
    @SerializedName("is_active") val isActive: Boolean? = null
)

data class AvailableSlotDto(
    @SerializedName("time") val time: String,
    @SerializedName("available") val available: Boolean
)

data class AvailableSlotsResponse(
    @SerializedName("psychologist_id") val psychologistId: Int,
    @SerializedName("date") val date: String,
    @SerializedName("slots") val slots: List<AvailableSlotDto>
)

data class AdminPsychologist(
    @SerializedName("username") val username: String,
    @SerializedName("full_name") val fullName: String?,
    @SerializedName("email") val email: String?,
    @SerializedName("title") val title: String,
    @SerializedName("specialty") val specialty: String,
    @SerializedName("status") val status: String,
    @SerializedName("created_at") val createdAt: String
)

data class PasswordResetRequest(
    @SerializedName("email") val email: String
)

data class PasswordResetVerifyRequest(
    @SerializedName("email") val email: String,
    @SerializedName("code") val code: String
)

data class PasswordResetVerifyResponse(
    @SerializedName("reset_token") val reset_token: String
)

data class PasswordResetCompleteRequest(
    @SerializedName("reset_token") val reset_token: String,
    @SerializedName("new_password") val new_password: String
)



