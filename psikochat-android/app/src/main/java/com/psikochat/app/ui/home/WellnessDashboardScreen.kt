package com.psikochat.app.ui.home

import android.content.Intent
import android.net.Uri
import androidx.compose.animation.*
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
    val factory = object : ViewModelProvider.Factory {
        @Suppress("UNCHECKED_CAST")
        override fun <T : ViewModel> create(modelClass: Class<T>): T {
            return WellnessDashboardViewModel(repository, tokenManager, syncManager) as T
        }
    }
    val viewModel: WellnessDashboardViewModel = viewModel(factory = factory)

    val dashboardState by viewModel.dashboardState.collectAsState()
    val selectedDays by viewModel.selectedDays.collectAsState()
    val scrollState = rememberScrollState()

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

            Spacer(modifier = Modifier.height(16.dp))

            // 2. Main content Box with Stateflow
            Box(
                modifier = Modifier
                    .weight(1f)
                    .fillMaxWidth()
            ) {
                when (val state = dashboardState) {
                    is Resource.Loading -> {
                        Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                            CircularProgressIndicator(color = LoginButton)
                        }
                    }
                    is Resource.Error -> {
                        Column(
                            modifier = Modifier
                                .fillMaxSize()
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
                    is Resource.Success -> {
                        val response = state.data
                        if (response == null) {
                            Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                                Text("Veri bulunamadı.", color = LoginTextColor)
                            }
                        } else {
                            val overview = response.overview
                            val scoreObj = response.wellnessScore
                            val sections = response.sections

                            Column(
                                modifier = Modifier
                                    .fillMaxSize()
                                    .verticalScroll(scrollState)
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
                                                        color = LoginButton,
                                                        radius = 4.dp.toPx(),
                                                        center = androidx.compose.ui.geometry.Offset(x, y)
                                                    )
                                                }

                                                drawPath(
                                                    path = path,
                                                    color = LoginButton,
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
                                                .padding(vertical = 4.dp),
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
    Surface(
        modifier = modifier.height(80.dp),
        shape = RoundedCornerShape(18.dp),
        color = Color.White.copy(alpha = 0.75f)
    ) {
        Row(
            modifier = Modifier.padding(16.dp),
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
