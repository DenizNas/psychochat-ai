package com.psikochat.app.ui.notification

import android.content.Context
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import com.psikochat.app.data.local.TokenManager
import kotlinx.coroutines.flow.first

class WeeklyRecapWorker(
    private val context: Context,
    params: WorkerParameters
) : CoroutineWorker(context, params) {

    override suspend fun doWork(): Result {
        val tokenManager = TokenManager(context)
        val enabled = tokenManager.getWeeklyRecapEnabled().first()

        if (enabled) {
            NotificationHelper.showNotification(
                context = context,
                id = 2002, // Unique ID for weekly recap
                title = "Haftalık iyi oluş özetin hazır",
                body = "Bu haftaki duygu ve gelişim özetine göz atabilirsin.",
                channelId = "weekly_recaps",
                targetRoute = "weekly_recap"
            )
        }

        // Reschedule for the next week
        NotificationScheduler.scheduleWeeklyRecap(context)

        return Result.success()
    }
}
