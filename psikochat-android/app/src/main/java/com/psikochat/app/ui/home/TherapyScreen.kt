package com.psikochat.app.ui.home

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
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
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavController
import com.psikochat.app.data.api.RetrofitClient
import com.psikochat.app.data.local.TokenManager
import com.psikochat.app.data.local.entity.CachedAppointment
import com.psikochat.app.data.model.PsychologistDto
import com.psikochat.app.data.model.Resource
import com.psikochat.app.ui.components.*
import com.psikochat.app.ui.theme.*
import kotlinx.coroutines.launch
import java.time.Instant
import java.time.LocalDate
import java.time.ZoneOffset

// Helper to format date in Turkish (e.g. 12 Haziran 2026)
fun formatTurkishDate(millis: Long): String {
    val date = Instant.ofEpochMilli(millis)
        .atZone(ZoneOffset.UTC)
        .toLocalDate()
    val day = date.dayOfMonth
    val year = date.year
    val monthTurkish = when (date.monthValue) {
        1 -> "Ocak"
        2 -> "Şubat"
        3 -> "Mart"
        4 -> "Nisan"
        5 -> "Mayıs"
        6 -> "Haziran"
        7 -> "Temmuz"
        8 -> "Ağustos"
        9 -> "Eylül"
        10 -> "Ekim"
        11 -> "Kasım"
        12 -> "Aralık"
        else -> ""
    }
    return "$day $monthTurkish $year"
}

