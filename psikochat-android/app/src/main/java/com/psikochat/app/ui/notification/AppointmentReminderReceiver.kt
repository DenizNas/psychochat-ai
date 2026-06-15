package com.psikochat.app.ui.notification

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import com.psikochat.app.data.local.TokenManager
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking

class AppointmentReminderReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        val appointmentId = intent.getIntExtra("appointment_id", -1)
        val appointmentTime = intent.getStringExtra("appointment_time") ?: ""

        if (appointmentId == -1) return

        runBlocking {
            val tokenManager = TokenManager(context)
            val enabled = tokenManager.getAppointmentsReminderEnabled().first()
            if (enabled) {
                NotificationHelper.showNotification(
                    context = context,
                    id = appointmentId,
                    title = "Randevu Hatırlatması",
                    body = "Bugün saat $appointmentTime için bir randevun var.",
                    channelId = "appointment_reminders",
                    targetRoute = "therapy"
                )
            }
        }
    }
}
