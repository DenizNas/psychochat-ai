package com.psikochat.app.ui.home

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
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
import androidx.compose.material3.*
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
                        val items = scheduleState.data ?: emptyList()
                        if (items.isEmpty()) {
                            // Empty State
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
                            // Sorted Chronological List
                            LazyColumn(
                                modifier = Modifier
                                    .weight(1f)
                                    .fillMaxWidth(),
                                verticalArrangement = Arrangement.spacedBy(16.dp),
                                contentPadding = PaddingValues(bottom = 24.dp)
                            ) {
                                items(items, key = { it.title + "_" + it.scheduledFor }) { item ->
                                    InterventionCard(item = item, onClick = { selectedIntervention = item })
                                }
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
