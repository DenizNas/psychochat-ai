package com.psikochat.app.ui.home

import android.Manifest
import android.app.TimePickerDialog
import android.content.Context
import android.content.pm.PackageManager
import android.os.Build
import android.widget.Toast
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowLeft
import androidx.compose.material.icons.filled.Notifications
import androidx.compose.material.icons.filled.Info
import androidx.compose.material.icons.filled.DateRange
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import androidx.navigation.NavController
import com.psikochat.app.data.local.TokenManager
import com.psikochat.app.ui.components.PremiumCard
import com.psikochat.app.ui.components.PremiumButton
import com.psikochat.app.ui.theme.LoginBackground
import com.psikochat.app.ui.theme.LoginTextColor
import com.psikochat.app.ui.theme.LoginSecondaryText
import com.psikochat.app.ui.theme.LoginButton
import com.psikochat.app.ui.theme.PremiumWhiteCard
import com.psikochat.app.ui.notification.NotificationScheduler
import com.psikochat.app.ui.notification.NotificationHelper
import kotlinx.coroutines.launch

fun checkNotificationPermission(context: Context): Boolean {
    return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
        ContextCompat.checkSelfPermission(context, Manifest.permission.POST_NOTIFICATIONS) == PackageManager.PERMISSION_GRANTED
    } else {
        true
    }
}

