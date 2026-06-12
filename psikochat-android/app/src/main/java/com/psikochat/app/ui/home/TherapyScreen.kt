package com.psikochat.app.ui.home

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavController
import com.psikochat.app.data.local.TokenManager
import com.psikochat.app.ui.theme.*
import com.psikochat.app.ui.components.*
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

@Immutable
data class Psychologist(
    val name: String,
    val specialty: String
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun TherapyScreen(navController: NavController, tokenManager: TokenManager) {
    val psychologists = remember {
        listOf(
            Psychologist("Uzm. Psk. Elif Kaya", "Bilişsel Terapi, Anksiyete"),
            Psychologist("Dr. Psk. Ahmet Yılmaz", "Depresyon, Aile Danışmanlığı"),
            Psychologist("Uzm. Psk. Ayşe Demir", "Çocuk ve Ergen Psikolojisi")
        )
    }

    val context = androidx.compose.ui.platform.LocalContext.current
    val db = com.psikochat.app.data.local.AppDatabase.getInstance(context)
    val appointmentRepository = com.psikochat.app.data.repository.AppointmentRepository(db.appointmentDao())
    val factory = object : ViewModelProvider.Factory {
        @Suppress("UNCHECKED_CAST")
        override fun <T : ViewModel> create(modelClass: Class<T>): T {
            return AppointmentViewModel(appointmentRepository) as T
        }
    }
    val viewModel: AppointmentViewModel = viewModel(factory = factory)

    var activePsychologist by remember { mutableStateOf<Psychologist?>(null) }
    var selectedDate by remember { mutableStateOf("Bugün") }
    var selectedTime by remember { mutableStateOf("14:00") }
    var showSuccessDialog by remember { mutableStateOf<com.psikochat.app.data.local.entity.CachedAppointment?>(null) }

    var showSuccessMessage by remember { mutableStateOf(false) }
    val snackbarHostState = remember { SnackbarHostState() }
    val scope = rememberCoroutineScope()

    Scaffold(
        snackbarHost = { SnackbarHost(snackbarHostState) },
        topBar = {
            CenterAlignedTopAppBar(
                title = {
                    Text(
                        "Psikolog Yönlendirme ve Randevu",
                        style = MaterialTheme.typography.titleMedium,
                        color = LoginTextColor,
                        fontSize = 16.sp
                    )
                },
                navigationIcon = {
                    IconButton(onClick = { navController.popBackStack() }) {
                        Icon(Icons.Default.KeyboardArrowLeft, contentDescription = "Geri", tint = LoginTextColor)
                    }
                },
                actions = {
                    IconButton(onClick = { }) {
                        Icon(Icons.Default.Menu, contentDescription = "Menü", tint = LoginTextColor)
                    }
                },
                colors = TopAppBarDefaults.centerAlignedTopAppBarColors(containerColor = Color.Transparent)
            )
        },
        bottomBar = {
            PremiumBottomNavigation(navController = navController, currentScreen = "therapy")
        },
        containerColor = LoginBackground
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(horizontal = 24.dp)
        ) {
            Spacer(modifier = Modifier.height(16.dp))

            // Premium supportive alert box
            PremiumCard(
                modifier = Modifier.fillMaxWidth(),
                backgroundColor = MildAlertBg,
                border = androidx.compose.foundation.BorderStroke(1.dp, MildAlertText.copy(alpha = 0.3f)),
                elevation = 0.dp
            ) {
                Row(
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Icon(Icons.Default.Warning, contentDescription = null, tint = MildAlertText)
                    Spacer(modifier = Modifier.width(12.dp))
                    Text(
                        text = "Destek alabileceğiniz profesyonel bir uzmana yönlendiriliyorsunuz.",
                        color = MildAlertText,
                        fontSize = 14.sp,
                        fontWeight = FontWeight.Bold
                    )
                }
            }

            Spacer(modifier = Modifier.height(24.dp))

            Text(
                text = "Psikolog Listesi",
                style = MaterialTheme.typography.titleLarge.copy(fontWeight = FontWeight.Bold),
                color = LoginTextColor
            )

            Spacer(modifier = Modifier.height(16.dp))

            LazyColumn(
                verticalArrangement = Arrangement.spacedBy(16.dp),
                contentPadding = PaddingValues(bottom = 16.dp)
            ) {
                items(psychologists, key = { it.name }) { psychologist ->
                    PsychologistCard(psychologist) {
                        activePsychologist = psychologist
                        selectedDate = "Bugün"
                        selectedTime = "14:00"
                    }
                }
            }
        }
    }

    if (activePsychologist != null) {
        val psychologist = activePsychologist!!
        AlertDialog(
            onDismissRequest = { activePsychologist = null },
            title = {
                Text(
                    "Randevu Planla",
                    fontWeight = FontWeight.Bold,
                    color = LoginTextColor
                )
            },
            text = {
                Column(modifier = Modifier.fillMaxWidth()) {
                    Text(
                        text = "${psychologist.name} ile görüşme zamanı seçin.",
                        fontSize = 14.sp,
                        color = LoginSecondaryText
                    )
                    Spacer(modifier = Modifier.height(16.dp))

                    Text("Tarih Seçin", fontWeight = FontWeight.Bold, fontSize = 12.sp, color = DarkTealPrimary)
                    Spacer(modifier = Modifier.height(8.dp))
                    Row(
                        horizontalArrangement = Arrangement.spacedBy(8.dp),
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        listOf("Bugün", "Yarın", "Sonraki Gün").forEach { dateOption ->
                            val isSelected = selectedDate == dateOption
                            Surface(
                                shape = RoundedCornerShape(12.dp),
                                color = if (isSelected) SoftMintAccent else Color.White,
                                border = BorderStroke(1.dp, if (isSelected) DarkTealPrimary else Color.LightGray),
                                modifier = Modifier
                                    .weight(1f)
                                    .clickable { selectedDate = dateOption }
                                    .padding(vertical = 2.dp)
                            ) {
                                Text(
                                    text = dateOption,
                                    color = if (isSelected) DarkTealPrimary else LoginTextColor,
                                    fontWeight = FontWeight.Bold,
                                    fontSize = 12.sp,
                                    textAlign = TextAlign.Center,
                                    modifier = Modifier.padding(vertical = 8.dp)
                                )
                            }
                        }
                    }

                    Spacer(modifier = Modifier.height(16.dp))

                    Text("Saat Seçin", fontWeight = FontWeight.Bold, fontSize = 12.sp, color = DarkTealPrimary)
                    Spacer(modifier = Modifier.height(8.dp))
                    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        val row1 = listOf("09:00", "10:00", "11:00", "14:00")
                        val row2 = listOf("15:00", "16:00", "17:00")
                        
                        Row(
                            horizontalArrangement = Arrangement.spacedBy(8.dp),
                            modifier = Modifier.fillMaxWidth()
                        ) {
                            row1.forEach { timeOption ->
                                val isSelected = selectedTime == timeOption
                                Surface(
                                    shape = RoundedCornerShape(12.dp),
                                    color = if (isSelected) SoftMintAccent else Color.White,
                                    border = BorderStroke(1.dp, if (isSelected) DarkTealPrimary else Color.LightGray),
                                    modifier = Modifier
                                        .weight(1f)
                                        .clickable { selectedTime = timeOption }
                                ) {
                                    Text(
                                        text = timeOption,
                                        color = if (isSelected) DarkTealPrimary else LoginTextColor,
                                        fontWeight = FontWeight.Bold,
                                        fontSize = 12.sp,
                                        textAlign = TextAlign.Center,
                                        modifier = Modifier.padding(vertical = 8.dp)
                                    )
                                }
                            }
                        }
                        
                        Row(
                            horizontalArrangement = Arrangement.spacedBy(8.dp),
                            modifier = Modifier.fillMaxWidth()
                        ) {
                            row2.forEach { timeOption ->
                                val isSelected = selectedTime == timeOption
                                Surface(
                                    shape = RoundedCornerShape(12.dp),
                                    color = if (isSelected) SoftMintAccent else Color.White,
                                    border = BorderStroke(1.dp, if (isSelected) DarkTealPrimary else Color.LightGray),
                                    modifier = Modifier
                                        .weight(1f)
                                        .clickable { selectedTime = timeOption }
                                ) {
                                    Text(
                                        text = timeOption,
                                        color = if (isSelected) DarkTealPrimary else LoginTextColor,
                                        fontWeight = FontWeight.Bold,
                                        fontSize = 12.sp,
                                        textAlign = TextAlign.Center,
                                        modifier = Modifier.padding(vertical = 8.dp)
                                    )
                                }
                            }
                            Spacer(modifier = Modifier.weight(1f))
                        }
                    }
                }
            },
            confirmButton = {
                Button(
                    onClick = {
                        // TODO: Replace local appointment storage with backend appointment API when available.
                        viewModel.bookAppointment(
                            psychologistName = psychologist.name,
                            specialty = psychologist.specialty,
                            date = selectedDate,
                            time = selectedTime
                        )
                        showSuccessDialog = com.psikochat.app.data.local.entity.CachedAppointment(
                            psychologistName = psychologist.name,
                            psychologistSpecialty = psychologist.specialty,
                            appointmentDate = selectedDate,
                            appointmentTime = selectedTime,
                            createdAt = ""
                        )
                        activePsychologist = null
                    },
                    colors = ButtonDefaults.buttonColors(containerColor = DarkTealPrimary)
                ) {
                    Text("Randevuyu Onayla", color = Color.White)
                }
            },
            dismissButton = {
                TextButton(onClick = { activePsychologist = null }) {
                    Text("İptal", color = LoginSecondaryText)
                }
            }
        )
    }

    if (showSuccessDialog != null) {
        val appt = showSuccessDialog!!
        AlertDialog(
            onDismissRequest = { showSuccessDialog = null },
            title = {
                Text(
                    "Randevunuz Planlandı! 🎉",
                    fontWeight = FontWeight.Bold,
                    color = LoginTextColor
                )
            },
            text = {
                Column {
                    Text(
                        text = "${appt.psychologistName} ile randevunuz başarıyla oluşturulmuştur.",
                        fontSize = 14.sp,
                        color = LoginTextColor
                    )
                    Spacer(modifier = Modifier.height(12.dp))
                    Surface(
                        color = SoftMintAccent.copy(alpha = 0.5f),
                        shape = RoundedCornerShape(12.dp),
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        Column(modifier = Modifier.padding(12.dp)) {
                            Text("Uzman: ${appt.psychologistName}", fontWeight = FontWeight.Bold, fontSize = 12.sp, color = DarkTealPrimary)
                            Text("Tarih: ${appt.appointmentDate}", fontSize = 12.sp, color = LoginTextColor)
                            Text("Saat: ${appt.appointmentTime}", fontSize = 12.sp, color = LoginTextColor)
                        }
                    }
                }
            },
            confirmButton = {
                Button(
                    onClick = { showSuccessDialog = null },
                    colors = ButtonDefaults.buttonColors(containerColor = DarkTealPrimary)
                ) {
                    Text("Harika", color = Color.White)
                }
            }
        )
    }
}

