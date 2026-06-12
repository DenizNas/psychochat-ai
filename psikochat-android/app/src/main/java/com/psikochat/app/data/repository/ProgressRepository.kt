package com.psikochat.app.data.repository

import com.psikochat.app.data.local.dao.ScoreSnapshotDao
import com.psikochat.app.data.local.entity.ScoreSnapshot
import kotlinx.coroutines.flow.Flow
import java.text.SimpleDateFormat
import java.util.*

class ProgressRepository(private val dao: ScoreSnapshotDao) {

    /**
     * Enforces the constraint score >= 0 && score <= 100 before saving a single daily snapshot.
     */
    suspend fun saveDailyScoreSnapshot(score: Int) {
        if (score < 0 || score > 100) return // Boundary protection limit
        
        val todayStr = SimpleDateFormat("yyyy-MM-dd", Locale.getDefault()).apply {
            timeZone = TimeZone.getTimeZone("UTC")
        }.format(Date())

        val exists = dao.existsForDate(todayStr)
        if (!exists) {
            val snapshot = ScoreSnapshot(
                date = todayStr,
                score = score,
                createdAt = System.currentTimeMillis()
            )
            dao.insertSnapshot(snapshot)
        }
    }

    fun loadLast7Days(): Flow<List<ScoreSnapshot>> = dao.getLast7Days()

    fun loadLast30Days(): Flow<List<ScoreSnapshot>> = dao.getLast30Days()

    /**
     * Calculates wellness score delta progression over snapshots (sorted descending by date).
     * Compares the latest score (index 0) against the previous score (index 1).
     * Returns formatted localization strings (e.g., "+5 gelişim", "-2 düşüş", "Değişim yok").
     */
    fun calculateScoreDelta(snapshots: List<ScoreSnapshot>): String {
        if (snapshots.size < 2) return "Değişim yok"
        val current = snapshots[0].score
        val previous = snapshots[1].score
        val diff = current - previous
        return when {
            diff > 0 -> "+$diff gelişim"
            diff < 0 -> "$diff düşüş"
            else -> "Değişim yok"
        }
    }
}
