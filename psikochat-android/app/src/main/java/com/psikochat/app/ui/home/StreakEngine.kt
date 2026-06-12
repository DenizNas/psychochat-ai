package com.psikochat.app.ui.home

import com.psikochat.app.data.local.entity.CachedChatMessage
import com.psikochat.app.data.local.entity.CachedMoodJournal
import java.text.SimpleDateFormat
import java.util.*

data class StreakSummary(
    val activeStreakDays: Int,
    val chatStreakDays: Int,
    val moodStreakDays: Int,
    val longestStreakDays: Int,
    val label: String,
    val encouragementText: String
)

object StreakEngine {

    private fun parseDate(dateStr: String): Date? {
        return try {
            SimpleDateFormat("yyyy-MM-dd", Locale.getDefault()).apply {
                timeZone = TimeZone.getTimeZone("UTC")
            }.parse(dateStr)
        } catch (e: Exception) {
            null
        }
    }

    private fun diffInDays(d1: Date, d2: Date): Long {
        val cal1 = Calendar.getInstance(TimeZone.getTimeZone("UTC")).apply {
            time = d1
            set(Calendar.HOUR_OF_DAY, 0)
            set(Calendar.MINUTE, 0)
            set(Calendar.SECOND, 0)
            set(Calendar.MILLISECOND, 0)
        }
        val cal2 = Calendar.getInstance(TimeZone.getTimeZone("UTC")).apply {
            time = d2
            set(Calendar.HOUR_OF_DAY, 0)
            set(Calendar.MINUTE, 0)
            set(Calendar.SECOND, 0)
            set(Calendar.MILLISECOND, 0)
        }
        val diffMs = cal2.timeInMillis - cal1.timeInMillis
        return diffMs / (1000 * 60 * 60 * 24)
    }

    fun calculateLongestStreak(dates: Set<String>): Int {
        if (dates.isEmpty()) return 0
        val sortedDates = dates.mapNotNull { parseDate(it) }.sorted()
        if (sortedDates.isEmpty()) return 0
        
        var longest = 1
        var current = 1
        for (i in 0 until sortedDates.size - 1) {
            val diff = diffInDays(sortedDates[i], sortedDates[i + 1])
            if (diff == 1L) {
                current++
            } else if (diff > 1L) {
                if (current > longest) {
                    longest = current
                }
                current = 1
            }
        }
        return maxOf(longest, current)
    }

    fun calculateCurrentActiveStreak(dates: Set<String>, todayStr: String, yesterdayStr: String): Int {
        if (dates.isEmpty()) return 0
        val sortedDates = dates.sortedDescending()
        val latestActiveDate = sortedDates.first()
        if (latestActiveDate != todayStr && latestActiveDate != yesterdayStr) {
            return 0
        }
        
        var streakCount = 1
        val currentCal = Calendar.getInstance(TimeZone.getTimeZone("UTC")).apply {
            val parts = latestActiveDate.split("-")
            if (parts.size == 3) {
                set(Calendar.YEAR, parts[0].toInt())
                set(Calendar.MONTH, parts[1].toInt() - 1)
                set(Calendar.DAY_OF_MONTH, parts[2].toInt())
            }
        }
        
        val formatter = SimpleDateFormat("yyyy-MM-dd", Locale.getDefault()).apply {
            timeZone = TimeZone.getTimeZone("UTC")
        }
        
        while (true) {
            currentCal.add(Calendar.DAY_OF_YEAR, -1)
            val checkStr = formatter.format(currentCal.time)
            if (dates.contains(checkStr)) {
                streakCount++
            } else {
                break
            }
        }
        
        return streakCount
    }

    fun computeStreakSummary(
        messages: List<CachedChatMessage>,
        moods: List<CachedMoodJournal>
    ): StreakSummary {
        val chatDates = mutableSetOf<String>()
        messages.forEach { msg ->
            try {
                if (msg.timestamp.length >= 10) {
                    chatDates.add(msg.timestamp.substring(0, 10))
                }
            } catch (e: Exception) {}
        }

        val moodDates = mutableSetOf<String>()
        moods.forEach { mood ->
            try {
                if (mood.createdAt.length >= 10) {
                    moodDates.add(mood.createdAt.substring(0, 10))
                }
            } catch (e: Exception) {}
        }

        val activeDates = chatDates + moodDates

        val todayStr = SimpleDateFormat("yyyy-MM-dd", Locale.getDefault()).apply {
            timeZone = TimeZone.getTimeZone("UTC")
        }.format(Date())
        
        val yesterdayCalendar = Calendar.getInstance(TimeZone.getTimeZone("UTC")).apply {
            add(Calendar.DAY_OF_YEAR, -1)
        }
        val yesterdayStr = SimpleDateFormat("yyyy-MM-dd", Locale.getDefault()).apply {
            timeZone = TimeZone.getTimeZone("UTC")
        }.format(yesterdayCalendar.time)

        val activeStreak = calculateCurrentActiveStreak(activeDates, todayStr, yesterdayStr)
        val chatStreak = calculateCurrentActiveStreak(chatDates, todayStr, yesterdayStr)
        val moodStreak = calculateCurrentActiveStreak(moodDates, todayStr, yesterdayStr)
        val longestStreak = calculateLongestStreak(activeDates)

        val label = if (activeStreak == 0) {
            "Bugün başladı"
        } else {
            "🔥 $activeStreak Gün"
        }

        val encouragementText = when {
            activeStreak == 0 -> "Bugün küçük bir adım atarak serini başlatabilirsin."
            activeStreak == 1 -> "Harika bir başlangıç! İstikrarını korumak için yarın da devam et."
            activeStreak in 2..4 -> "Süpersin! Zihinsel gelişim yolculuğunda harika ilerliyorsun."
            else -> "Muhteşem istikrar! Kendine yaptığın bu yatırım meyvelerini veriyor."
        }

        return StreakSummary(
            activeStreakDays = activeStreak,
            chatStreakDays = chatStreak,
            moodStreakDays = moodStreak,
            longestStreakDays = longestStreak,
            label = label,
            encouragementText = encouragementText
        )
    }
}