fun getTurkishDayName(dayStr: String): String {
    return when (dayStr.uppercase()) {
        "MONDAY" -> "Pazartesi"
        "TUESDAY" -> "Salı"
        "WEDNESDAY" -> "Çarşamba"
        "THURSDAY" -> "Perşembe"
        "FRIDAY" -> "Cuma"
        "SATURDAY" -> "Cumartesi"
        "SUNDAY" -> "Pazar"
        else -> "Pazar"
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun NotificationSettingsScreen(navController: NavController, tokenManager: TokenManager) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()

    var hasPermission by remember { mutableStateOf(checkNotificationPermission(context)) }
    var showPolitePermissionDialog by remember { mutableStateOf(false) }
    var pendingSwitchAction by remember { mutableStateOf<(() -> Unit)?>(null) }
    
    val permissionLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.RequestPermission()
    ) { isGranted ->
        hasPermission = isGranted
        if (isGranted) {
            pendingSwitchAction?.invoke()
            Toast.makeText(context, "Bildirim izni onaylandı", Toast.LENGTH_SHORT).show()
        } else {
            Toast.makeText(context, "Bildirim izni reddedildi", Toast.LENGTH_SHORT).show()
        }
        pendingSwitchAction = null
    }

    // Collect configurations from DataStore
    val appointmentsEnabled by tokenManager.getAppointmentsReminderEnabled().collectAsState(initial = true)
    val dailyEnabled by tokenManager.getDailyCheckInEnabled().collectAsState(initial = true)
    val dailyTime by tokenManager.getDailyCheckInTime().collectAsState(initial = "20:00")
    val weeklyEnabled by tokenManager.getWeeklyRecapEnabled().collectAsState(initial = true)
    val weeklyDay by tokenManager.getWeeklyRecapDay().collectAsState(initial = "SUNDAY")
    val weeklyTime by tokenManager.getWeeklyRecapTime().collectAsState(initial = "19:00")

    var showDaySelectionDialog by remember { mutableStateOf(false) }

    Scaffold(
        topBar = {
            CenterAlignedTopAppBar(
                title = {
                    Text(
                        "Bildirim Ayarları",
                        style = MaterialTheme.typography.titleMedium,
                        color = LoginTextColor,
                        fontWeight = FontWeight.Bold
                    )
                },
                navigationIcon = {
                    IconButton(onClick = { navController.popBackStack() }) {
                        Icon(Icons.AutoMirrored.Filled.KeyboardArrowLeft, contentDescription = "Geri", tint = LoginTextColor)
                    }
                },
                colors = TopAppBarDefaults.centerAlignedTopAppBarColors(containerColor = Color.Transparent)
            )
        },
        containerColor = LoginBackground
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(horizontal = 24.dp)
                .verticalScroll(rememberScrollState()),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            Spacer(modifier = Modifier.height(16.dp))

            // 1. Polite Permission Request Card
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU && !hasPermission) {
                PremiumCard(modifier = Modifier.fillMaxWidth()) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(Icons.Default.Info, contentDescription = null, tint = LoginButton, modifier = Modifier.size(24.dp))
                        Spacer(modifier = Modifier.width(12.dp))
                        Column(modifier = Modifier.weight(1f)) {
                            Text("Bildirimler Devre Dışı", fontWeight = FontWeight.Bold, color = LoginTextColor)
                            Text("Randevularınızı kaçırmamak ve günlük duygu durum kontrollerinizi almak için bildirim izinlerini etkinleştirebilirsiniz.", fontSize = 12.sp, color = LoginSecondaryText)
                        }
                    }
                    Spacer(modifier = Modifier.height(16.dp))
                    PremiumButton(
                        onClick = {
                            pendingSwitchAction = {
                                // Default enable schedules if permission is granted
                            }
                            permissionLauncher.launch(Manifest.permission.POST_NOTIFICATIONS)
                        },
                        modifier = Modifier.fillMaxWidth(),
                        height = 40.dp
                    ) {
                        Text("Bildirim İznini Etkinleştir", color = Color.White, fontWeight = FontWeight.Bold, fontSize = 13.sp)
                    }
                }
                Spacer(modifier = Modifier.height(24.dp))
            }

            // 2. Notification Preferences Card
            PremiumCard(modifier = Modifier.fillMaxWidth()) {
                Text("Bildirim Tercihleri", fontWeight = FontWeight.Bold, color = LoginTextColor, modifier = Modifier.padding(bottom = 8.dp))

                // Toggle 1: Randevu Hatırlatmaları
                SettingSwitchItem(
                    icon = Icons.Default.DateRange,
                    title = "Randevu Hatırlatmaları",
                    checked = appointmentsEnabled,
                    onCheckedChange = { isChecked ->
                        if (isChecked && !hasPermission && Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                            pendingSwitchAction = {
                                scope.launch {
                                    tokenManager.saveAppointmentsReminderEnabled(true)
                                }
                            }
                            showPolitePermissionDialog = true
                        } else {
                            scope.launch {
                                tokenManager.saveAppointmentsReminderEnabled(isChecked)
                            }
                        }
                    }
                )

                HorizontalDivider(color = Color.LightGray.copy(alpha = 0.3f), modifier = Modifier.padding(vertical = 8.dp))

                // Toggle 2: Günlük Check-in
                SettingSwitchItem(
                    icon = Icons.Default.Notifications,
                    title = "Günlük Check-in Bildirimi",
                    checked = dailyEnabled,
                    onCheckedChange = { isChecked ->
                        if (isChecked && !hasPermission && Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                            pendingSwitchAction = {
                                scope.launch {
                                    tokenManager.saveDailyCheckInEnabled(true)
                                    NotificationScheduler.scheduleDailyCheckIn(context)
                                }
                            }
                            showPolitePermissionDialog = true
                        } else {
                            scope.launch {
                                tokenManager.saveDailyCheckInEnabled(isChecked)
                                if (isChecked) {
                                    NotificationScheduler.scheduleDailyCheckIn(context)
                                } else {
                                    NotificationScheduler.cancelDailyCheckIn(context)
                                }
                            }
                        }
                    }
                )

                HorizontalDivider(color = Color.LightGray.copy(alpha = 0.3f), modifier = Modifier.padding(vertical = 8.dp))

                // Toggle 3: Haftalık Özet
                SettingSwitchItem(
                    icon = Icons.Default.Info,
                    title = "Haftalık Wellness Özeti",
                    checked = weeklyEnabled,
                    onCheckedChange = { isChecked ->
                        if (isChecked && !hasPermission && Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                            pendingSwitchAction = {
                                scope.launch {
                                    tokenManager.saveWeeklyRecapEnabled(true)
                                    NotificationScheduler.scheduleWeeklyRecap(context)
                                }
                            }
                            showPolitePermissionDialog = true
                        } else {
                            scope.launch {
                                tokenManager.saveWeeklyRecapEnabled(isChecked)
                                if (isChecked) {
                                    NotificationScheduler.scheduleWeeklyRecap(context)
                                } else {
                                    NotificationScheduler.cancelWeeklyRecap(context)
                                }
                            }
                        }
                    }
                )
            }

            Spacer(modifier = Modifier.height(24.dp))

            // 3. Time Selectors Card
            if (dailyEnabled || weeklyEnabled) {
                PremiumCard(modifier = Modifier.fillMaxWidth()) {
                    Text("Zamanlama Ayarları", fontWeight = FontWeight.Bold, color = LoginTextColor, modifier = Modifier.padding(bottom = 8.dp))

                    if (dailyEnabled) {
                        val parts = dailyTime.split(":")
                        val dailyHour = parts.getOrNull(0)?.toIntOrNull() ?: 20
                        val dailyMinute = parts.getOrNull(1)?.toIntOrNull() ?: 0

                        val timePicker = TimePickerDialog(
                            context,
                            { _, hour, minute ->
                                val selectedTime = String.format("%02d:%02d", hour, minute)
                                scope.launch {
                                    tokenManager.saveDailyCheckInTime(selectedTime)
                                    NotificationScheduler.scheduleDailyCheckIn(context)
                                    Toast.makeText(context, "Günlük check-in saati güncellendi: $selectedTime", Toast.LENGTH_SHORT).show()
                                }
                            },
                            dailyHour,
                            dailyMinute,
                            true
                        )

                        SettingClickItem(
                            icon = Icons.Default.Notifications,
                            title = "Günlük Check-in Saati",
                            value = dailyTime,
                            onClick = { timePicker.show() }
                        )
                    }

                    if (dailyEnabled && weeklyEnabled) {
                        HorizontalDivider(color = Color.LightGray.copy(alpha = 0.3f), modifier = Modifier.padding(vertical = 8.dp))
                    }

                    if (weeklyEnabled) {
                        val parts = weeklyTime.split(":")
                        val weeklyHour = parts.getOrNull(0)?.toIntOrNull() ?: 19
                        val weeklyMinute = parts.getOrNull(1)?.toIntOrNull() ?: 0

                        val timePicker = TimePickerDialog(
                            context,
                            { _, hour, minute ->
                                val selectedTime = String.format("%02d:%02d", hour, minute)
                                scope.launch {
                                    tokenManager.saveWeeklyRecapTime(selectedTime)
                                    NotificationScheduler.scheduleWeeklyRecap(context)
                                    Toast.makeText(context, "Haftalık özet saati güncellendi: $selectedTime", Toast.LENGTH_SHORT).show()
                                }
                            },
                            weeklyHour,
                            weeklyMinute,
                            true
                        )

                        SettingClickItem(
                            icon = Icons.Default.DateRange,
                            title = "Haftalık Özet Günü",
                            value = getTurkishDayName(weeklyDay),
                            onClick = { showDaySelectionDialog = true }
                        )

                        HorizontalDivider(color = Color.LightGray.copy(alpha = 0.3f), modifier = Modifier.padding(vertical = 8.dp))

                        SettingClickItem(
                            icon = Icons.Default.Info,
                            title = "Haftalık Özet Saati",
                            value = weeklyTime,
                            onClick = { timePicker.show() }
                        )
                    }
                }
                Spacer(modifier = Modifier.height(24.dp))
            }

            // 4. Debug Status and Test Notification Card
            PremiumCard(modifier = Modifier.fillMaxWidth()) {
                Text("Sistem Durumu ve Test", fontWeight = FontWeight.Bold, color = LoginTextColor, modifier = Modifier.padding(bottom = 8.dp))
                
                val dailyStatus = if (dailyEnabled) "Planlandı ($dailyTime)" else "Devre Dışı"
                val weeklyStatus = if (weeklyEnabled) "Planlandı (${getTurkishDayName(weeklyDay)} $weeklyTime)" else "Devre Dışı"
                
                val db = remember { com.psikochat.app.data.local.AppDatabase.getInstance(context) }
                val appointmentsFlow = remember { db.appointmentDao().getAllAppointments() }
                val appointments by appointmentsFlow.collectAsState(initial = emptyList())
                val activeAppt = appointments.firstOrNull { it.status == "scheduled" }
                val apptStatus = if (appointmentsEnabled && activeAppt != null) {
                    "Aktif (${activeAppt.psychologistName} - ${activeAppt.appointmentDate} ${activeAppt.appointmentTime})"
                } else if (!appointmentsEnabled) {
                    "Devre Dışı"
                } else {
                    "Aktif Randevu Bulunmuyor"
                }

                Column(
                    modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp),
                    verticalArrangement = Arrangement.spacedBy(6.dp)
                ) {
                    Text("• Daily check-in scheduled: $dailyStatus", fontSize = 13.sp, color = LoginSecondaryText)
                    Text("• Weekly recap scheduled: $weeklyStatus", fontSize = 13.sp, color = LoginSecondaryText)
                    Text("• Appointment reminder active: $apptStatus", fontSize = 13.sp, color = LoginSecondaryText)
                }

                Spacer(modifier = Modifier.height(16.dp))

                PremiumButton(
                    onClick = {
                        if (!hasPermission && Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                            pendingSwitchAction = {
                                NotificationHelper.showNotification(
                                    context = context,
                                    id = 9999,
                                    title = "Test Bildirimi",
                                    body = "PsikoChat bildirim sistemi başarıyla çalışıyor! Görünüm ve ayarlar için dokunun.",
                                    channelId = "daily_checkins",
                                    targetRoute = "notification_settings"
                                )
                            }
                            showPolitePermissionDialog = true
                        } else {
                            NotificationHelper.showNotification(
                                context = context,
                                id = 9999,
                                title = "Test Bildirimi",
                                body = "PsikoChat bildirim sistemi başarıyla çalışıyor! Görünüm ve ayarlar için dokunun.",
                                channelId = "daily_checkins",
                                targetRoute = "notification_settings"
                            )
                            Toast.makeText(context, "Test bildirimi gönderildi", Toast.LENGTH_SHORT).show()
                        }
                    },
                    modifier = Modifier.fillMaxWidth(),
                    height = 40.dp
                ) {
                    Text("Test Bildirimi Gönder", color = Color.White, fontWeight = FontWeight.Bold, fontSize = 13.sp)
                }
            }
            Spacer(modifier = Modifier.height(24.dp))
        }
    }

    // Polite explanation alert before requesting permission
    if (showPolitePermissionDialog) {
        AlertDialog(
            onDismissRequest = {
                showPolitePermissionDialog = false
                pendingSwitchAction = null
            },
            title = { Text("Bildirim İzni Gerekli", fontWeight = FontWeight.Bold) },
            text = { Text("Randevu hatırlatmalarınızı, günlük duygu durum kontrollerinizi ve haftalık iyi oluş raporlarınızı size ulaştırabilmemiz için bildirim gönderme iznine ihtiyacımız var.") },
            confirmButton = {
                Button(
                    onClick = {
                        showPolitePermissionDialog = false
                        permissionLauncher.launch(Manifest.permission.POST_NOTIFICATIONS)
                    },
                    colors = ButtonDefaults.buttonColors(containerColor = LoginButton)
                ) {
                    Text("İzin Ver", color = Color.White)
                }
            },
            dismissButton = {
                TextButton(onClick = {
                    showPolitePermissionDialog = false
                    pendingSwitchAction = null
                }) {
                    Text("Vazgeç")
                }
            }
        )
    }

    // Weekly Recap Day Selector Dialog
    if (showDaySelectionDialog) {
        val daysOfWeek = listOf(
            "MONDAY" to "Pazartesi",
            "TUESDAY" to "Salı",
            "WEDNESDAY" to "Çarşamba",
            "THURSDAY" to "Perşembe",
            "FRIDAY" to "Cuma",
            "SATURDAY" to "Cumartesi",
            "SUNDAY" to "Pazar"
        )
        AlertDialog(
            onDismissRequest = { showDaySelectionDialog = false },
            title = { Text("Haftalık Özet Günü Seçin", fontWeight = FontWeight.Bold) },
            text = {
                Column {
                    daysOfWeek.forEach { (code, label) ->
                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .clickable {
                                    scope.launch {
                                        tokenManager.saveWeeklyRecapDay(code)
                                        NotificationScheduler.scheduleWeeklyRecap(context)
                                        Toast.makeText(context, "Haftalık özet günü güncellendi: $label", Toast.LENGTH_SHORT).show()
                                        showDaySelectionDialog = false
                                    }
                                }
                                .padding(vertical = 12.dp),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            RadioButton(selected = weeklyDay == code, onClick = null)
                            Spacer(modifier = Modifier.width(12.dp))
                            Text(label)
                        }
                    }
                }
            },
            confirmButton = {}
        )
    }
}
