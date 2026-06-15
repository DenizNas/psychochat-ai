package com.psikochat.app.ui.home

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowLeft
import androidx.compose.material.icons.filled.Info
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material.icons.filled.DateRange
import androidx.compose.material.icons.filled.Close
import androidx.compose.material3.*
import androidx.compose.material3.TabRowDefaults.tabIndicatorOffset
import androidx.compose.material3.pulltorefresh.*

import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.input.nestedscroll.nestedScroll
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
import com.psikochat.app.data.model.Resource
import com.psikochat.app.data.model.ScheduledIntervention
import com.psikochat.app.data.model.WellnessPlanResponse
import com.psikochat.app.data.repository.WellnessScheduleRepository
import com.psikochat.app.ui.theme.*

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun WellnessScheduleScreen(navController: NavController, tokenManager: TokenManager) {
    val api = RetrofitClient.create(tokenManager)
    val repository = WellnessScheduleRepository(api)
    val factory = object : ViewModelProvider.Factory {
        override fun <T : ViewModel> create(modelClass: Class<T>): T {
            return WellnessScheduleViewModel(repository) as T
        }
    }
    val viewModel: WellnessScheduleViewModel = viewModel(factory = factory)

    // Appointment ViewModel Integration
    val context = androidx.compose.ui.platform.LocalContext.current
    val db = com.psikochat.app.data.local.AppDatabase.getInstance(context)
    val appointmentRepository = com.psikochat.app.data.repository.AppointmentRepository(api, db.appointmentDao(), context)
    val apptFactory = object : ViewModelProvider.Factory {
        @Suppress("UNCHECKED_CAST")
        override fun <T : ViewModel> create(modelClass: Class<T>): T {
            return AppointmentViewModel(appointmentRepository) as T
        }
    }
    val apptViewModel: AppointmentViewModel = viewModel(factory = apptFactory)
    val allAppointments by apptViewModel.allAppointments.collectAsState()

    var selectedTab by remember { mutableStateOf(0) }

    val scheduleState by viewModel.scheduleState.collectAsState()
    val refreshState by viewModel.refreshState.collectAsState()
    
    val snackbarHostState = remember { SnackbarHostState() }
    var selectedIntervention by remember { mutableStateOf<ScheduledIntervention?>(null) }
    
    // Pull to Refresh State
    val pullToRefreshState = rememberPullToRefreshState()
    var isRefreshing by remember { mutableStateOf(false) }

    LaunchedEffect(refreshState) {
        if (refreshState is Resource.Loading) {
            isRefreshing = true
        } else {
            isRefreshing = false
            if (refreshState is Resource.Error) {
                snackbarHostState.showSnackbar(refreshState?.message ?: "Yenileme başarısız")
                viewModel.clearRefreshState()
            } else if (refreshState is Resource.Success) {
                snackbarHostState.showSnackbar("Wellness programınız güncellendi")
                viewModel.clearRefreshState()
            }
        }
    }

    LaunchedEffect(isRefreshing) {
        if (isRefreshing) {
            pullToRefreshState.startRefresh()
        } else {
            pullToRefreshState.endRefresh()
        }
    }

    Scaffold(
        snackbarHost = { SnackbarHost(snackbarHostState) },
        topBar = {
            CenterAlignedTopAppBar(
                title = {
                    Text(
                        "Wellness Planım",
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
                actions = {
                    IconButton(
                        onClick = { navController.navigate("wellness_report") }
                    ) {
                        Icon(Icons.Default.Info, contentDescription = "Gelişim Raporum", tint = LoginTextColor)
                    }
                    IconButton(
                        onClick = { viewModel.refreshSchedule() },
                        enabled = !isRefreshing
                    ) {
                        Icon(Icons.Default.Refresh, contentDescription = "Yenile", tint = LoginTextColor)
                    }
                },
                colors = TopAppBarDefaults.centerAlignedTopAppBarColors(containerColor = Color.Transparent)
            )
        },
        containerColor = LoginBackground
    ) { padding ->
        Box(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .nestedScroll(pullToRefreshState.nestedScrollConnection)
        ) {
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(horizontal = 24.dp),
                horizontalAlignment = Alignment.CenterHorizontally
            ) {
                Spacer(modifier = Modifier.height(12.dp))
                
                // Timezone Info Badge
                Surface(
                    color = Color.White.copy(alpha = 0.6f),
                    shape = RoundedCornerShape(12.dp)
                ) {
                    Row(
                        modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Box(
                            modifier = Modifier
                                .size(8.dp)
                                .clip(CircleShape)
                                .background(LoginButton)
                        )
                        Spacer(modifier = Modifier.width(8.dp))
                        Text(
                            "Yerel Zaman Dilimi: Europe/Istanbul (UTC+3)",
                            fontSize = 11.sp,
                            fontWeight = FontWeight.Medium,
                            color = LoginTextColor
                        )
                    }
                }
                
                Spacer(modifier = Modifier.height(16.dp))

                TabRow(
                    selectedTabIndex = selectedTab,
                    containerColor = Color.Transparent,
                    contentColor = DarkTealPrimary,
                    indicator = { tabPositions ->
                        TabRowDefaults.SecondaryIndicator(
                            modifier = Modifier.tabIndicatorOffset(tabPositions[selectedTab]),
                            color = DarkTealPrimary
                        )
                    },
                    modifier = Modifier.fillMaxWidth().padding(vertical = 8.dp)
                ) {
                    Tab(
                        selected = selectedTab == 0,
                        onClick = { selectedTab = 0 },
                        text = { Text("Wellness Planım", fontWeight = FontWeight.Bold, fontSize = 14.sp) }
                    )
                    Tab(
                        selected = selectedTab == 1,
                        onClick = { selectedTab = 1 },
                        text = { Text("Randevularım", fontWeight = FontWeight.Bold, fontSize = 14.sp) }
                    )
                }

                Spacer(modifier = Modifier.height(16.dp))

                if (selectedTab == 0) {
                    when (scheduleState) {
                        is Resource.Loading -> {
                            Box(modifier = Modifier.weight(1f), contentAlignment = Alignment.Center) {
                                CircularProgressIndicator(color = LoginButton)
                            }
                        }
                        is Resource.Error -> {
                            Column(
                                modifier = Modifier
                                    .weight(1f)
                                    .padding(24.dp),
                                horizontalAlignment = Alignment.CenterHorizontally,
                                verticalArrangement = Arrangement.Center
                            ) {
                                Icon(Icons.Default.Warning, contentDescription = null, tint = DangerRed, modifier = Modifier.size(48.dp))
                                Spacer(modifier = Modifier.height(16.dp))
                                Text(
                                    scheduleState.message ?: "Program yüklenemedi",
                                    textAlign = TextAlign.Center,
                                    color = LoginTextColor
                                )
                                Spacer(modifier = Modifier.height(16.dp))
                                Button(
                                    onClick = { viewModel.loadSchedule() },
                                    colors = ButtonDefaults.buttonColors(containerColor = LoginButton)
                                ) {
                                    Text("Tekrar Dene")
                                }
                            }
                        }
                        is Resource.Success -> {
                            val plan = scheduleState.data
                            if (plan == null) {
                                // Empty State fallback
                                Column(
                                    modifier = Modifier
                                        .weight(1f)
                                        .padding(32.dp),
                                    horizontalAlignment = Alignment.CenterHorizontally,
                                    verticalArrangement = Arrangement.Center
                                ) {
                                    Surface(
                                        modifier = Modifier.size(80.dp),
                                        shape = CircleShape,
                                        color = Color.White.copy(alpha = 0.5f)
                                    ) {
                                        Box(contentAlignment = Alignment.Center) {
                                            Icon(Icons.Default.Info, contentDescription = null, tint = LoginButton, modifier = Modifier.size(40.dp))
                                        }
                                    }
                                    Spacer(modifier = Modifier.height(24.dp))
                                    Text(
                                        "Şu an planlanmış wellness önerisi bulunmuyor.",
                                        textAlign = TextAlign.Center,
                                        fontSize = 15.sp,
                                        fontWeight = FontWeight.Medium,
                                        color = LoginSecondaryText
                                    )
                                    Spacer(modifier = Modifier.height(8.dp))
                                    Text(
                                        "Duygu geçmişinize veya gün içindeki durumunuza göre wellness planınız otomatik olarak şekillenecektir.",
                                        textAlign = TextAlign.Center,
                                        fontSize = 12.sp,
                                        color = LoginSecondaryText.copy(alpha = 0.8f)
                                    )
                                }
                            } else {
                                val dailyGoals = plan.dailyGoals
                                val nextAppt = allAppointments.firstOrNull { it.status == "scheduled" }

                                LazyColumn(
                                    modifier = Modifier
                                        .weight(1f)
                                        .fillMaxWidth(),
                                    verticalArrangement = Arrangement.spacedBy(16.dp),
                                    contentPadding = PaddingValues(bottom = 24.dp)
                                ) {
                                    // 1. Today's Focus Card
                                    item {
                                        Text(
                                            "Günün Odağı",
                                            fontSize = 14.sp,
                                            fontWeight = FontWeight.Bold,
                                            color = LoginTextColor,
                                            modifier = Modifier.padding(start = 4.dp, bottom = 4.dp)
                                        )
                                        Card(
                                            modifier = Modifier.fillMaxWidth(),
                                            shape = RoundedCornerShape(20.dp),
                                            colors = CardDefaults.cardColors(containerColor = SoftMintLight),
                                            border = BorderStroke(1.dp, SoftMintAccent.copy(alpha = 0.5f))
                                        ) {
                                            Row(
                                                modifier = Modifier.padding(18.dp),
                                                verticalAlignment = Alignment.CenterVertically
                                            ) {
                                                Box(
                                                    modifier = Modifier
                                                        .size(40.dp)
                                                        .clip(CircleShape)
                                                        .background(Color.White),
                                                    contentAlignment = Alignment.Center
                                                ) {
                                                    Icon(
                                                        imageVector = Icons.Default.Info,
                                                        contentDescription = null,
                                                        tint = DarkTealPrimary,
                                                        modifier = Modifier.size(20.dp)
                                                    )
                                                }
                                                Spacer(modifier = Modifier.width(14.dp))
                                                Column {
                                                    Text(
                                                        text = plan.todayFocus,
                                                        fontSize = 13.sp,
                                                        fontWeight = FontWeight.Medium,
                                                        color = LoginTextColor,
                                                        lineHeight = 18.sp
                                                    )
                                                }
                                            }
                                        }
                                    }

                                    // 2. AI Wellness Summary / Reflection Card
                                    item {
                                        Text(
                                            "Yapay Zeka Wellness Özeti",
                                            fontSize = 14.sp,
                                            fontWeight = FontWeight.Bold,
                                            color = LoginTextColor,
                                            modifier = Modifier.padding(start = 4.dp, bottom = 4.dp)
                                        )
                                        Card(
                                            modifier = Modifier.fillMaxWidth(),
                                            shape = RoundedCornerShape(20.dp),
                                            colors = CardDefaults.cardColors(containerColor = PremiumWhiteCard),
                                            border = BorderStroke(1.dp, SoftMintAccent.copy(alpha = 0.5f))
                                        ) {
                                            Column(modifier = Modifier.padding(18.dp)) {
                                                Row(verticalAlignment = Alignment.CenterVertically) {
                                                    Text("✨", fontSize = 18.sp)
                                                    Spacer(modifier = Modifier.width(10.dp))
                                                    Text(
                                                        text = "İyi Oluş Analizi",
                                                        fontWeight = FontWeight.Bold,
                                                        fontSize = 14.sp,
                                                        color = LoginTextColor
                                                    )
                                                }
                                                Spacer(modifier = Modifier.height(8.dp))
                                                Text(
                                                    text = plan.aiWellnessSummary,
                                                    fontSize = 12.sp,
                                                    color = LoginSecondaryText,
                                                    lineHeight = 18.sp
                                                )
                                            }
                                        }
                                    }

                                    // 3. Emotional Trend Card
                                    item {
                                        Text(
                                            "Duygu Analizi Özeti",
                                            fontSize = 14.sp,
                                            fontWeight = FontWeight.Bold,
                                            color = LoginTextColor,
                                            modifier = Modifier.padding(start = 4.dp, bottom = 4.dp)
                                        )
                                        Card(
                                            modifier = Modifier.fillMaxWidth(),
                                            shape = RoundedCornerShape(20.dp),
                                            colors = CardDefaults.cardColors(containerColor = PremiumWhiteCard),
                                            border = BorderStroke(1.dp, SoftMintAccent.copy(alpha = 0.5f))
                                        ) {
                                            Row(
                                                modifier = Modifier.padding(16.dp),
                                                verticalAlignment = Alignment.CenterVertically
                                            ) {
                                                Text("📊", fontSize = 18.sp)
                                                Spacer(modifier = Modifier.width(12.dp))
                                                Text(
                                                    text = plan.emotionalTrendSummary,
                                                    fontSize = 12.sp,
                                                    color = LoginSecondaryText,
                                                    lineHeight = 17.sp
                                                )
                                            }
                                        }
                                    }

                                    // 4. Appointment guidance card
                                    if (nextAppt != null) {
                                        item {
                                            Text(
                                                "Yaklaşan Görüşme Rehberi",
                                                fontSize = 14.sp,
                                                fontWeight = FontWeight.Bold,
                                                color = LoginTextColor,
                                                modifier = Modifier.padding(start = 4.dp, bottom = 4.dp)
                                            )
                                            Card(
                                                modifier = Modifier.fillMaxWidth(),
                                                shape = RoundedCornerShape(20.dp),
                                                colors = CardDefaults.cardColors(containerColor = Color(0xFFFFFBEB)), // Warm golden tint
                                                border = BorderStroke(1.dp, Color(0xFFFDE68A))
                                            ) {
                                                Column(modifier = Modifier.padding(18.dp)) {
                                                    Row(verticalAlignment = Alignment.CenterVertically) {
                                                        Icon(
                                                            imageVector = Icons.Default.DateRange,
                                                            contentDescription = null,
                                                            tint = Color(0xFFD97706),
                                                            modifier = Modifier.size(18.dp)
                                                        )
                                                        Spacer(modifier = Modifier.width(8.dp))
                                                        Text(
                                                            text = "${nextAppt.psychologistName} ile Randevu",
                                                            fontWeight = FontWeight.Bold,
                                                            fontSize = 13.sp,
                                                            color = Color(0xFF92400E)
                                                        )
                                                    }
                                                    Spacer(modifier = Modifier.height(8.dp))
                                                    Text(
                                                        text = "Yaklaşan Randevu: ${nextAppt.psychologistName} ile ${nextAppt.appointmentDate} saat ${nextAppt.appointmentTime}'te randevunuz bulunuyor. Görüşme öncesi duygularınızı ve sormak istediklerinizi not etmek görüşmenizi daha verimli kılabilir.",
                                                        fontSize = 12.sp,
                                                        color = Color(0xFF92400E),
                                                        lineHeight = 18.sp
                                                    )
                                                }
                                            }
                                        }
                                    }

                                    // 5. Daily Goals
                                    item {
                                        Text(
                                            "Günlük Wellness Önerileri",
                                            fontSize = 14.sp,
                                            fontWeight = FontWeight.Bold,
                                            color = LoginTextColor,
                                            modifier = Modifier.padding(start = 4.dp, bottom = 4.dp)
                                        )
                                    }

                                    if (dailyGoals.isEmpty()) {
                                        item {
                                            Surface(
                                                modifier = Modifier.fillMaxWidth(),
                                                shape = RoundedCornerShape(16.dp),
                                                color = Color.White.copy(alpha = 0.5f)
                                            ) {
                                                Text(
                                                    text = "Şu an planlanmış bir wellness adımı bulunmuyor.",
                                                    modifier = Modifier.padding(16.dp),
                                                    fontSize = 12.sp,
                                                    color = LoginSecondaryText,
                                                    textAlign = TextAlign.Center
                                                )
                                            }
                                        }
                                    } else {
                                        items(dailyGoals, key = { goal -> goal.title + "_" + goal.scheduledFor }) { goal ->
                                            val intervention = ScheduledIntervention(
                                                type = goal.type,
                                                priority = goal.priority,
                                                scheduledFor = goal.scheduledFor,
                                                status = goal.status,
                                                title = goal.title,
                                                description = goal.description
                                            )
                                            InterventionCard(item = intervention, onClick = { selectedIntervention = intervention })
                                        }
                                    }
                                }
                            }
                        }
                    }
                } else {
                    if (allAppointments.isEmpty()) {
                        Column(
                            modifier = Modifier
                                .weight(1f)
                                .padding(32.dp),
                            horizontalAlignment = Alignment.CenterHorizontally,
                            verticalArrangement = Arrangement.Center
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
                                "Şu an planlanmış bir uzman randevunuz bulunmuyor.",
                                textAlign = TextAlign.Center,
                                fontSize = 15.sp,
                                fontWeight = FontWeight.Medium,
                                color = LoginSecondaryText
                            )
                            Spacer(modifier = Modifier.height(8.dp))
                            Text(
                                "Destek sayfamızdan dilediğiniz uzman psikologla randevu planlayabilirsiniz.",
                                textAlign = TextAlign.Center,
                                fontSize = 12.sp,
                                color = LoginSecondaryText.copy(alpha = 0.8f)
                            )
                            Spacer(modifier = Modifier.height(24.dp))
                            // Premium button that navigates directly to therapy route
                            com.psikochat.app.ui.components.PremiumButton(
                                onClick = { navController.navigate("therapy") },
                                cornerRadius = 16.dp,
                                height = 48.dp,
                                modifier = Modifier.fillMaxWidth(0.7f)
                            ) {
                                Text("Psikolog Bul", color = Color.White)
                            }
                        }
                    } else {
                        LazyColumn(
                            modifier = Modifier
                                .weight(1f)
                                .fillMaxWidth(),
                            verticalArrangement = Arrangement.spacedBy(16.dp),
                            contentPadding = PaddingValues(bottom = 24.dp)
                        ) {
                            items(allAppointments, key = { it.id }) { appointment ->
                                AppointmentCard(
                                    appt = appointment,
                                    onCancel = {
                                        apptViewModel.cancelAppointment(appointment.id)
                                    }
                                )
                            }
                        }
                    }
                }
            }

            // Pull to Refresh Indicator
            PullToRefreshContainer(
                state = pullToRefreshState,
                modifier = Modifier.align(Alignment.TopCenter),
                contentColor = LoginButton,
                containerColor = Color.White
            )
        }
    }

    // Gentle Empathetic Helper Dialog (Non-Authoritative)
    if (selectedIntervention != null) {
        val item = selectedIntervention!!
        AlertDialog(
            onDismissRequest = { selectedIntervention = null },
            title = {
                Text(
                    item.title,
                    fontWeight = FontWeight.Bold,
                    color = LoginTextColor
                )
            },
            text = {
                Column {
                    Text(
                        item.description,
                        style = MaterialTheme.typography.bodyMedium,
                        color = LoginSecondaryText
                    )
                    Spacer(modifier = Modifier.height(16.dp))
                    Text(
                        "Planlanan Zaman: ${item.scheduledFor.replace("T", " ")}",
                        fontSize = 12.sp,
                        fontWeight = FontWeight.SemiBold,
                        color = LoginButton
                    )
                    Spacer(modifier = Modifier.height(8.dp))
                    Text(
                        "Bu öneri tamamen destek amaçlıdır. Kendinizi nasıl hissettiğinize bağlı olarak uygulamak veya geçmek tamamen sizin tercihinizdir.",
                        fontSize = 11.sp,
                        color = LoginSecondaryText.copy(alpha = 0.7f)
                    )
                }
            },
            confirmButton = {
                Button(
                    onClick = { selectedIntervention = null },
                    colors = ButtonDefaults.buttonColors(containerColor = LoginButton)
                ) {
                    Text("Teşekkürler")
                }
            }
        )
    }
}

