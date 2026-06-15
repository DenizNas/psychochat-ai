package com.psikochat.app.ui.notification

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import com.psikochat.app.data.local.AppDatabase
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch

class BootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action == Intent.ACTION_BOOT_COMPLETED) {
            val pendingResult = goAsync()
            val scope = CoroutineScope(Dispatchers.IO)
            scope.launch {
                try {
                    val db = AppDatabase.getInstance(context)
                    val appointments = db.appointmentDao().getAllAppointments().first()
                    val activeAppointments = appointments.filter { it.status == "scheduled" }
                    
                    for (appt in activeAppointments) {
                        NotificationScheduler.scheduleAppointmentReminder(context, appt)
                    }

                    // Reschedule Daily and Weekly checkins
                    NotificationScheduler.scheduleDailyCheckIn(context)
                    NotificationScheduler.scheduleWeeklyRecap(context)
                } catch (e: Exception) {
                    // Shield errors
                } finally {
                    pendingResult.finish()
                }
            }
        }
    }
}
