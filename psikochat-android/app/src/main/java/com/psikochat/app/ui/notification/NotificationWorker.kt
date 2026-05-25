package com.psikochat.app.ui.notification

import android.content.Context
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import com.psikochat.app.data.api.RetrofitClient
import com.psikochat.app.data.local.TokenManager
import com.psikochat.app.data.repository.NotificationRepository
import com.psikochat.app.data.model.Resource
import kotlinx.coroutines.flow.first

class NotificationWorker(
    private val context: Context,
    params: WorkerParameters
) : CoroutineWorker(context, params) {

    override suspend fun doWork(): Result {
        val tokenManager = TokenManager(context)
        val token = tokenManager.getToken().first()

        if (token.isNullOrEmpty()) {
            return Result.success()
        }

        return try {
            val api = RetrofitClient.create(tokenManager)
            val repository = NotificationRepository(api)
            val result = repository.getNotifications()

            if (result is Resource.Success && result.data != null) {
                val pending = result.data.filter { it.status == "pending" }
                for (event in pending) {
                    // 1. Show notification to user
                    NotificationHelper.showNotification(
                        context,
                        event.id,
                        event.title,
                        event.body,
                        event.notificationType
                    )
                    // 2. Mark notification as delivered
                    repository.markNotificationDelivered(event.id)
                }
                Result.success()
            } else {
                Result.retry()
            }
        } catch (e: Exception) {
            Result.retry()
        }
    }
}
