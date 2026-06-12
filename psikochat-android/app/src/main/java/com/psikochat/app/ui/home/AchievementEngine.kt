package com.psikochat.app.ui.home

import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.ui.graphics.vector.ImageVector
import com.psikochat.app.data.local.entity.CachedAppointment
import com.psikochat.app.data.local.entity.CachedChatMessage
import com.psikochat.app.data.local.entity.CachedMoodJournal

/**
 * Lightweight UI model for a single achievement.
 */
data class AchievementItem(
    val id: String,
    val title: String,
    val description: String,
    val icon: ImageVector,
    val unlocked: Boolean,
    val progressText: String,
    val category: String
)

/**
 * AchievementEngine — pure local calculator, no side effects.
 * All unlock conditions based solely on cached Room data.
 * No fake unlocks are ever returned.
 */
object AchievementEngine {

    /**
     * Compute the full list of 6 achievements from local Room data and StreakSummary.
     *
     * @param messages   All cached chat messages for the current user
     * @param moods      All cached mood journal entries for the current user
     * @param appointments All cached appointments for the current user
     * @param streak     Pre-computed StreakSummary from StreakEngine
     */
    fun computeAchievements(
        messages: List<CachedChatMessage>,
        moods: List<CachedMoodJournal>,
        appointments: List<CachedAppointment>,
        streak: StreakSummary
    ): List<AchievementItem> {
        return listOf(
            // 1. İlk Sohbet
            AchievementItem(
                id = "first_chat",
                title = "İlk Sohbet",
                description = "İlk PsikoChat sohbetini başlattın.",
                icon = Icons.Default.Email,
                unlocked = messages.isNotEmpty(),
                progressText = if (messages.isNotEmpty())
                    "${messages.size} sohbet mesajı"
                else
                    "Henüz hiç sohbet yok — ilk mesajını gönder!",
                category = "Sohbet"
            ),

            // 2. 7 Günlük İstikrar
            AchievementItem(
                id = "week_streak",
                title = "7 Günlük İstikrar",
                description = "7 gün boyunca düzenli zihinsel wellness aktivitesi yaptın.",
                icon = Icons.Default.Star,
                unlocked = streak.activeStreakDays >= 7,
                progressText = if (streak.activeStreakDays >= 7)
                    "🔥 ${streak.activeStreakDays} günlük seri aktif!"
                else
                    "${streak.activeStreakDays} / 7 gün tamamlandı",
                category = "İstikrar"
            ),

            // 3. İlk İçgörü
            // TODO: When AI reflection feature is available, unlock based on
            //       first viewed reflection summary (e.g. ReflectionViewModel data).
            //       Currently kept locked as no safe unlock signal exists locally.
            AchievementItem(
                id = "first_insight",
                title = "İlk İçgörü",
                description = "İlk AI refleksiyon özetini görüntüledin.",
                icon = Icons.Default.Info,
                unlocked = false, // TODO: unlock when reflection history is queryable
                progressText = "Yansımalar bölümünü keşfet",
                category = "Keşif"
            ),

            // 4. İlk Randevu
            AchievementItem(
                id = "first_appointment",
                title = "İlk Randevu",
                description = "İlk uzman randevunu oluşturdun.",
                icon = Icons.Default.DateRange,
                unlocked = appointments.isNotEmpty(),
                progressText = if (appointments.isNotEmpty())
                    "${appointments.size} randevu oluşturuldu"
                else
                    "Uzman desteği için randevu oluştur",
                category = "Destek"
            ),

            // 5. Ruh Hali Dedektifi
            AchievementItem(
                id = "mood_detective",
                title = "Ruh Hali Dedektifi",
                description = "5 ruh hali kaydıyla kendini daha iyi tanımaya başladın.",
                icon = Icons.Default.Edit,
                unlocked = moods.size >= 5,
                progressText = if (moods.size >= 5)
                    "${moods.size} duygu kaydı — harika!"
                else
                    "${moods.size} / 5 ruh hali kaydı",
                category = "Günlük"
            ),

            // 6. Denge Ustası
            AchievementItem(
                id = "balance_master",
                title = "Denge Ustası",
                description = "Sohbet ve günlük alışkanlıklarını dengeli şekilde sürdürdün.",
                icon = Icons.Default.Favorite,
                unlocked = messages.size >= 50 && moods.size >= 10,
                progressText = buildBalanceProgressText(messages.size, moods.size),
                category = "Denge"
            )
        )
    }

    private fun buildBalanceProgressText(messageCount: Int, moodCount: Int): String {
        val chatDone = messageCount >= 50
        val moodDone = moodCount >= 10
        return when {
            chatDone && moodDone -> "Her iki hedefe de ulaştın! 🎉"
            chatDone -> "Sohbet ✓ — Ruh hali: $moodCount / 10"
            moodDone -> "Ruh hali ✓ — Sohbet: $messageCount / 50"
            else -> "Sohbet: $messageCount / 50 · Ruh hali: $moodCount / 10"
        }
    }
}
