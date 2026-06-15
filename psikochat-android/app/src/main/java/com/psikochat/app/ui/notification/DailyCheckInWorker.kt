package com.psikochat.app.ui.notification

import android.content.Context
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import com.psikochat.app.data.local.TokenManager
import kotlinx.coroutines.flow.first

class DailyCheckInWorker(
    private val context: Context,
    params: WorkerParameters
) : CoroutineWorker(context, params) {

    override suspend fun doWork(): Result {
        val tokenManager = TokenManager(context)
        val enabled = tokenManager.getDailyCheckInEnabled().first()

        if (enabled) {
            NotificationHelper.showNotification(
                context = context,
                id = 2001, // Unique ID for daily check-in
                title = "Bugün nasılsın?",
                body = "Kısa bir duygu check-in’i yapmak ister misin?",
                channelId = "daily_checkins",
                targetRoute = "mood_journal"
            )
        }

        // Reschedule for the next day
        NotificationScheduler.scheduleDailyCheckIn(context)

        return Result.success()
    }
}
