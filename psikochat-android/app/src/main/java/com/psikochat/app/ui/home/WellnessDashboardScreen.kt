package com.psikochat.app.ui.home

import android.content.Intent
import android.net.Uri
import androidx.compose.animation.*
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material.icons.automirrored.filled.ArrowForward
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowLeft
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.platform.LocalContext
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
import com.psikochat.app.data.model.WellnessDashboardResponse
import com.psikochat.app.data.repository.WellnessDashboardRepository
import com.psikochat.app.ui.theme.*
import com.psikochat.app.ui.components.*

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun WellnessDashboardScreen(
    navController: NavController,
    tokenManager: TokenManager
) {
    val context = LocalContext.current
    val db = com.psikochat.app.data.local.AppDatabase.getInstance(context)
    val syncManager = com.psikochat.app.data.sync.SyncManager.getInstance(context)
    val api = RetrofitClient.create(tokenManager)
    val repository = WellnessDashboardRepository(api, db.dashboardDao())
    val progressRepository = com.psikochat.app.data.repository.ProgressRepository(db.scoreSnapshotDao())
    val factory = object : ViewModelProvider.Factory {
        @Suppress("UNCHECKED_CAST")
        override fun <T : ViewModel> create(modelClass: Class<T>): T {
            return WellnessDashboardViewModel(repository, tokenManager, syncManager, progressRepository) as T
        }
    }
    val viewModel: WellnessDashboardViewModel = viewModel(factory = factory)

    val dashboardState by viewModel.dashboardState.collectAsState()
    val selectedDays by viewModel.selectedDays.collectAsState()
    val scrollState = rememberScrollState()

    val usernameFlow = remember { tokenManager.getUsername() }
    val username by usernameFlow.collectAsState(initial = "")

    val messagesFlow = remember(username) { db.chatDao().getAllCachedMessages(username) }
    val messages by messagesFlow.collectAsState(initial = emptyList())
    val moodsFlow = remember(username) { db.moodJournalDao().getCachedMoodJournals(username) }
    val moods by moodsFlow.collectAsState(initial = emptyList())

    Scaffold(
        topBar = {
            CenterAlignedTopAppBar(
                title = {
                    Text(
                        "Zihinsel Sağlık Paneli",
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
                    IconButton(onClick = { viewModel.loadDashboard() }) {
                        Icon(Icons.Default.Refresh, contentDescription = "Yenile", tint = LoginTextColor)
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
                .verticalScroll(scrollState)
                .padding(horizontal = 20.dp)
        ) {
            Spacer(modifier = Modifier.height(8.dp))

            // 1. Timeframe Selection Toggle
            Surface(
                modifier = Modifier
                    .fillMaxWidth()
                    .height(48.dp),
                shape = RoundedCornerShape(24.dp),
                color = Color.White.copy(alpha = 0.5f)
            ) {
                Row(
                    modifier = Modifier.fillMaxSize().padding(4.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    val is7Days = selectedDays == 7
                    Box(
                        modifier = Modifier
                            .weight(1f)
                            .fillMaxHeight()
                            .clip(RoundedCornerShape(20.dp))
                            .background(if (is7Days) LoginButton else Color.Transparent)
                            .clickable { viewModel.selectDays(7) },
                        contentAlignment = Alignment.Center
                    ) {
                        Text(
                            "7 Günlük",
                            fontSize = 13.sp,
                            fontWeight = FontWeight.Bold,
                            color = if (is7Days) Color.White else LoginSecondaryText
                        )
                    }

                    Box(
                        modifier = Modifier
                            .weight(1f)
                            .fillMaxHeight()
                            .clip(RoundedCornerShape(20.dp))
                            .background(if (!is7Days) LoginButton else Color.Transparent)
                            .clickable { viewModel.selectDays(30) },
                        contentAlignment = Alignment.Center
                    ) {
                        Text(
                            "30 Günlük",
                            fontSize = 13.sp,
                            fontWeight = FontWeight.Bold,
                            color = if (!is7Days) Color.White else LoginSecondaryText
                        )
                    }
                }
            }

            Spacer(modifier = Modifier.height(20.dp))

            // 2. İstikrar Takibi — Always visible, calculated purely from local Room data
            val streakSummary = remember(messages, moods) {
                StreakEngine.computeStreakSummary(messages, moods)
            }

            Text(
                "İstikrar Takibi",
                fontSize = 14.sp,
                fontWeight = FontWeight.Bold,
                color = LoginTextColor,
                modifier = Modifier.padding(start = 4.dp, bottom = 12.dp)
            )

            // Encouragement / Active Streak Banner
            Surface(
                modifier = Modifier.fillMaxWidth().padding(bottom = 16.dp),
                shape = RoundedCornerShape(20.dp),
                color = PremiumWhiteCard,
                border = BorderStroke(1.dp, SoftMintAccent.copy(alpha = 0.5f))
            ) {
                Row(
                    modifier = Modifier.padding(16.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Box(
                        modifier = Modifier
                            .size(44.dp)
                            .clip(CircleShape)
                            .background(SoftMintLight),
                        contentAlignment = Alignment.Center
                    ) {
                        Text(
                            text = if (streakSummary.activeStreakDays == 0) "✨" else "🔥",
                            fontSize = 20.sp
                        )
                    }
                    Spacer(modifier = Modifier.width(14.dp))
                    Column {
                        Text(
                            text = streakSummary.label,
                            fontWeight = FontWeight.Bold,
                            fontSize = 16.sp,
                            color = LoginTextColor
                        )
                        Spacer(modifier = Modifier.height(2.dp))
                        Text(
                            text = streakSummary.encouragementText,
                            fontSize = 12.sp,
                            color = LoginSecondaryText,
                            lineHeight = 17.sp
                        )
                    }
                }
            }

            // 2×2 Streak Cards Grid
            Row(modifier = Modifier.fillMaxWidth()) {
                StreakStatCard(
                    title = "Günlük Seri",
                    value = streakSummary.activeStreakDays.toString(),
                    subtitle = "Aktif kullanım",
                    badge = "🔥",
                    modifier = Modifier.weight(1f)
                )
                Spacer(modifier = Modifier.width(12.dp))
                StreakStatCard(
                    title = "Sohbet Serisi",
                    value = streakSummary.chatStreakDays.toString(),
                    subtitle = "AI terapist",
                    badge = "💬",
                    modifier = Modifier.weight(1f)
                )
            }
            Spacer(modifier = Modifier.height(12.dp))
            Row(modifier = Modifier.fillMaxWidth()) {
                StreakStatCard(
                    title = "Ruh Hali Serisi",
                    value = streakSummary.moodStreakDays.toString(),
                    subtitle = "Duygu günlüğü",
                    badge = "📝",
                    modifier = Modifier.weight(1f)
                )
                Spacer(modifier = Modifier.width(12.dp))
                StreakStatCard(
                    title = "En Uzun Seri",
                    value = streakSummary.longestStreakDays.toString(),
                    subtitle = "Kişisel rekor",
                    badge = "🏆",
                    modifier = Modifier.weight(1f)
                )
            }

            Spacer(modifier = Modifier.height(24.dp))

            // Weekly Recap Banner — navigates to weekly_recap
            Surface(
                modifier = Modifier
                    .fillMaxWidth()
                    .clickable { navController.navigate("weekly_recap") },
                shape = RoundedCornerShape(20.dp),
                color = DarkTealPrimary,
                shadowElevation = 2.dp
            ) {
                Row(
                    modifier = Modifier.padding(horizontal = 20.dp, vertical = 14.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {
                    Column {
                        Text(
                            text = "Haftalık Özetimi Gör",
                            fontWeight = FontWeight.Bold,
                            fontSize = 15.sp,
                            color = Color.White
                        )
                        Text(
                            text = "Geçen 7 günü tek bakışta incele",
                            fontSize = 12.sp,
                            color = Color.White.copy(alpha = 0.7f)
                        )
                    }
                    Icon(
                        imageVector = Icons.AutoMirrored.Filled.ArrowForward,
                        contentDescription = null,
                        tint = Color.White,
                        modifier = Modifier.size(20.dp)
                    )
                }
            }

            Spacer(modifier = Modifier.height(24.dp))

            // 3. Backend Dashboard State
            Box(
                modifier = Modifier
                    .fillMaxWidth()
            ) {
                when (val state = dashboardState) {
                    is Resource.Loading -> {
                        Box(
                            modifier = Modifier.fillMaxWidth().height(200.dp),
                            contentAlignment = Alignment.Center
                        ) {
                            CircularProgressIndicator(color = LoginButton)
                        }
                    }
                    is Resource.Error -> {
                        if (state.isPremiumRequired) {
                            PremiumLockedCard(
                                title = "Premium Analiz",
                                description = "Gelişmiş iyi oluş analizleri ve kişisel raporlar Premium üyelikle açılır.",
                                ctaText = "Premium'a Geç",
                                onUpgradeClick = { navController.navigate("payment_methods") },
                                modifier = Modifier.padding(vertical = 16.dp)
                            )
                        } else {
                            Column(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .padding(24.dp),
                                horizontalAlignment = Alignment.CenterHorizontally,
                                verticalArrangement = Arrangement.Center
                            ) {
                                Icon(Icons.Default.Warning, contentDescription = null, tint = DangerRed, modifier = Modifier.size(48.dp))
                                Spacer(modifier = Modifier.height(16.dp))
                                Text(
                                    state.message ?: "Dashboard verileri yüklenirken hata oluştu.",
                                    textAlign = TextAlign.Center,
                                    color = LoginTextColor
                                )
                                Spacer(modifier = Modifier.height(16.dp))
                                Button(
                                    onClick = { viewModel.loadDashboard() },
                                    colors = ButtonDefaults.buttonColors(containerColor = LoginButton)
                                ) {
                                    Text("Yeniden Dene")
                                }
                            }
                        }
                    }
                    is Resource.Success -> {
                        val response = state.data
                        if (response == null) {
                            Box(
                                modifier = Modifier.fillMaxWidth().height(120.dp),
                                contentAlignment = Alignment.Center
                            ) {
                                Text("Veri bulunamadı.", color = LoginTextColor)
                            }
                        } else {
                            val overview = response.overview
                            val scoreObj = response.wellnessScore
                            val sections = response.sections

                            Column(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .padding(bottom = 24.dp)
                            ) {
                                // Stale cache badge
                                if (!response.lastUpdated.isNullOrBlank()) {
                                    Card(
                                        modifier = Modifier.fillMaxWidth().padding(bottom = 16.dp),
                                        shape = RoundedCornerShape(16.dp),
                                        colors = CardDefaults.cardColors(containerColor = Color(0xFFFFF3E0))
                                    ) {
                                        Row(
                                            modifier = Modifier.padding(12.dp),
                                            verticalAlignment = Alignment.CenterVertically
                                        ) {
                                            Icon(Icons.Default.Warning, contentDescription = null, tint = Color(0xFFE65100), modifier = Modifier.size(16.dp))
                                            Spacer(modifier = Modifier.width(8.dp))
                                            Text(
                                                text = "Son Güncelleme: ${response.lastUpdated} (Çevrimdışı)",
                                                fontSize = 11.sp,
                                                color = Color(0xFFE65100),
                                                fontWeight = FontWeight.Bold
                                            )
                                        }
                                    }
                                }

                                // A. Crisis Adaptive Redirection Banner
                                if (overview.crisisCount >= 1) {
                                    Surface(
                                        modifier = Modifier
                                            .fillMaxWidth()
                                            .padding(bottom = 16.dp),
                                        shape = RoundedCornerShape(20.dp),
                                        color = Color(0xFFFEE2E2), // Gentle supportive pink/red background
                                        shadowElevation = 1.dp
                                    ) {
                                        Column(modifier = Modifier.padding(18.dp)) {
                                            Row(verticalAlignment = Alignment.CenterVertically) {
                                                Box(
                                                    modifier = Modifier
                                                        .size(32.dp)
                                                        .clip(CircleShape)
                                                        .background(Color.White),
                                                    contentAlignment = Alignment.Center
                                                ) {
                                                    Icon(
                                                        Icons.Default.Warning,
                                                        contentDescription = null,
                                                        tint = DangerRed,
                                                        modifier = Modifier.size(18.dp)
                                                    )
                                                }
                                                Spacer(modifier = Modifier.width(10.dp))
                                                Text(
                                                    "Yalnız Değilsiniz, Yanınızdayız",
                                                    fontSize = 14.sp,
                                                    fontWeight = FontWeight.Bold,
                                                    color = Color(0xFF991B1B)
                                                )
                                            }
                                            Spacer(modifier = Modifier.height(8.dp))
                                            Text(
                                                "Son zamanlarda duygusal yoğunluğunuzun arttığını fark ettik. İhtiyaç duyduğunuz her an, uzman desteğine ücretsiz ve gizli şekilde ulaşabilirsiniz.",
                                                fontSize = 12.sp,
                                                lineHeight = 18.sp,
                                                color = Color(0xFF7F1D1D)
                                            )
                                            Spacer(modifier = Modifier.height(14.dp))
                                            Row(
                                                modifier = Modifier.fillMaxWidth(),
                                                horizontalArrangement = Arrangement.spacedBy(8.dp)
                                            ) {
                                                Button(
                                                    onClick = {
                                                        val intent = Intent(Intent.ACTION_DIAL, Uri.parse("tel:112"))
                                                        context.startActivity(intent)
                                                    },
                                                    colors = ButtonDefaults.buttonColors(containerColor = DangerRed),
                                                    shape = RoundedCornerShape(12.dp),
                                                    modifier = Modifier.weight(1f)
                                                ) {
                                                    Icon(Icons.Default.Call, contentDescription = null, modifier = Modifier.size(16.dp))
                                                    Spacer(modifier = Modifier.width(6.dp))
                                                    Text("112 Acil Yardım", fontSize = 11.sp, fontWeight = FontWeight.Bold)
                                                }
                                                Button(
                                                    onClick = {
                                                        val intent = Intent(Intent.ACTION_DIAL, Uri.parse("tel:114"))
                                                        context.startActivity(intent)
                                                    },
                                                    colors = ButtonDefaults.buttonColors(containerColor = AccentPrimary),
                                                    shape = RoundedCornerShape(12.dp),
                                                    modifier = Modifier.weight(1f)
                                                ) {
                                                    Icon(Icons.Default.Call, contentDescription = null, modifier = Modifier.size(16.dp))
                                                    Spacer(modifier = Modifier.width(6.dp))
                                                    Text("114 Destek", fontSize = 11.sp, fontWeight = FontWeight.Bold)
                                                }
                                            }
                                        }
                                    }
                                }

                                // B. Wellness Score Arc Progress Card (Calming pastel card design)
                                val baseColor = if (overview.crisisCount >= 1) Color(0xFFFDF2F2) else Color.White.copy(alpha = 0.85f)
                                val accentColor = if (overview.crisisCount >= 1) DangerRed else LoginButton

                                Surface(
                                    modifier = Modifier.fillMaxWidth(),
                                    shape = RoundedCornerShape(24.dp),
                                    color = baseColor,
                                    shadowElevation = 1.dp
                                ) {
                                    Column(
                                        modifier = Modifier.padding(24.dp),
                                        horizontalAlignment = Alignment.CenterHorizontally
                                    ) {
                                        Text(
                                            "Zihinsel Wellness Skoru",
                                            fontSize = 15.sp,
                                            fontWeight = FontWeight.Bold,
                                            color = LoginTextColor
                                        )
                                        Spacer(modifier = Modifier.height(18.dp))

                                        Box(
                                            contentAlignment = Alignment.Center,
                                            modifier = Modifier.size(140.dp)
                                        ) {
                                            Canvas(modifier = Modifier.size(120.dp)) {
                                                drawArc(
                                                    color = Color.LightGray.copy(alpha = 0.25f),
                                                    startAngle = 135f,
                                                    sweepAngle = 270f,
                                                    useCenter = false,
                                                    style = Stroke(width = 10.dp.toPx(), cap = StrokeCap.Round)
                                                )

                                                if (scoreObj.score != null) {
                                                    val sweepAngle = 270f * (scoreObj.score.toFloat() / 100f)
                                                    drawArc(
                                                        color = accentColor,
                                                        startAngle = 135f,
                                                        sweepAngle = sweepAngle,
                                                        useCenter = false,
                                                        style = Stroke(width = 10.dp.toPx(), cap = StrokeCap.Round)
                                                    )
                                                }
                                            }

                                            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                                                Text(
                                                    text = scoreObj.score?.toString() ?: "--",
                                                    fontSize = 32.sp,
                                                    fontWeight = FontWeight.Black,
                                                    color = LoginTextColor
                                                )
                                                Text(
                                                    text = "/ 100",
                                                    fontSize = 11.sp,
                                                    color = LoginSecondaryText.copy(alpha = 0.7f)
                                                )
                                            }
                                        }

                                        Spacer(modifier = Modifier.height(10.dp))

                                        Text(
                                            text = scoreObj.label,
                                            fontSize = 14.sp,
                                            fontWeight = FontWeight.Bold,
                                            color = accentColor,
                                            textAlign = TextAlign.Center
                                        )

                                        Spacer(modifier = Modifier.height(6.dp))

                                        Text(
                                            text = scoreObj.description,
                                            fontSize = 12.sp,
                                            lineHeight = 18.sp,
                                            color = LoginSecondaryText,
                                            textAlign = TextAlign.Center,
                                            modifier = Modifier.padding(horizontal = 8.dp)
                                        )
                                    }
                                }

                                Spacer(modifier = Modifier.height(20.dp))

                                // New "İlerleme" Section (Delta Cards + Canvas Graph)
                                Text(
                                    "Gelişim ve İlerleme",
                                    fontSize = 14.sp,
                                    fontWeight = FontWeight.Bold,
                                    color = LoginTextColor,
                                    modifier = Modifier.padding(start = 4.dp, bottom = 12.dp)
                                )

                                // Check if we have snapshots logged in database
                                val last7Days by viewModel.last7DaysSnapshots.collectAsState()
                                val last30Days by viewModel.last30DaysSnapshots.collectAsState()

                                if (last7Days.isEmpty()) {
                                    // Global Empty State Card
                                    Surface(
                                        modifier = Modifier.fillMaxWidth().padding(bottom = 20.dp),
                                        shape = RoundedCornerShape(20.dp),
                                        color = PremiumWhiteCard,
                                        border = BorderStroke(1.dp, SoftMintAccent.copy(alpha = 0.5f))
                                    ) {
                                        Column(modifier = Modifier.padding(20.dp)) {
                                            Row(verticalAlignment = Alignment.CenterVertically) {
                                                Icon(
                                                    imageVector = Icons.Default.Info,
                                                    contentDescription = null,
                                                    tint = DarkTealPrimary,
                                                    modifier = Modifier.size(24.dp)
                                                )
                                                Spacer(modifier = Modifier.width(12.dp))
                                                Text(
                                                    text = "İlerleme verileri oluşturuluyor",
                                                    fontWeight = FontWeight.Bold,
                                                    fontSize = 15.sp,
                                                    color = LoginTextColor
                                                )
                                            }
                                            Spacer(modifier = Modifier.height(8.dp))
                                            Text(
                                                text = "Daha fazla kullanım sonrasında gelişim trendlerini burada görebileceksin. Her gün zihinsel wellness paneline göz atarak veya sohbet ederek günlük wellness skor gelişimini takip edebilirsin.",
                                                fontSize = 12.sp,
                                                lineHeight = 18.sp,
                                                color = LoginSecondaryText
                                            )
                                        }
                                    }
                                } else {
                                    // 1. Delta Progression Cards Row
                                    Row(
                                        modifier = Modifier.fillMaxWidth().padding(bottom = 16.dp),
                                        horizontalArrangement = Arrangement.spacedBy(12.dp)
                                    ) {
                                        // Card 1: Son 7 Gün
                                        val delta7Text = remember(last7Days) {
                                            progressRepository.calculateScoreDelta(last7Days)
                                        }
                                        val is7Gelisim = delta7Text.contains("gelişim")
                                        val is7Dusis = delta7Text.contains("düşüş")
                                        val card7Bg = when {
                                            is7Gelisim -> SoftMintLight
                                            is7Dusis -> MildAlertBg
                                            else -> PremiumWhiteCard
                                        }
                                        val card7Border = when {
                                            is7Gelisim -> DarkTealPrimary.copy(alpha = 0.2f)
                                            is7Dusis -> MildAlertText.copy(alpha = 0.2f)
                                            else -> SoftMintAccent.copy(alpha = 0.5f)
                                        }
                                        val text7Color = when {
                                            is7Gelisim -> DarkTealPrimary
                                            is7Dusis -> MildAlertText
                                            else -> LoginSecondaryText
                                        }

                                        Surface(
                                            modifier = Modifier.weight(1f),
                                            shape = RoundedCornerShape(16.dp),
                                            color = card7Bg,
                                            border = BorderStroke(1.dp, card7Border)
                                        ) {
                                            Column(modifier = Modifier.padding(14.dp)) {
                                                Text("Son 7 Gün", fontSize = 12.sp, fontWeight = FontWeight.Bold, color = LoginTextColor)
                                                Spacer(modifier = Modifier.height(6.dp))
                                                Text(
                                                    text = delta7Text,
                                                    fontSize = 14.sp,
                                                    fontWeight = FontWeight.Bold,
                                                    color = text7Color
                                                )
                                            }
                                        }

                                        // Card 2: Son 30 Gün
                                        val delta30Text = remember(last30Days) {
                                            progressRepository.calculateScoreDelta(last30Days)
                                        }
                                        val is30Gelisim = delta30Text.contains("gelişim")
                                        val is30Dusis = delta30Text.contains("düşüş")
                                        val card30Bg = when {
                                            is30Gelisim -> SoftMintLight
                                            is30Dusis -> MildAlertBg
                                            else -> PremiumWhiteCard
                                        }
                                        val card30Border = when {
                                            is30Gelisim -> DarkTealPrimary.copy(alpha = 0.2f)
                                            is30Dusis -> MildAlertText.copy(alpha = 0.2f)
                                            else -> SoftMintAccent.copy(alpha = 0.5f)
                                        }
                                        val text30Color = when {
                                            is30Gelisim -> DarkTealPrimary
                                            is30Dusis -> MildAlertText
                                            else -> LoginSecondaryText
                                        }

                                        Surface(
                                            modifier = Modifier.weight(1f),
                                            shape = RoundedCornerShape(16.dp),
                                            color = card30Bg,
                                            border = BorderStroke(1.dp, card30Border)
                                        ) {
                                            Column(modifier = Modifier.padding(14.dp)) {
                                                Text("Son 30 Gün", fontSize = 12.sp, fontWeight = FontWeight.Bold, color = LoginTextColor)
                                                Spacer(modifier = Modifier.height(6.dp))
                                                Text(
                                                    text = delta30Text,
                                                    fontSize = 14.sp,
                                                    fontWeight = FontWeight.Bold,
                                                    color = text30Color
                                                )
                                            }
                                        }
                                    }

                                    // 2. Line Chart Visualizer Card (Canvas-based)
                                    Surface(
                                        modifier = Modifier.fillMaxWidth().padding(bottom = 20.dp),
                                        shape = RoundedCornerShape(20.dp),
                                        color = PremiumWhiteCard,
                                        border = BorderStroke(1.dp, SoftMintAccent.copy(alpha = 0.5f))
                                    ) {
                                        Column(modifier = Modifier.padding(16.dp)) {
                                            Text(
                                                text = "Skor Değişim Grafiği (Son 7 Gün)",
                                                fontSize = 13.sp,
                                                fontWeight = FontWeight.Bold,
                                                color = LoginTextColor,
                                                modifier = Modifier.padding(bottom = 12.dp)
                                            )

                                            if (last7Days.size < 2) {
                                                // Graph empty state
                                                Box(
                                                    modifier = Modifier.fillMaxWidth().height(120.dp),
                                                    contentAlignment = Alignment.Center
                                                ) {
                                                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                                                        Icon(Icons.Default.Info, contentDescription = null, tint = SecondaryTealText, modifier = Modifier.size(24.dp))
                                                        Spacer(modifier = Modifier.height(4.dp))
                                                        Text("Henüz yeterli veri yok", fontWeight = FontWeight.Bold, fontSize = 12.sp, color = LoginTextColor)
                                                        Text("En az 2 günlük wellness skoru kaydı gerekiyor.", fontSize = 10.sp, color = LoginSecondaryText)
                                                    }
                                                }
                                            } else {
                                                // Renders custom Compose line graph using Canvas
                                                // Reverse list to show chronologically from left to right (oldest to newest)
                                                val chronologicalSnapshots = remember(last7Days) {
                                                    last7Days.reversed()
                                                }

                                                Canvas(
                                                    modifier = Modifier.fillMaxWidth().height(140.dp)
                                                ) {
                                                    val canvasWidth = size.width
                                                    val canvasHeight = size.height
                                                    val paddingLeft = 30.dp.toPx()
                                                    val paddingRight = 30.dp.toPx()
                                                    val paddingTop = 20.dp.toPx()
                                                    val paddingBottom = 20.dp.toPx()

                                                    val drawWidth = canvasWidth - paddingLeft - paddingRight
                                                    val drawHeight = canvasHeight - paddingTop - paddingBottom

                                                    val pointsCount = chronologicalSnapshots.size
                                                    val stepX = drawWidth / (pointsCount - 1)

                                                    // Wellness score is 0 to 100
                                                    val linePath = Path()
                                                    val fillPath = Path()

                                                    // Calculate coordinates
                                                    val coordinates = chronologicalSnapshots.mapIndexed { idx, snap ->
                                                        val x = paddingLeft + (idx * stepX)
                                                        // Score 100 is at top (paddingTop), score 0 is at bottom (paddingTop + drawHeight)
                                                        val normScore = snap.score.coerceIn(0, 100).toFloat() / 100f
                                                        val y = paddingTop + (drawHeight * (1f - normScore))
                                                        x to y
                                                    }

                                                    // Begin paths
                                                    coordinates.forEachIndexed { idx, (x, y) ->
                                                        if (idx == 0) {
                                                            linePath.moveTo(x, y)
                                                            fillPath.moveTo(x, paddingTop + drawHeight)
                                                            fillPath.lineTo(x, y)
                                                        } else {
                                                            linePath.lineTo(x, y)
                                                            fillPath.lineTo(x, y)
                                                        }
                                                        if (idx == coordinates.lastIndex) {
                                                            fillPath.lineTo(x, paddingTop + drawHeight)
                                                            fillPath.close()
                                                        }
                                                    }

                                                    // 1. Draw solid background filled area
                                                    drawPath(
                                                        path = fillPath,
                                                        color = SoftMintAccent.copy(alpha = 0.25f)
                                                    )

                                                    // 2. Draw active connecting line
                                                    drawPath(
                                                        path = linePath,
                                                        color = DarkTealAccent,
                                                        style = Stroke(width = 3.dp.toPx(), cap = StrokeCap.Round)
                                                    )

                                                    // 3. Draw circle dots on each score point, score label and date abbreviation
                                                    coordinates.forEachIndexed { idx, (x, y) ->
                                                        // Point circle
                                                        drawCircle(
                                                            color = DarkTealPrimary,
                                                            radius = 4.dp.toPx(),
                                                            center = androidx.compose.ui.geometry.Offset(x, y)
                                                        )
                                                        // White inner dot for premium look
                                                        drawCircle(
                                                            color = Color.White,
                                                            radius = 2.dp.toPx(),
                                                            center = androidx.compose.ui.geometry.Offset(x, y)
                                                        )
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }

                                Spacer(modifier = Modifier.height(20.dp))

                                // C. Overview Stats Grid (2x2 Display)
                                Text(
                                    "Genel Durum Özetleri",
                                    fontSize = 14.sp,
                                    fontWeight = FontWeight.Bold,
                                    color = LoginTextColor,
                                    modifier = Modifier.padding(start = 4.dp, bottom = 12.dp)
                                )

                                Row(modifier = Modifier.fillMaxWidth()) {
                                    DashboardStatCard(
                                        title = "Sohbet Sayısı",
                                        value = overview.totalMessages.toString(),
                                        icon = Icons.Default.Email,
                                        color = AccentPrimary.copy(alpha = 0.15f),
                                        tint = AccentPrimary,
                                        modifier = Modifier.weight(1f)
                                    )
                                    Spacer(modifier = Modifier.width(12.dp))
                                    DashboardStatCard(
                                        title = "Günlük Kayıt",
                                        value = overview.journalCount.toString(),
                                        icon = Icons.Default.Edit,
                                        color = Color(0xFFFCD34D).copy(alpha = 0.2f),
                                        tint = Color(0xFFD97706),
                                        modifier = Modifier.weight(1f)
                                    )
                                }
                                Spacer(modifier = Modifier.height(12.dp))
                                Row(modifier = Modifier.fillMaxWidth()) {
                                    DashboardStatCard(
                                        title = "Planlanmış Öneri",
                                        value = overview.scheduledInterventionCount.toString(),
                                        icon = Icons.Default.DateRange,
                                        color = LoginButton.copy(alpha = 0.2f),
                                        tint = LoginButton,
                                        modifier = Modifier.weight(1f)
                                    )
                                    Spacer(modifier = Modifier.width(12.dp))
                                    DashboardStatCard(
                                        title = "Hatırlatıcılar",
                                        value = overview.notificationCount.toString(),
                                        icon = Icons.Default.Notifications,
                                        color = Purple80.copy(alpha = 0.25f),
                                        tint = AccentPrimary,
                                        modifier = Modifier.weight(1f)
                                    )
                                }

                                // D. Emotion Distribution Chart
                                if (sections.emotionDistribution.isNotEmpty()) {
                                    Spacer(modifier = Modifier.height(24.dp))
                                    Text(
                                        "Duygusal Dağılım",
                                        fontSize = 14.sp,
                                        fontWeight = FontWeight.Bold,
                                        color = LoginTextColor,
                                        modifier = Modifier.padding(start = 4.dp, bottom = 12.dp)
                                    )

                                    Surface(
                                        modifier = Modifier.fillMaxWidth(),
                                        shape = RoundedCornerShape(20.dp),
                                        color = Color.White.copy(alpha = 0.75f)
                                    ) {
                                        Column(modifier = Modifier.padding(20.dp)) {
                                            val total = sections.emotionDistribution.values.sum().toFloat()
                                            sections.emotionDistribution.forEach { (emotion, count) ->
                                                val pct = if (total > 0) (count / total * 100f).toInt() else 0
                                                val color = when (emotion.lowercase()) {
                                                    "mutluluk", "joy", "happy" -> Color(0xFF34D399) // Emerald
                                                    "sakin", "calm" -> Color(0xFF60A5FA) // Blue
                                                    "kaygı", "anxious", "stres", "stress" -> Color(0xFFFBBF24) // Yellow
                                                    "üzüntü", "sad", "sadness" -> Color(0xFF818CF8) // Indigo
                                                    "öfke", "anger", "angry" -> Color(0xFFF87171) // Red
                                                    "yorgun", "tired" -> Color(0xFFA78BFA) // Purple
                                                    else -> Color.Gray
                                                }

                                                Column(modifier = Modifier.padding(vertical = 6.dp)) {
                                                    Row(
                                                        modifier = Modifier.fillMaxWidth(),
                                                        horizontalArrangement = Arrangement.SpaceBetween
                                                    ) {
                                                        Text(emotion, fontSize = 11.sp, color = LoginTextColor, fontWeight = FontWeight.Bold)
                                                        Text("%$pct ($count Adet)", fontSize = 11.sp, color = LoginSecondaryText)
                                                    }
                                                    Spacer(modifier = Modifier.height(4.dp))
                                                    Box(
                                                        modifier = Modifier
                                                            .fillMaxWidth()
                                                            .height(8.dp)
                                                            .clip(CircleShape)
                                                            .background(Color.LightGray.copy(alpha = 0.3f))
                                                    ) {
                                                        Box(
                                                            modifier = Modifier
                                                                .fillMaxWidth(if (total > 0) count / total else 0f)
                                                                .fillMaxHeight()
                                                                .clip(CircleShape)
                                                                .background(color)
                                                        )
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }

                                // E. Mini Daily Trend Timeline Line Chart
                                if (sections.dailyTrend.isNotEmpty()) {
                                    Spacer(modifier = Modifier.height(24.dp))
                                    Text(
                                        "Duygusal İletişim Eğrisi",
                                        fontSize = 14.sp,
                                        fontWeight = FontWeight.Bold,
                                        color = LoginTextColor,
                                        modifier = Modifier.padding(start = 4.dp, bottom = 12.dp)
                                    )

                                    Surface(
                                        modifier = Modifier.fillMaxWidth(),
                                        shape = RoundedCornerShape(20.dp),
                                        color = Color.White.copy(alpha = 0.75f)
                                    ) {
                                        Column(modifier = Modifier.padding(20.dp)) {
                                            Text(
                                                "Günlük Sohbet Adedi Grafiği",
                                                fontSize = 12.sp,
                                                fontWeight = FontWeight.Bold,
                                                color = LoginSecondaryText,
                                                modifier = Modifier.padding(bottom = 12.dp)
                                            )

                                            val maxVal = sections.dailyTrend.maxOfOrNull { it.totalCount } ?: 1
                                            val resolvedLoginButton = LoginButton
                                            Canvas(
                                                modifier = Modifier
                                                    .fillMaxWidth()
                                                    .height(100.dp)
                                            ) {
                                                val width = size.width
                                                val height = size.height
                                                val spacing = width / (sections.dailyTrend.size - 1).coerceAtLeast(1)

                                                val path = Path()
                                                sections.dailyTrend.forEachIndexed { i, item ->
                                                    val x = i * spacing
                                                    val y = height - (item.totalCount.toFloat() / maxVal.toFloat() * height * 0.8f)

                                                    if (i == 0) {
                                                        path.moveTo(x, y)
                                                    } else {
                                                        path.lineTo(x, y)
                                                    }
                                                    drawCircle(
                                                        color = resolvedLoginButton,
                                                        radius = 4.dp.toPx(),
                                                        center = androidx.compose.ui.geometry.Offset(x, y)
                                                    )
                                                }

                                                drawPath(
                                                    path = path,
                                                    color = resolvedLoginButton,
                                                    style = Stroke(width = 3.dp.toPx(), cap = StrokeCap.Round)
                                                )
                                            }

                                            Spacer(modifier = Modifier.height(10.dp))
                                            Row(
                                                modifier = Modifier.fillMaxWidth(),
                                                horizontalArrangement = Arrangement.SpaceBetween
                                            ) {
                                                Text(sections.dailyTrend.first().date, fontSize = 9.sp, color = LoginSecondaryText)
                                                Text(sections.dailyTrend.last().date, fontSize = 9.sp, color = LoginSecondaryText)
                                            }
                                        }
                                    }
                                }

                                // F. Active Behavioral Insights Preview
                                if (sections.topInsights.isNotEmpty()) {
                                    Spacer(modifier = Modifier.height(24.dp))
                                    Text(
                                        "Önemli Davranışsal İçgörüler",
                                        fontSize = 14.sp,
                                        fontWeight = FontWeight.Bold,
                                        color = LoginTextColor,
                                        modifier = Modifier.padding(start = 4.dp, bottom = 12.dp)
                                    )

                                    sections.topInsights.forEach { insight ->
                                        Surface(
                                            modifier = Modifier
                                                .fillMaxWidth()
                                                .padding(vertical = 4.dp)
                                                .clickable { navController.navigate("insights") },
                                            shape = RoundedCornerShape(16.dp),
                                            color = Color.White.copy(alpha = 0.8f)
                                        ) {
                                            Row(
                                                modifier = Modifier.padding(16.dp),
                                                verticalAlignment = Alignment.Top
                                            ) {
                                                Icon(
                                                    Icons.Default.Info,
                                                    contentDescription = null,
                                                    tint = LoginButton,
                                                    modifier = Modifier.size(18.dp)
                                                )
                                                Spacer(modifier = Modifier.width(12.dp))
                                                Column {
                                                    Text(insight.title, fontSize = 12.sp, fontWeight = FontWeight.Bold, color = LoginTextColor)
                                                    Spacer(modifier = Modifier.height(4.dp))
                                                    Text(insight.description, fontSize = 11.sp, lineHeight = 16.sp, color = LoginSecondaryText)
                                                }
                                            }
                                        }
                                    }
                                }

                                // G. Previews of latest reflection and reports (FULLY CLICKABLE LINKINGS)
                                if (sections.latestReflection != null) {
                                    Spacer(modifier = Modifier.height(24.dp))
                                    Text(
                                        "Zihinsel Refleksiyon Özeti",
                                        fontSize = 14.sp,
                                        fontWeight = FontWeight.Bold,
                                        color = LoginTextColor,
                                        modifier = Modifier.padding(start = 4.dp, bottom = 12.dp)
                                    )

                                    Surface(
                                        modifier = Modifier
                                            .fillMaxWidth()
                                            .clickable { navController.navigate("reflections") },
                                        shape = RoundedCornerShape(20.dp),
                                        color = Color.White.copy(alpha = 0.85f),
                                        shadowElevation = 0.5.dp
                                    ) {
                                        Column(modifier = Modifier.padding(20.dp)) {
                                            Row(
                                                verticalAlignment = Alignment.CenterVertically,
                                                horizontalArrangement = Arrangement.SpaceBetween,
                                                modifier = Modifier.fillMaxWidth()
                                            ) {
                                                Text(
                                                    sections.latestReflection.reflectionTitle,
                                                    fontSize = 13.sp,
                                                    fontWeight = FontWeight.Bold,
                                                    color = LoginTextColor
                                                )
                                                Icon(Icons.AutoMirrored.Filled.ArrowForward, contentDescription = null, tint = LoginButton, modifier = Modifier.size(16.dp))
                                            }
                                            Spacer(modifier = Modifier.height(8.dp))
                                            Text(
                                                sections.latestReflection.reflectionText,
                                                fontSize = 11.sp,
                                                lineHeight = 16.sp,
                                                maxLines = 3,
                                                color = LoginSecondaryText
                                            )
                                        }
                                    }
                                }

                                if (sections.latestReport != null) {
                                    Spacer(modifier = Modifier.height(24.dp))
                                    Text(
                                        "Haftalık Gelişim Raporu",
                                        fontSize = 14.sp,
                                        fontWeight = FontWeight.Bold,
                                        color = LoginTextColor,
                                        modifier = Modifier.padding(start = 4.dp, bottom = 12.dp)
                                    )

                                    Surface(
                                        modifier = Modifier
                                            .fillMaxWidth()
                                            .clickable { navController.navigate("wellness_report") },
                                        shape = RoundedCornerShape(20.dp),
                                        color = Color.White.copy(alpha = 0.85f),
                                        shadowElevation = 0.5.dp
                                    ) {
                                        Column(modifier = Modifier.padding(20.dp)) {
                                            Row(
                                                verticalAlignment = Alignment.CenterVertically,
                                                horizontalArrangement = Arrangement.SpaceBetween,
                                                modifier = Modifier.fillMaxWidth()
                                            ) {
                                                Text(
                                                    sections.latestReport.summaryTitle,
                                                    fontSize = 13.sp,
                                                    fontWeight = FontWeight.Bold,
                                                    color = LoginTextColor
                                                )
                                                Icon(Icons.AutoMirrored.Filled.ArrowForward, contentDescription = null, tint = LoginButton, modifier = Modifier.size(16.dp))
                                            }
                                            Spacer(modifier = Modifier.height(8.dp))
                                            Text(
                                                sections.latestReport.summaryText,
                                                fontSize = 11.sp,
                                                lineHeight = 16.sp,
                                                maxLines = 3,
                                                color = LoginSecondaryText
                                            )
                                        }
                                    }
                                }

                                // H. Scheduled Wellness Interventions Previews
                                if (sections.activeInterventions.isNotEmpty()) {
                                    Spacer(modifier = Modifier.height(24.dp))
                                    Text(
                                        "Önerilen Aktiviteler",
                                        fontSize = 14.sp,
                                        fontWeight = FontWeight.Bold,
                                        color = LoginTextColor,
                                        modifier = Modifier.padding(start = 4.dp, bottom = 12.dp)
                                    )

                                    Surface(
                                        modifier = Modifier
                                            .fillMaxWidth()
                                            .clickable { navController.navigate("wellness_schedule") },
                                        shape = RoundedCornerShape(20.dp),
                                        color = Color.White.copy(alpha = 0.85f),
                                        shadowElevation = 0.5.dp
                                    ) {
                                        Column(modifier = Modifier.padding(20.dp)) {
                                            Row(
                                                verticalAlignment = Alignment.CenterVertically,
                                                horizontalArrangement = Arrangement.SpaceBetween,
                                                modifier = Modifier.fillMaxWidth()
                                            ) {
                                                Text(
                                                    "Planlanmış Egzersizlerim",
                                                    fontSize = 13.sp,
                                                    fontWeight = FontWeight.Bold,
                                                    color = LoginTextColor
                                                )
                                                Icon(Icons.AutoMirrored.Filled.ArrowForward, contentDescription = null, tint = LoginButton, modifier = Modifier.size(16.dp))
                                            }
                                            Spacer(modifier = Modifier.height(8.dp))
                                            sections.activeInterventions.forEachIndexed { idx, act ->
                                                if (idx < 2) {
                                                    Row(
                                                        modifier = Modifier.padding(vertical = 4.dp),
                                                        verticalAlignment = Alignment.CenterVertically
                                                    ) {
                                                        Icon(Icons.Default.CheckCircle, contentDescription = null, tint = LoginButton, modifier = Modifier.size(14.dp))
                                                        Spacer(modifier = Modifier.width(8.dp))
                                                        Text(act.title, fontSize = 11.sp, color = LoginSecondaryText)
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }

                                // Clinical Disclaimer Card
                                Spacer(modifier = Modifier.height(32.dp))
                                Surface(
                                    color = Color.White.copy(alpha = 0.4f),
                                    shape = RoundedCornerShape(16.dp),
                                    modifier = Modifier.fillMaxWidth()
                                ) {
                                    Text(
                                        "Bu panel, duygu geçmişinizin gözlemsel bir özetidir. Kesinlikle tıbbi bir teşhis veya klinik tedavi planı niteliği taşımaz. İhtiyaç duyduğunuz durumlarda uzman desteği almayı ihmal etmeyiniz.",
                                        fontSize = 10.sp,
                                        lineHeight = 16.sp,
                                        color = LoginTextColor.copy(alpha = 0.6f),
                                        modifier = Modifier.padding(16.dp),
                                        textAlign = TextAlign.Center
                                    )
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
fun DashboardStatCard(
    title: String,
    value: String,
    icon: androidx.compose.ui.graphics.vector.ImageVector,
    color: Color,
    tint: Color,
    modifier: Modifier = Modifier
) {
    PremiumCard(
        modifier = modifier.height(80.dp),
        backgroundColor = Color.White.copy(alpha = 0.75f),
        cornerRadius = 18.dp,
        elevation = 1.dp
    ) {
        Row(
            verticalAlignment = Alignment.CenterVertically
        ) {
            Box(
                modifier = Modifier
                    .size(40.dp)
                    .clip(CircleShape)
                    .background(color),
                contentAlignment = Alignment.Center
            ) {
                Icon(icon, contentDescription = null, tint = tint, modifier = Modifier.size(18.dp))
            }
            Spacer(modifier = Modifier.width(12.dp))
            Column {
                Text(title, fontSize = 11.sp, color = LoginSecondaryText)
                Text(value, fontSize = 16.sp, fontWeight = FontWeight.Bold, color = LoginTextColor)
            }
        }
    }
}

@Composable
private fun StreakStatCard(
    title: String,
    value: String,
    subtitle: String,
    badge: String,
    modifier: Modifier = Modifier
) {
    Surface(
        modifier = modifier,
        shape = RoundedCornerShape(16.dp),
        color = PremiumWhiteCard,
        border = BorderStroke(1.dp, SoftMintAccent.copy(alpha = 0.5f))
    ) {
        Column(
            modifier = Modifier.padding(14.dp)
        ) {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.SpaceBetween,
                modifier = Modifier.fillMaxWidth()
            ) {
                Text(
                    text = title,
                    fontSize = 12.sp,
                    fontWeight = FontWeight.Bold,
                    color = LoginSecondaryText
                )
                Text(
                    text = badge,
                    fontSize = 14.sp
                )
            }
            Spacer(modifier = Modifier.height(8.dp))
            Text(
                text = value,
                fontSize = 22.sp,
                fontWeight = FontWeight.Black,
                color = LoginTextColor
            )
            Spacer(modifier = Modifier.height(2.dp))
            Text(
                text = subtitle,
                fontSize = 11.sp,
                color = SecondaryTealText
            )
        }
    }
}

