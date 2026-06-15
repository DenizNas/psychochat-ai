package com.psikochat.app.ui.psychologist

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.DateRange
import androidx.compose.material.icons.filled.Info
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavController
import com.psikochat.app.data.api.RetrofitClient
import com.psikochat.app.data.local.TokenManager
import com.psikochat.app.data.model.AppointmentDto
import com.psikochat.app.data.model.Resource
import com.psikochat.app.ui.theme.*
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun PsychologistAppointmentsScreen(navController: NavController, tokenManager: TokenManager) {
    val context = androidx.compose.ui.platform.LocalContext.current
    val api = RetrofitClient.create(tokenManager)
    val db = com.psikochat.app.data.local.AppDatabase.getInstance(context)
    val appointmentRepo = remember(api) { com.psikochat.app.data.repository.AppointmentRepository(api, db.appointmentDao(), context) }
    val appointmentFactory = object : ViewModelProvider.Factory {
        @Suppress("UNCHECKED_CAST")
        override fun <T : ViewModel> create(modelClass: Class<T>): T {
            return com.psikochat.app.ui.home.AppointmentViewModel(appointmentRepo) as T
        }
    }
    val viewModel: com.psikochat.app.ui.home.AppointmentViewModel = viewModel(factory = appointmentFactory)
    val fetchState by viewModel.fetchState.collectAsState()

    var appointmentToCancel by remember { mutableStateOf<AppointmentDto?>(null) }
    var showConfirmationDialog by remember { mutableStateOf(false) }

    val scope = rememberCoroutineScope()
    val snackbarHostState = remember { SnackbarHostState() }

    LaunchedEffect(Unit) {
        viewModel.loadAppointments()
    }

    Scaffold(
        snackbarHost = { SnackbarHost(snackbarHostState) },
        topBar = {
            CenterAlignedTopAppBar(
                title = {
                    Text(
                        "Randevu Takvimi",
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Bold,
                        color = LoginTextColor
                    )
                },
                navigationIcon = {
                    IconButton(onClick = { navController.popBackStack() }) {
                        Icon(
                            imageVector = Icons.AutoMirrored.Filled.ArrowBack,
                            contentDescription = "Geri",
                            tint = LoginTextColor
                        )
                    }
                },
                actions = {
                    IconButton(onClick = { viewModel.loadAppointments() }) {
                        Icon(
                            imageVector = Icons.Default.Refresh,
                            contentDescription = "Yenile",
                            tint = LoginTextColor
                        )
                    }
                },
                colors = TopAppBarDefaults.centerAlignedTopAppBarColors(
                    containerColor = Color.Transparent
                )
            )
        },
        containerColor = LoginBackground
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(horizontal = 24.dp)
        ) {
            when (val state = fetchState) {
                is Resource.Loading -> {
                    Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                        CircularProgressIndicator(color = DarkTealPrimary)
                    }
                }
                is Resource.Error -> {
                    Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                        Column(
                            horizontalAlignment = Alignment.CenterHorizontally,
                            verticalArrangement = Arrangement.Center
                        ) {
                            Icon(
                                imageVector = Icons.Default.Warning,
                                contentDescription = null,
                                tint = DangerRed,
                                modifier = Modifier.size(48.dp)
                            )
                            Spacer(modifier = Modifier.height(16.dp))
                            Text(
                                text = state.message ?: "Randevular yüklenemedi.",
                                style = MaterialTheme.typography.bodyMedium,
                                color = LoginTextColor,
                                textAlign = TextAlign.Center
                            )
                            Spacer(modifier = Modifier.height(16.dp))
                            Button(
                                onClick = { viewModel.loadAppointments() },
                                colors = ButtonDefaults.buttonColors(containerColor = DarkTealPrimary)
                            ) {
                                Text("Tekrar Dene", color = Color.White)
                            }
                        }
                    }
                }
                else -> {
                    val list = state?.data ?: emptyList()
                    val activeAppointments = list.filter { it.status == "scheduled" }
                        .sortedWith(compareBy({ it.appointmentDate }, { it.appointmentTime }))
                    
                    val pastOrCancelledAppointments = list.filter { it.status != "scheduled" }
                        .sortedWith(compareByDescending<AppointmentDto> { it.appointmentDate }.thenByDescending { it.appointmentTime })
                    
                    val combinedList = remember(activeAppointments, pastOrCancelledAppointments) {
                        val items = mutableListOf<Any>()
                        if (activeAppointments.isNotEmpty()) {
                            items.add("Aktif Randevular")
                            items.addAll(activeAppointments)
                        }
                        if (pastOrCancelledAppointments.isNotEmpty()) {
                            items.add("Geçmiş / İptal Edilenler")
                            items.addAll(pastOrCancelledAppointments)
                        }
                        items
                    }

                    if (list.isEmpty()) {
                        Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                            Column(
                                horizontalAlignment = Alignment.CenterHorizontally,
                                verticalArrangement = Arrangement.Center
                            ) {
                                Icon(
                                    imageVector = Icons.Default.DateRange,
                                    contentDescription = null,
                                    tint = LoginSecondaryText,
                                    modifier = Modifier.size(54.dp)
                                )
                                Spacer(modifier = Modifier.height(16.dp))
                                Text(
                                    text = "Henüz planlanmış randevunuz yok.",
                                    style = MaterialTheme.typography.bodyMedium,
                                    color = LoginSecondaryText,
                                    textAlign = TextAlign.Center
                                )
                            }
                        }
                    } else {
                        LazyColumn(
                            modifier = Modifier.fillMaxSize(),
                            verticalArrangement = Arrangement.spacedBy(12.dp),
                            contentPadding = PaddingValues(bottom = 24.dp)
                        ) {
                            items(combinedList) { item ->
                                if (item is String) {
                                    Text(
                                        text = item,
                                        fontSize = 14.sp,
                                        fontWeight = FontWeight.Bold,
                                        color = LoginTextColor,
                                        modifier = Modifier.padding(top = 12.dp, bottom = 4.dp)
                                    )
                                } else if (item is AppointmentDto) {
                                    AppointmentItem(
                                        appointment = item,
                                        onCancelClick = {
                                            appointmentToCancel = item
                                            showConfirmationDialog = true
                                        }
                                    )
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    if (showConfirmationDialog && appointmentToCancel != null) {
        val appt = appointmentToCancel!!
        AlertDialog(
            onDismissRequest = {
                showConfirmationDialog = false
                appointmentToCancel = null
            },
            icon = {
                Icon(
                    imageVector = Icons.Default.Warning,
                    contentDescription = null,
                    tint = DangerRed
                )
            },
            title = {
                Text(
                    text = "Randevuyu İptal Et",
                    fontWeight = FontWeight.Bold,
                    color = LoginTextColor
                )
            },
            text = {
                Text(
                    text = "${appt.patientName ?: "Danışan"} ile ${appt.appointmentDate} tarihindeki saat ${appt.appointmentTime} randevusunu iptal etmek istediğinize emin misiniz?\n\nBu işlem geri alınamaz.",
                    color = LoginSecondaryText
                )
            },
            confirmButton = {
                Button(
                    onClick = {
                        scope.launch {
                            viewModel.cancelAppointment(appt.id)
                            snackbarHostState.showSnackbar("Randevu başarıyla iptal edildi.")
                            showConfirmationDialog = false
                            appointmentToCancel = null
                        }
                    },
                    colors = ButtonDefaults.buttonColors(containerColor = DangerRed)
                ) {
                    Text("Evet, İptal Et", color = Color.White)
                }
            },
            dismissButton = {
                TextButton(
                    onClick = {
                        showConfirmationDialog = false
                        appointmentToCancel = null
                    }
                ) {
                    Text("Vazgeç", color = DarkTealPrimary)
                }
            }
        )
    }
}

@Composable
fun AppointmentItem(
    appointment: AppointmentDto,
    onCancelClick: () -> Unit
) {
    val isScheduled = appointment.status == "scheduled"
    val statusBgColor = if (isScheduled) SoftMintAccent.copy(alpha = 0.5f) else Color.LightGray.copy(alpha = 0.3f)
    val statusTextColor = if (isScheduled) DarkTealPrimary else Color.Gray
    val statusLabel = if (isScheduled) "Aktif" else if (appointment.status == "cancelled") "İptal Edildi" else appointment.status

    Surface(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(20.dp),
        color = PremiumWhiteCard,
        border = BorderStroke(1.dp, SoftMintAccent.copy(alpha = 0.5f)),
        shadowElevation = 1.dp
    ) {
        Column(
            modifier = Modifier.padding(16.dp)
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Column {
                    Text(
                        text = appointment.patientName ?: "Danışan",
                        fontSize = 15.sp,
                        fontWeight = FontWeight.Bold,
                        color = LoginTextColor
                    )
                    if (!appointment.patientEmail.isNullOrBlank()) {
                        Spacer(modifier = Modifier.height(2.dp))
                        Text(
                            text = appointment.patientEmail,
                            fontSize = 12.sp,
                            color = LoginSecondaryText
                        )
                    }
                }

                Surface(
                    shape = RoundedCornerShape(8.dp),
                    color = statusBgColor
                ) {
                    Text(
                        text = statusLabel,
                        fontSize = 11.sp,
                        fontWeight = FontWeight.Bold,
                        color = statusTextColor,
                        modifier = Modifier.padding(horizontal = 10.dp, vertical = 4.dp)
                    )
                }
            }

            Spacer(modifier = Modifier.height(12.dp))
            HorizontalDivider(color = SoftMintAccent.copy(alpha = 0.3f))
            Spacer(modifier = Modifier.height(12.dp))

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(
                        imageVector = Icons.Default.DateRange,
                        contentDescription = null,
                        tint = DarkTealPrimary,
                        modifier = Modifier.size(16.dp)
                    )
                    Spacer(modifier = Modifier.width(6.dp))
                    Text(
                        text = "${appointment.appointmentDate}  |  ${appointment.appointmentTime}",
                        fontSize = 13.sp,
                        fontWeight = FontWeight.SemiBold,
                        color = LoginTextColor
                    )
                }

                if (isScheduled) {
                    IconButton(
                        onClick = onCancelClick,
                        modifier = Modifier
                            .size(32.dp)
                            .background(DangerRed.copy(alpha = 0.1f), RoundedCornerShape(8.dp))
                    ) {
                        Icon(
                            imageVector = Icons.Default.Close,
                            contentDescription = "İptal Et",
                            tint = DangerRed,
                            modifier = Modifier.size(18.dp)
                        )
                    }
                }
            }
        }
    }
}