@Composable
fun PsychologistCard(psychologist: Psychologist, onAppointmentCreated: () -> Unit) {
    PremiumCard(
        modifier = Modifier.fillMaxWidth()
    ) {
        Box(modifier = Modifier.fillMaxWidth()) {
            Icon(
                Icons.Default.Info,
                contentDescription = null,
                tint = DarkTealAccent,
                modifier = Modifier.align(Alignment.TopEnd).size(20.dp)
            )
            
            Row(verticalAlignment = Alignment.CenterVertically) {
                Box(
                    modifier = Modifier
                        .size(64.dp)
                        .clip(CircleShape)
                        .background(SoftMintAccent),
                    contentAlignment = Alignment.Center
                ) {
                    Icon(Icons.Default.Person, contentDescription = null, modifier = Modifier.size(40.dp), tint = DarkTealPrimary)
                }
                
                Spacer(modifier = Modifier.width(16.dp))
                
                Column(modifier = Modifier.weight(1f)) {
                    Text(
                        text = psychologist.name,
                        fontWeight = FontWeight.Bold,
                        fontSize = 16.sp,
                        color = LoginTextColor
                    )
                    Text(
                        text = "Uzmanlık Alanı: ${psychologist.specialty}",
                        fontSize = 12.sp,
                        color = LoginSecondaryText
                    )
                    Spacer(modifier = Modifier.height(8.dp))
                    PremiumButton(
                        onClick = onAppointmentCreated,
                        cornerRadius = 12.dp,
                        height = 36.dp,
                        contentPadding = PaddingValues(horizontal = 16.dp, vertical = 0.dp)
                    ) {
                        Text("Randevu Oluştur", fontSize = 12.sp, color = Color.White)
                    }
                }
            }
        }
    }
}
