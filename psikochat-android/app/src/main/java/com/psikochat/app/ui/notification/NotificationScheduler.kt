package com.psikochat.app.ui.notification

import android.app.AlarmManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.os.Build
import androidx.core.app.AlarmManagerCompat
import androidx.work.*
import com.psikochat.app.data.local.TokenManager
import com.psikochat.app.data.local.entity.CachedAppointment
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import java.time.DayOfWeek
import java.time.LocalDateTime
import java.time.ZoneId
import java.time.temporal.ChronoUnit
import java.util.Calendar
import java.util.concurrent.TimeUnit

object NotificationScheduler {

    // For Daily Check-In
    fun scheduleDailyCheckIn(context: Context) {
        val workManager = WorkManager.getInstance(context)
        val tokenManager = TokenManager(context)

        runBlocking {
            val enabled = tokenManager.getDailyCheckInEnabled().first()
            if (!enabled) {
                workManager.cancelUniqueWork("daily_checkin_work")
                return@runBlocking
            }

            val timeStr = tokenManager.getDailyCheckInTime().first()
            val delayMs = calculateDailyDelay(timeStr)

            val workRequest = OneTimeWorkRequestBuilder<DailyCheckInWorker>()
                .setInitialDelay(delayMs, TimeUnit.MILLISECONDS)
                .build()

            workManager.enqueueUniqueWork(
                "daily_checkin_work",
                ExistingWorkPolicy.REPLACE,
                workRequest
            )
        }
    }

    fun cancelDailyCheckIn(context: Context) {
        WorkManager.getInstance(context).cancelUniqueWork("daily_checkin_work")
    }

    private fun calculateDailyDelay(timeStr: String): Long {
        val parts = timeStr.split(":")
        val hour = parts.getOrNull(0)?.toIntOrNull() ?: 20
        val minute = parts.getOrNull(1)?.toIntOrNull() ?: 0

        val now = LocalDateTime.now()
        var target = now.withHour(hour).withMinute(minute).withSecond(0).withNano(0)
        if (target.isBefore(now)) {
            target = target.plusDays(1)
        }
        return ChronoUnit.MILLIS.between(now, target)
    }

    // For Weekly Recap
    fun scheduleWeeklyRecap(context: Context) {
        val workManager = WorkManager.getInstance(context)
        val tokenManager = TokenManager(context)

        runBlocking {
            val enabled = tokenManager.getWeeklyRecapEnabled().first()
            if (!enabled) {
                workManager.cancelUniqueWork("weekly_recap_work")
                return@runBlocking
            }

            val dayStr = tokenManager.getWeeklyRecapDay().first() // e.g. "SUNDAY"
            val timeStr = tokenManager.getWeeklyRecapTime().first()
            val delayMs = calculateWeeklyDelay(dayStr, timeStr)

            val workRequest = OneTimeWorkRequestBuilder<WeeklyRecapWorker>()
                .setInitialDelay(delayMs, TimeUnit.MILLISECONDS)
                .build()

            workManager.enqueueUniqueWork(
                "weekly_recap_work",
                ExistingWorkPolicy.REPLACE,
                workRequest
            )
        }
    }

    fun cancelWeeklyRecap(context: Context) {
        WorkManager.getInstance(context).cancelUniqueWork("weekly_recap_work")
    }

    private fun calculateWeeklyDelay(dayStr: String, timeStr: String): Long {
        val parts = timeStr.split(":")
        val hour = parts.getOrNull(0)?.toIntOrNull() ?: 19
        val minute = parts.getOrNull(1)?.toIntOrNull() ?: 0

        val targetDay = try {
            DayOfWeek.valueOf(dayStr.uppercase())
        } catch (e: Exception) {
            DayOfWeek.SUNDAY
        }

        val now = LocalDateTime.now()
        var target = now.withHour(hour).withMinute(minute).withSecond(0).withNano(0)
        
        while (target.dayOfWeek != targetDay) {
            target = target.plusDays(1)
        }
        
        if (target.isBefore(now)) {
            target = target.plusWeeks(1)
        }

        return ChronoUnit.MILLIS.between(now, target)
    }

    // For Appointment Reminders
    fun scheduleAppointmentReminder(context: Context, appointment: CachedAppointment) {
        if (appointment.status != "scheduled") {
            cancelAppointmentReminder(context, appointment.id)
            return
        }

        val triggerTime = parseAppointmentDateTime(appointment.appointmentDate, appointment.appointmentTime) ?: return
        val oneHourBefore = triggerTime - (60 * 60 * 1000)

        // Do not schedule if reminder is in the past
        if (oneHourBefore < System.currentTimeMillis()) {
            return
        }

        val alarmManager = context.getSystemService(Context.ALARM_SERVICE) as AlarmManager
        val intent = Intent(context, AppointmentReminderReceiver::class.java).apply {
            putExtra("appointment_id", appointment.id)
            putExtra("psychologist_name", appointment.psychologistName)
            putExtra("appointment_time", appointment.appointmentTime)
        }

        val pendingIntent = PendingIntent.getBroadcast(
            context,
            appointment.id,
            intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                if (alarmManager.canScheduleExactAlarms()) {
                    alarmManager.setExactAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, oneHourBefore, pendingIntent)
                } else {
                    alarmManager.setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, oneHourBefore, pendingIntent)
                }
            } else {
                AlarmManagerCompat.setExactAndAllowWhileIdle(alarmManager, AlarmManager.RTC_WAKEUP, oneHourBefore, pendingIntent)
            }
        } catch (securityException: SecurityException) {
            // Fallback gracefully on API 31+ exact alarm permission denied
            alarmManager.setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, oneHourBefore, pendingIntent)
        }
    }

    fun cancelAppointmentReminder(context: Context, appointmentId: Int) {
        val alarmManager = context.getSystemService(Context.ALARM_SERVICE) as AlarmManager
        val intent = Intent(context, AppointmentReminderReceiver::class.java)
        val pendingIntent = PendingIntent.getBroadcast(
            context,
            appointmentId,
            intent,
            PendingIntent.FLAG_NO_CREATE or PendingIntent.FLAG_IMMUTABLE
        )
        if (pendingIntent != null) {
            alarmManager.cancel(pendingIntent)
            pendingIntent.cancel()
        }
    }

    private fun parseAppointmentDateTime(dateStr: String, timeStr: String): Long? {
        return try {
            val dateParts = dateStr.split("-")
            val timeParts = timeStr.split(":")
            val calendar = Calendar.getInstance().apply {
                set(Calendar.YEAR, dateParts[0].toInt())
                set(Calendar.MONTH, dateParts[1].toInt() - 1)
                set(Calendar.DAY_OF_MONTH, dateParts[2].toInt())
                set(Calendar.HOUR_OF_DAY, timeParts[0].toInt())
                set(Calendar.MINUTE, timeParts[1].toInt())
                set(Calendar.SECOND, 0)
                set(Calendar.MILLISECOND, 0)
            }
            calendar.timeInMillis
        } catch (e: Exception) {
            null
        }
    }
}
