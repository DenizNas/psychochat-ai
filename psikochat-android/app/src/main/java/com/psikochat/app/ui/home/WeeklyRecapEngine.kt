package com.psikochat.app.ui.home

import com.psikochat.app.data.local.entity.CachedAppointment
import com.psikochat.app.data.local.entity.CachedChatMessage
import com.psikochat.app.data.local.entity.CachedMoodJournal
import com.psikochat.app.data.local.entity.ScoreSnapshot
import java.text.SimpleDateFormat
import java.util.*

/**
 * Lightweight UI model for the weekly wellness recap.
 * All fields are derived from real local data only.
 */
data class WeeklyRecapSummary(
    val totalMessagesThisWeek: Int,
    val moodEntriesThisWeek: Int,
    val appointmentsThisWeek: Int,
    val activeStreakDays: Int,
    val unlockedAchievementsCount: Int,
    val wellnessScoreDeltaText: String,
    val dominantMoodText: String,
    val motivationalMessage: String,
    val hasAnyActivity: Boolean
)

/**
 * WeeklyRecapEngine — pure local calculator.
 * Uses last 7 calendar days from UTC timestamps.
 * No fake values are ever generated.
 */
object WeeklyRecapEngine {

    private val utcSdf = SimpleDateFormat("yyyy-MM-dd", Locale.getDefault()).apply {
        timeZone = TimeZone.getTimeZone("UTC")
    }

    /** Returns a set of date strings for the last 7 days inclusive (today + 6 days back), UTC. */
    private fun last7DaySet(): Set<String> {
        val cal = Calendar.getInstance(TimeZone.getTimeZone("UTC"))
        val dates = mutableSetOf<String>()
        repeat(7) {
            dates.add(utcSdf.format(cal.time))
            cal.add(Calendar.DAY_OF_YEAR, -1)
        }
        return dates
    }

    private fun extractDateStr(timestamp: String): String? {
        return try {
            if (timestamp.length >= 10) timestamp.substring(0, 10) else null
        } catch (e: Exception) {
            null
        }
    }

    fun compute(
        messages: List<CachedChatMessage>,
        moods: List<CachedMoodJournal>,
        appointments: List<CachedAppointment>,
        snapshots: List<ScoreSnapshot>,
        streak: StreakSummary,
        achievements: List<AchievementItem>
    ): WeeklyRecapSummary {

        val last7 = last7DaySet()

        // --- Counts for this week ---
        val weekMessages = messages.count { msg ->
            extractDateStr(msg.timestamp)?.let { last7.contains(it) } ?: false
        }

        val weekMoods = moods.count { mood ->
            extractDateStr(mood.createdAt)?.let { last7.contains(it) } ?: false
        }

        val weekAppointments = appointments.count { appt ->
            extractDateStr(appt.createdAt)?.let { last7.contains(it) } ?: false
        }

        // --- Wellness score delta ---
        val scoreDeltaText = computeScoreDelta(snapshots, last7)

        // --- Dominant mood ---
        val dominantMood = computeDominantMood(moods, last7)

        // --- Achievement count ---
        val unlockedCount = achievements.count { it.unlocked }

        // --- Any activity this week? ---
        val hasActivity = weekMessages > 0 || weekMoods > 0 || weekAppointments > 0

        // --- Motivational message ---
        val motivation = buildMotivation(weekMessages, weekMoods, streak.activeStreakDays, hasActivity)

        return WeeklyRecapSummary(
            totalMessagesThisWeek = weekMessages,
            moodEntriesThisWeek = weekMoods,
            appointmentsThisWeek = weekAppointments,
            activeStreakDays = streak.activeStreakDays,
            unlockedAchievementsCount = unlockedCount,
            wellnessScoreDeltaText = scoreDeltaText,
            dominantMoodText = dominantMood,
            motivationalMessage = motivation,
            hasAnyActivity = hasActivity
        )
    }

    private fun computeScoreDelta(snapshots: List<ScoreSnapshot>, last7: Set<String>): String {
        if (snapshots.isEmpty()) return "Henüz yeterli veri yok"

        val weekSnaps = snapshots
            .filter { last7.contains(it.date) }
            .sortedBy { it.date }

        if (weekSnaps.size < 2) return "Henüz yeterli veri yok"

        val oldest = weekSnaps.first().score
        val newest = weekSnaps.last().score
        val delta = newest - oldest
        return when {
            delta > 0 -> "+$delta puan gelişim 📈"
            delta < 0 -> "$delta puan düşüş 📉"
            else -> "Değişim yok — istikrarlı 📊"
        }
    }

    private fun computeDominantMood(moods: List<CachedMoodJournal>, last7: Set<String>): String {
        val weekMoods = moods.filter { mood ->
            extractDateStr(mood.createdAt)?.let { last7.contains(it) } ?: false
        }
        if (weekMoods.isEmpty()) return "Bu hafta kayıt yok"

        val grouped = weekMoods.groupBy { it.mood.lowercase(Locale.getDefault()) }
        val dominant = grouped.maxByOrNull { it.value.size }?.key ?: return "Çeşitli"
        val count = grouped[dominant]?.size ?: 0

        val displayMood = dominant.replaceFirstChar { it.uppercase() }
        return "$displayMood ($count kayıt)"
    }

    private fun buildMotivation(
        messages: Int,
        moods: Int,
        streak: Int,
        hasActivity: Boolean
    ): String {
        return when {
            !hasActivity ->
                "Bu hafta henüz bir adım atmadın — yarın yeni bir başlangıç için her şey hazır!"
            streak >= 7 ->
                "🔥 Muhteşem! 7+ günlük serin devam ediyor. Bu istikrar zihinsel sağlığının temeli."
            streak >= 3 ->
                "💪 Harika bir ritm yakaladın! Düzenli aktivite wellness'ının anahtarı."
            messages >= 10 && moods >= 3 ->
                "✨ Bu hafta hem sohbet hem de duygu kaydıyla dengeli bir yolculuk geçirdin."
            messages >= 5 ->
                "💬 Sohbet alışkanlığın güçleniyor. Ruh hali kaydı ekleyerek içgörülerini derinleştirebilirsin."
            moods >= 3 ->
                "📝 Duygu günlüğü alışkanlığın gelişiyor. Bir sohbetle haftayı tamamla!"
            else ->
                "Her küçük adım önemli. Bu haftaki çabaların wellness yolculuğunun parçası."
        }
    }
}