// Helper to format date for backend API (YYYY-MM-DD)
fun formatBackendDate(millis: Long): String {
    val date = Instant.ofEpochMilli(millis)
        .atZone(ZoneOffset.UTC)
        .toLocalDate()
    return String.format(java.util.Locale.US, "%04d-%02d-%02d", date.year, date.monthValue, date.dayOfMonth)
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun TherapyScreen(navController: NavController, tokenManager: TokenManager) {
    val context = androidx.compose.ui.platform.LocalContext.current
    val db = com.psikochat.app.data.local.AppDatabase.getInstance(context)
    val api = RetrofitClient.create(tokenManager)
    val appointmentRepository = com.psikochat.app.data.repository.AppointmentRepository(api, db.appointmentDao())
    val factory = object : ViewModelProvider.Factory {
        @Suppress("UNCHECKED_CAST")
        override fun <T : ViewModel> create(modelClass: Class<T>): T {
            return AppointmentViewModel(appointmentRepository) as T
        }
    }
    val viewModel: AppointmentViewModel = viewModel(factory = factory)

    val userRole by tokenManager.getRole().collectAsState(initial = "user")

    // UI States
    var selectedTab by remember { mutableStateOf(0) } // 0: Randevu Al, 1: Randevularım
    var currentStep by remember { mutableStateOf(1) } // Steps 1 to 4

    var selectedPsychologist by remember { mutableStateOf<PsychologistDto?>(null) }
    var selectedDateMillis by remember { mutableStateOf<Long?>(null) }
    var selectedTime by remember { mutableStateOf<String?>(null) }
    
    var showDatePicker by remember { mutableStateOf(false) }
    var showSuccessDialog by remember { mutableStateOf(false) }

    val psychologistsState by viewModel.psychologistsState.collectAsState()
    val bookAppointmentState by viewModel.bookAppointmentState.collectAsState()
    val fetchState by viewModel.fetchState.collectAsState()
    val allAppointments by viewModel.allAppointments.collectAsState()

    val scope = rememberCoroutineScope()
    val snackbarHostState = remember { SnackbarHostState() }

    // Check for psychologist role block
    if (userRole == "psychologist") {
        Box(
            modifier = Modifier
                .fillMaxSize()
                .background(LoginBackground)
                .padding(24.dp),
            contentAlignment = Alignment.Center
        ) {
            Column(
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.Center
            ) {
                Icon(
                    imageVector = Icons.Default.Warning,
                    contentDescription = null,
                    tint = DangerRed,
                    modifier = Modifier.size(64.dp)
                )
                Spacer(modifier = Modifier.height(24.dp))
                Text(
                    text = "Psikolog yetkisiyle randevu alamazsınız.",
                    fontSize = 18.sp,
                    fontWeight = FontWeight.Bold,
                    color = LoginTextColor,
                    textAlign = TextAlign.Center
                )
                Spacer(modifier = Modifier.height(8.dp))
                Text(
                    text = "Lütfen randevu listelerinizi görmek için uzman panelini kullanın.",
                    fontSize = 14.sp,
                    color = LoginSecondaryText,
                    textAlign = TextAlign.Center
                )
                Spacer(modifier = Modifier.height(24.dp))
                Button(
                    onClick = { navController.popBackStack() },
                    colors = ButtonDefaults.buttonColors(containerColor = DarkTealPrimary)
                ) {
                    Text("Geri Dön", color = Color.White)
                }
            }
        }
        return
    }

    // Success flow observer
    LaunchedEffect(bookAppointmentState) {
        if (bookAppointmentState is Resource.Success) {
            showSuccessDialog = true
            viewModel.clearBookAppointmentState()
        }
    }

    Scaffold(
        snackbarHost = { SnackbarHost(snackbarHostState) },
        topBar = {
            CenterAlignedTopAppBar(
                title = {
                    Text(
                        "Psikolog Yönlendirme ve Randevu",
                        style = MaterialTheme.typography.titleMedium,
                        color = LoginTextColor,
                        fontSize = 16.sp,
                        fontWeight = FontWeight.Bold
                    )
                },
                navigationIcon = {
                    IconButton(onClick = { navController.popBackStack() }) {
                        Icon(Icons.Default.KeyboardArrowLeft, contentDescription = "Geri", tint = LoginTextColor)
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
            // Tabs Row
            SecondaryTabRow(
                selectedTabIndex = selectedTab,
                containerColor = Color.Transparent,
                contentColor = DarkTealPrimary,
            ) {
                Tab(
                    selected = selectedTab == 0,
                    onClick = { selectedTab = 0 },
                    text = { Text("Randevu Al", fontWeight = FontWeight.Bold, fontSize = 14.sp) }
                )
                Tab(
                    selected = selectedTab == 1,
                    onClick = { selectedTab = 1 },
                    text = { Text("Randevularım", fontWeight = FontWeight.Bold, fontSize = 14.sp) }
                )
            }

            Spacer(modifier = Modifier.height(16.dp))

            if (selectedTab == 0) {
                // Stepper Row
                Row(
                    modifier = Modifier.fillMaxWidth().padding(vertical = 8.dp),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    for (i in 1..4) {
                        val isActive = i == currentStep
                        val isCompleted = i < currentStep
                        val stepColor = if (isActive) DarkTealPrimary else if (isCompleted) SoftMintAccent else Color.LightGray.copy(alpha = 0.5f)
                        val stepTextColor = if (isActive || isCompleted) DarkTealPrimary else Color.Gray

                        Column(
                            horizontalAlignment = Alignment.CenterHorizontally,
                            modifier = Modifier.weight(1f)
                        ) {
                            Box(
                                modifier = Modifier
                                    .size(28.dp)
                                    .clip(CircleShape)
                                    .background(stepColor),
                                contentAlignment = Alignment.Center
                            ) {
                                if (isCompleted) {
                                    Icon(Icons.Default.Check, contentDescription = null, tint = Color.White, modifier = Modifier.size(16.dp))
                                } else {
                                    Text(text = i.toString(), color = if (isActive) Color.White else Color.Gray, fontWeight = FontWeight.Bold, fontSize = 12.sp)
                                }
                            }
                            Spacer(modifier = Modifier.height(4.dp))
                            Text(
                                text = when (i) {
                                    1 -> "Uzman"
                                    2 -> "Tarih"
                                    3 -> "Saat"
                                    4 -> "Onay"
                                    else -> ""
                                },
                                fontSize = 10.sp,
                                fontWeight = if (isActive) FontWeight.Bold else FontWeight.Normal,
                                color = stepTextColor
                            )
                        }
                        if (i < 4) {
                            Box(
                                modifier = Modifier
                                    .height(2.dp)
                                    .weight(0.5f)
                                    .background(if (isCompleted) SoftMintAccent else Color.LightGray.copy(alpha = 0.5f))
                            )
                        }
                    }
                }

                Spacer(modifier = Modifier.height(16.dp))

                // Step Contents
                when (currentStep) {
                    1 -> {
                        // Step 1: Select Psychologist
                        Text(
                            text = "Uzman Seçin",
                            style = MaterialTheme.typography.titleMedium.copy(fontWeight = FontWeight.Bold),
                            color = LoginTextColor,
                            modifier = Modifier.padding(bottom = 12.dp)
                        )

                        when (val state = psychologistsState) {
                            is Resource.Loading -> {
                                Box(modifier = Modifier.weight(1f).fillMaxWidth(), contentAlignment = Alignment.Center) {
                                    CircularProgressIndicator(color = DarkTealPrimary)
                                }
                            }
                            is Resource.Error -> {
                                val errMessage = state.message ?: ""
                                val isConnectionErr = errMessage.contains("connect", ignoreCase = true) ||
                                        errMessage.contains("resolve", ignoreCase = true) ||
                                        errMessage.contains("network", ignoreCase = true) ||
                                        errMessage.contains("bağlantı", ignoreCase = true)
                                val displayErr = if (isConnectionErr) "Randevu oluşturmak için bağlantı gerekli." else errMessage

                                Box(modifier = Modifier.weight(1f).fillMaxWidth(), contentAlignment = Alignment.Center) {
                                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                                        Icon(Icons.Default.Warning, contentDescription = null, tint = DangerRed, modifier = Modifier.size(48.dp))
                                        Spacer(modifier = Modifier.height(16.dp))
                                        Text(displayErr, color = LoginTextColor, textAlign = TextAlign.Center, modifier = Modifier.padding(horizontal = 24.dp))
                                        Spacer(modifier = Modifier.height(16.dp))
                                        Button(
                                            onClick = { viewModel.loadApprovedPsychologists() },
                                            colors = ButtonDefaults.buttonColors(containerColor = DarkTealPrimary)
                                        ) {
                                            Text("Tekrar Dene", color = Color.White)
                                        }
                                    }
                                }
                            }
                            is Resource.Success -> {
                                val list = state.data ?: emptyList()
                                if (list.isEmpty()) {
                                    Box(modifier = Modifier.weight(1f).fillMaxWidth(), contentAlignment = Alignment.Center) {
                                        Text("Şu an onaylı uzman psikolog bulunmamaktadır.", color = LoginSecondaryText, textAlign = TextAlign.Center)
                                    }
                                } else {
                                    Column(modifier = Modifier.weight(1f)) {
                                        LazyColumn(
                                            modifier = Modifier.weight(1f),
                                            verticalArrangement = Arrangement.spacedBy(12.dp),
                                            contentPadding = PaddingValues(bottom = 16.dp)
                                        ) {
                                            items(list, key = { it.username }) { psychologist ->
                                                val isSelected = selectedPsychologist?.username == psychologist.username
                                                val borderColor = if (isSelected) DarkTealPrimary else Color.Transparent
                                                val bgColor = if (isSelected) SoftMintAccent.copy(alpha = 0.2f) else PremiumWhiteCard

                                                Surface(
                                                    modifier = Modifier
                                                        .fillMaxWidth()
                                                        .clickable { selectedPsychologist = psychologist },
                                                    shape = RoundedCornerShape(16.dp),
                                                    color = bgColor,
                                                    border = BorderStroke(1.5.dp, borderColor),
                                                    shadowElevation = 1.dp
                                                ) {
                                                    Row(
                                                        modifier = Modifier.padding(16.dp),
                                                        verticalAlignment = Alignment.CenterVertically
                                                    ) {
                                                        Box(
                                                            modifier = Modifier
                                                                .size(52.dp)
                                                                .clip(CircleShape)
                                                                .background(SoftMintAccent),
                                                            contentAlignment = Alignment.Center
                                                        ) {
                                                            Icon(Icons.Default.Person, contentDescription = null, modifier = Modifier.size(32.dp), tint = DarkTealPrimary)
                                                        }
                                                        Spacer(modifier = Modifier.width(16.dp))
                                                        Column(modifier = Modifier.weight(1f)) {
                                                            Row(verticalAlignment = Alignment.CenterVertically) {
                                                                Text(
                                                                    text = "${psychologist.title} ${psychologist.fullName ?: psychologist.username}",
                                                                    fontWeight = FontWeight.Bold,
                                                                    fontSize = 15.sp,
                                                                    color = LoginTextColor,
                                                                    maxLines = 1,
                                                                    overflow = TextOverflow.Ellipsis
                                                                )
                                                                Spacer(modifier = Modifier.width(6.dp))
                                                                // Approval badge
                                                                Surface(
                                                                    shape = RoundedCornerShape(6.dp),
                                                                    color = SoftMintAccent
                                                                ) {
                                                                    Row(
                                                                        modifier = Modifier.padding(horizontal = 4.dp, vertical = 2.dp),
                                                                        verticalAlignment = Alignment.CenterVertically
                                                                    ) {
                                                                        Icon(Icons.Default.Check, contentDescription = null, tint = DarkTealPrimary, modifier = Modifier.size(10.dp))
                                                                        Spacer(modifier = Modifier.width(2.dp))
                                                                        Text("Onaylı", fontSize = 8.sp, fontWeight = FontWeight.Bold, color = DarkTealPrimary)
                                                                    }
                                                                }
                                                            }
                                                            Text(
                                                                text = psychologist.specialty,
                                                                fontSize = 12.sp,
                                                                fontWeight = FontWeight.Medium,
                                                                color = DarkTealPrimary,
                                                                modifier = Modifier.padding(vertical = 2.dp)
                                                            )
                                                            Text(
                                                                text = psychologist.bio,
                                                                fontSize = 11.sp,
                                                                color = LoginSecondaryText,
                                                                maxLines = 2,
                                                                overflow = TextOverflow.Ellipsis
                                                            )
                                                        }
                                                    }
                                                }
                                            }
                                        }

                                        PremiumButton(
                                            onClick = { currentStep = 2 },
                                            enabled = selectedPsychologist != null,
                                            modifier = Modifier.fillMaxWidth().padding(bottom = 16.dp),
                                            cornerRadius = 16.dp,
                                            height = 48.dp
                                        ) {
                                            Text("Devam Et", color = Color.White, fontWeight = FontWeight.Bold)
                                        }
                                    }
                                }
                            }
                        }
                    }
                    2 -> {
                        // Step 2: Select Date (Calendar Dialog UI)
                        Text(
                            text = "Tarih Seçin",
                            style = MaterialTheme.typography.titleMedium.copy(fontWeight = FontWeight.Bold),
                            color = LoginTextColor,
                            modifier = Modifier.padding(bottom = 12.dp)
                        )

                        Column(modifier = Modifier.weight(1f)) {
                            // Psychologist info card header
                            selectedPsychologist?.let { psychologist ->
                                Surface(
                                    modifier = Modifier.fillMaxWidth().padding(bottom = 20.dp),
                                    shape = RoundedCornerShape(12.dp),
                                    color = SoftMintAccent.copy(alpha = 0.3f),
                                    border = BorderStroke(1.dp, SoftMintAccent)
                                ) {
                                    Row(modifier = Modifier.padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
                                        Icon(Icons.Default.Person, contentDescription = null, tint = DarkTealPrimary)
                                        Spacer(modifier = Modifier.width(10.dp))
                                        Column {
                                            Text("${psychologist.title} ${psychologist.fullName ?: psychologist.username}", fontWeight = FontWeight.Bold, fontSize = 14.sp, color = LoginTextColor)
                                            Text(psychologist.specialty, fontSize = 11.sp, color = LoginSecondaryText)
                                        }
                                    }
                                }
                            }

                            // Interactive Calendar Trigger Box
                            Surface(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .clickable { showDatePicker = true }
                                    .padding(vertical = 8.dp),
                                shape = RoundedCornerShape(16.dp),
                                color = PremiumWhiteCard,
                                border = BorderStroke(1.dp, Color.LightGray.copy(alpha = 0.5f))
                            ) {
                                Row(
                                    modifier = Modifier.padding(20.dp),
                                    verticalAlignment = Alignment.CenterVertically,
                                    horizontalArrangement = Arrangement.SpaceBetween
                                ) {
                                    Row(verticalAlignment = Alignment.CenterVertically) {
                                        Icon(Icons.Default.DateRange, contentDescription = null, tint = DarkTealPrimary, modifier = Modifier.size(28.dp))
                                        Spacer(modifier = Modifier.width(16.dp))
                                        Column {
                                            Text("Randevu Tarihi", fontWeight = FontWeight.Bold, fontSize = 12.sp, color = LoginSecondaryText)
                                            Text(
                                                text = selectedDateMillis?.let { formatTurkishDate(it) } ?: "Tarih Seçilmedi",
                                                fontSize = 16.sp,
                                                fontWeight = FontWeight.SemiBold,
                                                color = if (selectedDateMillis != null) DarkTealPrimary else Color.LightGray
                                            )
                                        }
                                    }
                                    Icon(Icons.Default.KeyboardArrowRight, contentDescription = null, tint = LoginSecondaryText)
                                }
                            }

                            // Calendar dialog (Turkish local support and past dates disabled)
                            if (showDatePicker) {
                                val datePickerState = rememberDatePickerState(
                                    selectableDates = remember {
                                        object : SelectableDates {
                                            override fun isSelectableDate(utcTimeMillis: Long): Boolean {
                                                val todayStart = LocalDate.now()
                                                    .atStartOfDay(ZoneOffset.UTC)
                                                    .toInstant()
                                                    .toEpochMilli()
                                                return utcTimeMillis >= todayStart
                                            }
                                        }
                                    }
                                )

                                DatePickerDialog(
                                    onDismissRequest = { showDatePicker = false },
                                    confirmButton = {
                                        TextButton(
                                            onClick = {
                                                datePickerState.selectedDateMillis?.let { millis ->
                                                    selectedDateMillis = millis
                                                }
                                                showDatePicker = false
                                            }
                                        ) {
                                            Text("Seç", color = DarkTealPrimary, fontWeight = FontWeight.Bold)
                                        }
                                    },
                                    dismissButton = {
                                        TextButton(onClick = { showDatePicker = false }) {
                                            Text("İptal", color = LoginSecondaryText)
                                        }
                                    }
                                ) {
                                    DatePicker(state = datePickerState)
                                }
                            }

                            Spacer(modifier = Modifier.weight(1f))

                            Row(
                                modifier = Modifier.fillMaxWidth().padding(bottom = 16.dp),
                                horizontalArrangement = Arrangement.spacedBy(16.dp)
                            ) {
                                OutlinedButton(
                                    onClick = { currentStep = 1 },
                                    modifier = Modifier.weight(1f).height(48.dp),
                                    shape = RoundedCornerShape(16.dp),
                                    border = BorderStroke(1.5.dp, DarkTealPrimary),
                                    colors = ButtonDefaults.outlinedButtonColors(contentColor = DarkTealPrimary)
                                ) {
                                    Text("Geri", fontWeight = FontWeight.Bold)
                                }
                                PremiumButton(
                                    onClick = { currentStep = 3 },
                                    enabled = selectedDateMillis != null,
                                    modifier = Modifier.weight(1f),
                                    cornerRadius = 16.dp,
                                    height = 48.dp
                                ) {
                                    Text("Devam Et", color = Color.White, fontWeight = FontWeight.Bold)
                                }
                            }
                        }
                    }
                    3 -> {
                        // Step 3: Select Time
                        Text(
                            text = "Saat Seçin",
                            style = MaterialTheme.typography.titleMedium.copy(fontWeight = FontWeight.Bold),
                            color = LoginTextColor,
                            modifier = Modifier.padding(bottom = 12.dp)
                        )

                        Column(modifier = Modifier.weight(1f)) {
                            // Summary header
                            Surface(
                                modifier = Modifier.fillMaxWidth().padding(bottom = 20.dp),
                                shape = RoundedCornerShape(12.dp),
                                color = SoftMintAccent.copy(alpha = 0.3f),
                                border = BorderStroke(1.dp, SoftMintAccent)
                            ) {
                                Column(modifier = Modifier.padding(12.dp)) {
                                    Text("Uzman: ${selectedPsychologist?.title} ${selectedPsychologist?.fullName ?: selectedPsychologist?.username}", fontWeight = FontWeight.Bold, fontSize = 13.sp, color = LoginTextColor)
                                    Text("Tarih: ${selectedDateMillis?.let { formatTurkishDate(it) }}", fontSize = 12.sp, color = DarkTealPrimary, fontWeight = FontWeight.SemiBold)
                                }
                            }

                            Text("Müsait Zaman Dilimleri", fontSize = 12.sp, fontWeight = FontWeight.Bold, color = LoginSecondaryText, modifier = Modifier.padding(bottom = 12.dp))

                            val timeSlots = listOf("09:00", "10:00", "11:00", "13:00", "14:00", "15:00", "16:00")

                            // Display chips in structured rows
                            Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                                val row1 = timeSlots.take(4)
                                val row2 = timeSlots.drop(4)

                                Row(horizontalArrangement = Arrangement.spacedBy(10.dp), modifier = Modifier.fillMaxWidth()) {
                                    row1.forEach { slot ->
                                        val isSelected = selectedTime == slot
                                        val chipBg = if (isSelected) DarkTealPrimary else PremiumWhiteCard
                                        val chipBorder = if (isSelected) DarkTealPrimary else Color.LightGray.copy(alpha = 0.5f)
                                        val chipText = if (isSelected) Color.White else LoginTextColor

                                        Surface(
                                            modifier = Modifier.weight(1f).clickable { selectedTime = slot },
                                            shape = RoundedCornerShape(12.dp),
                                            color = chipBg,
                                            border = BorderStroke(1.dp, chipBorder)
                                        ) {
                                            Text(
                                                text = slot,
                                                color = chipText,
                                                fontWeight = FontWeight.Bold,
                                                fontSize = 13.sp,
                                                textAlign = TextAlign.Center,
                                                modifier = Modifier.padding(vertical = 12.dp)
                                            )
                                        }
                                    }
                                }

                                Row(horizontalArrangement = Arrangement.spacedBy(10.dp), modifier = Modifier.fillMaxWidth()) {
                                    row2.forEach { slot ->
                                        val isSelected = selectedTime == slot
                                        val chipBg = if (isSelected) DarkTealPrimary else PremiumWhiteCard
                                        val chipBorder = if (isSelected) DarkTealPrimary else Color.LightGray.copy(alpha = 0.5f)
                                        val chipText = if (isSelected) Color.White else LoginTextColor

                                        Surface(
                                            modifier = Modifier.weight(1f).clickable { selectedTime = slot },
                                            shape = RoundedCornerShape(12.dp),
                                            color = chipBg,
                                            border = BorderStroke(1.dp, chipBorder)
                                        ) {
                                            Text(
                                                text = slot,
                                                color = chipText,
                                                fontWeight = FontWeight.Bold,
                                                fontSize = 13.sp,
                                                textAlign = TextAlign.Center,
                                                modifier = Modifier.padding(vertical = 12.dp)
                                            )
                                        }
                                    }
                                    Spacer(modifier = Modifier.weight(1f))
                                }
                            }

                            Spacer(modifier = Modifier.weight(1f))

                            Row(
                                modifier = Modifier.fillMaxWidth().padding(bottom = 16.dp),
                                horizontalArrangement = Arrangement.spacedBy(16.dp)
                            ) {
                                OutlinedButton(
                                    onClick = { currentStep = 2 },
                                    modifier = Modifier.weight(1f).height(48.dp),
                                    shape = RoundedCornerShape(16.dp),
                                    border = BorderStroke(1.5.dp, DarkTealPrimary),
                                    colors = ButtonDefaults.outlinedButtonColors(contentColor = DarkTealPrimary)
                                ) {
                                    Text("Geri", fontWeight = FontWeight.Bold)
                                }
                                PremiumButton(
                                    onClick = { currentStep = 4 },
                                    enabled = selectedTime != null,
                                    modifier = Modifier.weight(1f),
                                    cornerRadius = 16.dp,
                                    height = 48.dp
                                ) {
                                    Text("Devam Et", color = Color.White, fontWeight = FontWeight.Bold)
                                }
                            }
                        }
                    }
                    4 -> {
                        // Step 4: Summary & Confirm
                        Text(
                            text = "Randevuyu Onayla",
                            style = MaterialTheme.typography.titleMedium.copy(fontWeight = FontWeight.Bold),
                            color = LoginTextColor,
                            modifier = Modifier.padding(bottom = 12.dp)
                        )

                        Column(modifier = Modifier.weight(1f)) {
                            // Summary Details Card
                            Surface(
                                modifier = Modifier.fillMaxWidth().padding(vertical = 8.dp),
                                shape = RoundedCornerShape(20.dp),
                                color = PremiumWhiteCard,
                                border = BorderStroke(1.dp, SoftMintAccent),
                                shadowElevation = 2.dp
                            ) {
                                Column(modifier = Modifier.padding(20.dp)) {
                                    Text("Randevu Özeti", fontWeight = FontWeight.Bold, fontSize = 16.sp, color = DarkTealPrimary)
                                    Spacer(modifier = Modifier.height(16.dp))

                                    Row(verticalAlignment = Alignment.CenterVertically) {
                                        Icon(Icons.Default.Person, contentDescription = null, tint = DarkTealPrimary, modifier = Modifier.size(20.dp))
                                        Spacer(modifier = Modifier.width(10.dp))
                                        Column {
                                            Text("Uzman Psikolog", fontSize = 11.sp, color = LoginSecondaryText, fontWeight = FontWeight.Bold)
                                            Text(
                                                text = "${selectedPsychologist?.title} ${selectedPsychologist?.fullName ?: selectedPsychologist?.username}",
                                                fontSize = 14.sp,
                                                fontWeight = FontWeight.Bold,
                                                color = LoginTextColor
                                            )
                                            Text(
                                                text = selectedPsychologist?.specialty ?: "",
                                                fontSize = 12.sp,
                                                color = LoginSecondaryText
                                            )
                                        }
                                    }

                                    Spacer(modifier = Modifier.height(16.dp))

                                    Row(verticalAlignment = Alignment.CenterVertically) {
                                        Icon(Icons.Default.DateRange, contentDescription = null, tint = DarkTealPrimary, modifier = Modifier.size(20.dp))
                                        Spacer(modifier = Modifier.width(10.dp))
                                        Column {
                                            Text("Görüşme Tarihi", fontSize = 11.sp, color = LoginSecondaryText, fontWeight = FontWeight.Bold)
                                            Text(
                                                text = selectedDateMillis?.let { formatTurkishDate(it) } ?: "",
                                                fontSize = 14.sp,
                                                fontWeight = FontWeight.Bold,
                                                color = LoginTextColor
                                            )
                                        }
                                    }

                                    Spacer(modifier = Modifier.height(16.dp))

                                    Row(verticalAlignment = Alignment.CenterVertically) {
                                        Icon(Icons.Default.Info, contentDescription = null, tint = DarkTealPrimary, modifier = Modifier.size(20.dp))
                                        Spacer(modifier = Modifier.width(10.dp))
                                        Column {
                                            Text("Görüşme Saati", fontSize = 11.sp, color = LoginSecondaryText, fontWeight = FontWeight.Bold)
                                            Text(
                                                text = selectedTime ?: "",
                                                fontSize = 14.sp,
                                                fontWeight = FontWeight.Bold,
                                                color = LoginTextColor
                                            )
                                        }
                                    }
                                }
                            }

                            Spacer(modifier = Modifier.height(16.dp))

                            // Show network or submission error
                            if (bookAppointmentState is Resource.Error) {
                                val err = (bookAppointmentState as Resource.Error).message ?: ""
                                val isConnection = err.contains("connect", ignoreCase = true) ||
                                        err.contains("resolve", ignoreCase = true) ||
                                        err.contains("network", ignoreCase = true) ||
                                        err.contains("bağlantı", ignoreCase = true)
                                val displayErr = if (isConnection) "Randevu oluşturmak için bağlantı gerekli." else err

                                Card(
                                    colors = CardDefaults.cardColors(containerColor = DangerRed.copy(alpha = 0.1f)),
                                    border = BorderStroke(1.dp, DangerRed),
                                    modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp)
                                ) {
                                    Text(
                                        text = displayErr,
                                        color = DangerRed,
                                        fontSize = 12.sp,
                                        fontWeight = FontWeight.SemiBold,
                                        modifier = Modifier.padding(12.dp)
                                    )
                                }
                            }

                            Spacer(modifier = Modifier.weight(1f))

                            Row(
                                modifier = Modifier.fillMaxWidth().padding(bottom = 16.dp),
                                horizontalArrangement = Arrangement.spacedBy(16.dp),
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                OutlinedButton(
                                    onClick = { currentStep = 3 },
                                    modifier = Modifier.weight(1f).height(48.dp),
                                    shape = RoundedCornerShape(16.dp),
                                    border = BorderStroke(1.5.dp, DarkTealPrimary),
                                    colors = ButtonDefaults.outlinedButtonColors(contentColor = DarkTealPrimary)
                                ) {
                                    Text("Geri", fontWeight = FontWeight.Bold)
                                }

                                val isLoading = bookAppointmentState is Resource.Loading
                                PremiumButton(
                                    onClick = {
                                        val psyUsername = selectedPsychologist?.username
                                        val dateStr = selectedDateMillis?.let { formatBackendDate(it) }
                                        val timeStr = selectedTime
                                        if (psyUsername != null && dateStr != null && timeStr != null) {
                                            viewModel.bookAppointment(psyUsername, dateStr, timeStr)
                                        }
                                    },
                                    enabled = !isLoading,
                                    modifier = Modifier.weight(1.5f),
                                    cornerRadius = 16.dp,
                                    height = 48.dp
                                ) {
                                    if (isLoading) {
                                        CircularProgressIndicator(color = Color.White, modifier = Modifier.size(24.dp))
                                    } else {
                                        Text("Randevuyu Onayla ve Oluştur", color = Color.White, fontWeight = FontWeight.Bold, fontSize = 12.sp)
                                    }
                                }
                            }
                        }
                    }
                }
            } else {
                // Tab 1: Randevularım (My Appointments)
                Text(
                    text = "Görüşmelerim",
                    style = MaterialTheme.typography.titleLarge.copy(fontWeight = FontWeight.Bold),
                    color = LoginTextColor,
                    modifier = Modifier.padding(bottom = 12.dp)
                )

                // Check for fetch updates warning/error
                if (fetchState is Resource.Error) {
                    val fetchErr = (fetchState as Resource.Error).message ?: ""
                    Card(
                        colors = CardDefaults.cardColors(containerColor = DangerRed.copy(alpha = 0.1f)),
                        border = BorderStroke(1.dp, DangerRed.copy(alpha = 0.5f)),
                        modifier = Modifier.fillMaxWidth().padding(bottom = 12.dp)
                    ) {
                        Row(modifier = Modifier.padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
                            Icon(Icons.Default.Warning, contentDescription = null, tint = DangerRed)
                            Spacer(modifier = Modifier.width(10.dp))
                            Text(
                                text = "Güncel randevular yüklenemedi: $fetchErr. Eski kayıtlar gösteriliyor olabilir.",
                                color = DangerRed,
                                fontSize = 11.sp,
                                fontWeight = FontWeight.Medium
                            )
                        }
                    }
                }

                if (allAppointments.isEmpty()) {
                    Box(modifier = Modifier.weight(1f).fillMaxWidth(), contentAlignment = Alignment.Center) {
                        Column(
                            horizontalAlignment = Alignment.CenterHorizontally,
                            verticalArrangement = Arrangement.Center,
                            modifier = Modifier.padding(24.dp)
                        ) {
                            Surface(
                                modifier = Modifier.size(80.dp),
                                shape = CircleShape,
                                color = Color.White.copy(alpha = 0.5f)
                            ) {
                                Box(contentAlignment = Alignment.Center) {
                                    Icon(Icons.Default.DateRange, contentDescription = null, tint = DarkTealPrimary, modifier = Modifier.size(40.dp))
                                }
                            }
                            Spacer(modifier = Modifier.height(24.dp))
                            Text(
                                text = "Planlanmış randevunuz bulunmamaktadır.",
                                fontSize = 15.sp,
                                fontWeight = FontWeight.Bold,
                                color = LoginTextColor,
                                textAlign = TextAlign.Center
                            )
                            Spacer(modifier = Modifier.height(8.dp))
                            Text(
                                text = "Dilediğiniz uzman psikologla randevu planlayarak ilk adımınızı atabilirsiniz.",
                                fontSize = 12.sp,
                                color = LoginSecondaryText,
                                textAlign = TextAlign.Center
                            )
                            Spacer(modifier = Modifier.height(24.dp))
                            PremiumButton(
                                onClick = { selectedTab = 0 },
                                cornerRadius = 16.dp,
                                height = 48.dp,
                                modifier = Modifier.fillMaxWidth(0.7f)
                            ) {
                                Text("Randevu Al", color = Color.White, fontWeight = FontWeight.Bold)
                            }
                        }
                    }
                } else {
                    LazyColumn(
                        modifier = Modifier.weight(1f).fillMaxWidth(),
                        verticalArrangement = Arrangement.spacedBy(16.dp),
                        contentPadding = PaddingValues(bottom = 24.dp)
                    ) {
                        items(allAppointments, key = { it.id }) { appointment ->
                            AppointmentCardItem(
                                appt = appointment,
                                onCancel = {
                                    viewModel.cancelAppointment(appointment.id)
                                }
                            )
                        }
                    }
                }
            }
        }
    }

    // Success confirmation dialog
    if (showSuccessDialog) {
        AlertDialog(
            onDismissRequest = {
                showSuccessDialog = false
                currentStep = 1
                selectedPsychologist = null
                selectedDateMillis = null
                selectedTime = null
                selectedTab = 1 // Switch to upcoming list
            },
            title = {
                Text(
                    text = "Randevunuz Başarıyla Alındı! 🎉",
                    fontWeight = FontWeight.Bold,
                    color = LoginTextColor
                )
            },
            text = {
                Column {
                    Text(
                        text = "Randevun oluşturuldu.",
                        fontSize = 14.sp,
                        color = LoginTextColor,
                        fontWeight = FontWeight.SemiBold
                    )
                    Spacer(modifier = Modifier.height(12.dp))
                    Surface(
                        color = SoftMintAccent.copy(alpha = 0.4f),
                        shape = RoundedCornerShape(12.dp),
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        Column(modifier = Modifier.padding(14.dp)) {
                            Text(
                                text = "Uzman: ${selectedPsychologist?.title} ${selectedPsychologist?.fullName ?: selectedPsychologist?.username}",
                                fontWeight = FontWeight.Bold,
                                fontSize = 12.sp,
                                color = DarkTealPrimary
                            )
                            Text(
                                text = "Tarih: ${selectedDateMillis?.let { formatTurkishDate(it) }}",
                                fontSize = 12.sp,
                                color = LoginTextColor
                            )
                            Text(
                                text = "Saat: $selectedTime",
                                fontSize = 12.sp,
                                color = LoginTextColor
                            )
                        }
                    }
                }
            },
            confirmButton = {
                Button(
                    onClick = {
                        showSuccessDialog = false
                        currentStep = 1
                        selectedPsychologist = null
                        selectedDateMillis = null
                        selectedTime = null
                        selectedTab = 1 // Switch to upcoming list
                    },
                    colors = ButtonDefaults.buttonColors(containerColor = DarkTealPrimary)
                ) {
                    Text("Harika", color = Color.White)
                }
            }
        )
    }
}

@Composable
fun AppointmentCardItem(appt: CachedAppointment, onCancel: () -> Unit) {
    val isCancelled = appt.status == "cancelled"
    val cardColor = if (isCancelled) Color(0xFFFEE2E2) else Color.White
    val borderStrokeColor = if (isCancelled) Color(0xFFFECACA) else SoftMintAccent.copy(alpha = 0.5f)

    Surface(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(24.dp),
        color = cardColor,
        border = BorderStroke(1.dp, borderStrokeColor),
        shadowElevation = 1.dp
    ) {
        Row(
            modifier = Modifier.padding(20.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Box(
                modifier = Modifier
                    .size(44.dp)
                    .clip(CircleShape)
                    .background(if (isCancelled) Color.White else SoftMintAccent.copy(alpha = 0.6f)),
                contentAlignment = Alignment.Center
            ) {
                Icon(
                    imageVector = if (isCancelled) Icons.Default.Close else Icons.Default.DateRange,
                    contentDescription = null,
                    tint = if (isCancelled) DangerRed else DarkTealPrimary,
                    modifier = Modifier.size(24.dp)
                )
            }
            Spacer(modifier = Modifier.width(16.dp))
            Column(modifier = Modifier.weight(1f)) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text(
                        text = appt.psychologistName,
                        fontSize = 14.sp,
                        fontWeight = FontWeight.Bold,
                        color = LoginTextColor,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                        modifier = Modifier.weight(1f)
                    )

                    Surface(
                        shape = RoundedCornerShape(8.dp),
                        color = if (isCancelled) Color(0xFFFCA5A5).copy(alpha = 0.3f) else SoftMintAccent
                    ) {
                        Text(
                            text = if (isCancelled) "İptal Edildi" else "Planlandı",
                            fontSize = 10.sp,
                            fontWeight = FontWeight.Bold,
                            color = if (isCancelled) DangerRed else DarkTealPrimary,
                            modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp)
                        )
                    }
                }
                Text(
                    text = "Uzmanlık Alanı: ${appt.psychologistSpecialty}",
                    fontSize = 11.sp,
                    color = LoginSecondaryText
                )
                Spacer(modifier = Modifier.height(4.dp))
                
                // Parse date formatting dynamically: if it's backend date format YYYY-MM-DD, try to make it look nicer
                val displayDate = if (appt.appointmentDate.contains("-")) {
                    try {
                        val parts = appt.appointmentDate.split("-")
                        if (parts.size == 3) {
                            val year = parts[0].toInt()
                            val month = parts[1].toInt()
                            val day = parts[2].toInt()
                            val monthTurkish = when (month) {
                                1 -> "Ocak"
                                2 -> "Şubat"
                                3 -> "Mart"
                                4 -> "Nisan"
                                5 -> "Mayıs"
                                6 -> "Haziran"
                                7 -> "Temmuz"
                                8 -> "Ağustos"
                                9 -> "Eylül"
                                10 -> "Ekim"
                                11 -> "Kasım"
                                12 -> "Aralık"
                                else -> ""
                            }
                            "$day $monthTurkish $year"
                        } else {
                            appt.appointmentDate
                        }
                    } catch (e: Exception) {
                        appt.appointmentDate
                    }
                } else {
                    appt.appointmentDate
                }

                Text(
                    text = "Tarih: $displayDate Saat: ${appt.appointmentTime}",
                    fontSize = 12.sp,
                    fontWeight = FontWeight.SemiBold,
                    color = DarkTealPrimary
                )

                if (!isCancelled) {
                    Spacer(modifier = Modifier.height(12.dp))
                    OutlinedButton(
                        onClick = onCancel,
                        modifier = Modifier.height(36.dp),
                        shape = RoundedCornerShape(12.dp),
                        border = BorderStroke(1.dp, Color(0xFFDC2626)),
                        colors = ButtonDefaults.outlinedButtonColors(contentColor = Color(0xFFDC2626)),
                        contentPadding = PaddingValues(horizontal = 16.dp, vertical = 0.dp)
                    ) {
                        Text("Randevuyu İptal Et", fontSize = 12.sp, fontWeight = FontWeight.Bold)
                    }
                }
            }
        }
    }
}