@Composable
fun InterventionCard(item: ScheduledIntervention, onClick: () -> Unit) {
    val isCrisis = item.type == "priority_support"
    val cardColor = when {
        isCrisis -> Color(0xFFFEE2E2) // Soft support pink/crimson
        item.priority == "high" -> Color(0xFFFFEDD5) // Soft orange/peach
        item.priority == "medium" -> Color(0xFFFFFBEB) // Soft warm gold
        else -> Color.White.copy(alpha = 0.9f)
    }

    val iconColor = when {
        isCrisis -> DangerRed
        item.priority == "high" -> Color(0xFFF97316)
        item.priority == "medium" -> Color(0xFFD97706)
        else -> LoginButton
    }

    Surface(
        modifier = Modifier
            .fillMaxWidth()
            .clickable { onClick() },
        shape = RoundedCornerShape(24.dp),
        color = cardColor,
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
                    .background(Color.White),
                contentAlignment = Alignment.Center
            ) {
                Icon(
                    Icons.Default.Info,
                    contentDescription = null,
                    tint = iconColor,
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
                        text = when (item.type) {
                            "breathing_break" -> "Nefes Molası"
                            "short_walk" -> "Kısa Yürüyüş"
                            "social_connection" -> "Sosyal Bağlantı"
                            "grounding_exercise" -> "Topraklanma Egzersizi"
                            "positive_reflection" -> "Olumlu Düşünce"
                            "priority_support" -> "Öncelikli Destek"
                            "hydration_reminder" -> "Su Hatırlatıcı"
                            "sleep_reminder" -> "Uyku Rutini"
                            else -> "Wellness Önerisi"
                        },
                        fontSize = 14.sp,
                        fontWeight = FontWeight.Bold,
                        color = LoginTextColor
                    )
                    
                    // Format time
                    val timeStr = try {
                        val parts = item.scheduledFor.split("T")
                        if (parts.size > 1) {
                            parts[1].substring(0, 5)
                        } else ""
                    } catch (e: Exception) {
                        ""
                    }
                    if (timeStr.isNotEmpty()) {
                        Text(
                            text = timeStr,
                            fontSize = 12.sp,
                            fontWeight = FontWeight.Bold,
                            color = LoginSecondaryText
                        )
                    }
                }
                Spacer(modifier = Modifier.height(4.dp))
                Text(
                    text = item.title,
                    fontSize = 12.sp,
                    color = LoginSecondaryText,
                    maxLines = 1
                )
            }
        }
    }
}

// TODO: Replace local appointment storage with backend appointment API when available.
@Composable
fun AppointmentCard(appt: com.psikochat.app.data.local.entity.CachedAppointment, onCancel: () -> Unit) {
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
                        color = LoginTextColor
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
                Text(
                    text = "Tarih: ${appt.appointmentDate} Saat: ${appt.appointmentTime}",
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
