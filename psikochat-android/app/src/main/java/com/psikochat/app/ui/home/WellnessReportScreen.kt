package com.psikochat.app.ui.home

import androidx.compose.animation.*
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Done
import androidx.compose.material.icons.filled.Info
import androidx.compose.material.icons.filled.KeyboardArrowLeft
import androidx.compose.material.icons.filled.Star
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
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
import com.psikochat.app.data.model.WellnessReport
import com.psikochat.app.data.repository.WellnessReportRepository
import com.psikochat.app.ui.theme.*
import com.psikochat.app.ui.components.PremiumLockedCard

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun WellnessReportScreen(navController: NavController, tokenManager: TokenManager) {
    val context = LocalContext.current
    val db = com.psikochat.app.data.local.AppDatabase.getInstance(context)
    val syncManager = com.psikochat.app.data.sync.SyncManager.getInstance(context)
    val api = RetrofitClient.create(tokenManager)
    val repository = WellnessReportRepository(api, db.reportDao())
    val factory = object : ViewModelProvider.Factory {
        @Suppress("UNCHECKED_CAST")
        override fun <T : ViewModel> create(modelClass: Class<T>): T {
            return WellnessReportViewModel(repository, tokenManager, syncManager) as T
        }
    }
    val viewModel: WellnessReportViewModel = viewModel(factory = factory)

    val reportState by viewModel.reportState.collectAsState()
    val selectedPeriod by viewModel.selectedPeriod.collectAsState()
    
    val scrollState = rememberScrollState()

    Scaffold(
        topBar = {
            CenterAlignedTopAppBar(
                title = {
                    Text(
                        "Gelişim Raporum",
                        style = MaterialTheme.typography.titleMedium,
                        color = LoginTextColor,
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
        containerColor = LoginBackground
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(horizontal = 24.dp)
        ) {
            Spacer(modifier = Modifier.height(8.dp))

            // 1. Period Toggle (Segmented Control style)
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
                    // Daily Tab
                    val dailySelected = selectedPeriod == "daily"
                    Box(
                        modifier = Modifier
                            .weight(1f)
                            .fillMaxHeight()
                            .clip(RoundedCornerShape(20.dp))
                            .background(if (dailySelected) LoginButton else Color.Transparent)
                            .clickable { viewModel.selectPeriod("daily") },
                        contentAlignment = Alignment.Center
                    ) {
                        Text(
                            "Günlük Analiz",
                            fontSize = 13.sp,
                            fontWeight = FontWeight.Bold,
                            color = if (dailySelected) Color.White else LoginSecondaryText
                        )
                    }

                    // Weekly Tab
                    val weeklySelected = selectedPeriod == "weekly"
                    Box(
                        modifier = Modifier
                            .weight(1f)
                            .fillMaxHeight()
                            .clip(RoundedCornerShape(20.dp))
                            .background(if (weeklySelected) LoginButton else Color.Transparent)
                            .clickable { viewModel.selectPeriod("weekly") },
                        contentAlignment = Alignment.Center
                    ) {
                        Text(
                            "Haftalık Analiz",
                            fontSize = 13.sp,
                            fontWeight = FontWeight.Bold,
                            color = if (weeklySelected) Color.White else LoginSecondaryText
                        )
                    }
                }
            }

            Spacer(modifier = Modifier.height(20.dp))

            // 2. Report State Selector
            Box(
                modifier = Modifier
                    .weight(1f)
                    .fillMaxWidth()
            ) {
                when (val state = reportState) {
                    is Resource.Loading -> {
                        Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                            CircularProgressIndicator(color = LoginButton)
                        }
                    }
                    is Resource.Error -> {
                        if (state.isPremiumRequired) {
                            PremiumLockedCard(
                                title = "Premium Rapor",
                                description = "Gelişmiş iyi oluş analizleri ve kişisel raporlar Premium üyelikle açılır.",
                                ctaText = "Premium'a Geç",
                                onUpgradeClick = { navController.navigate("payment_methods") }
                            )
                        } else {
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
                                    state.message ?: "Rapor yüklenirken hata oluştu.",
                                    textAlign = TextAlign.Center,
                                    color = LoginTextColor
                                )
                                Spacer(modifier = Modifier.height(16.dp))
                                Button(
                                    onClick = { viewModel.loadReport() },
                                    colors = ButtonDefaults.buttonColors(containerColor = LoginButton)
                                ) {
                                    Text("Yeniden Dene")
                                }
                            }
                        }
                    }
                    is Resource.Success -> {
                        val report = state.data
                        if (report == null || report.summaryTitle == "Henüz yeterli veri oluşmadı.") {
                            // Insufficient Data State
                            Column(
                                modifier = Modifier
                                    .fillMaxSize()
                                    .verticalScroll(scrollState)
                                    .padding(vertical = 16.dp),
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
                                    "Henüz Yeterli Veri Oluşmadı",
                                    textAlign = TextAlign.Center,
                                    fontSize = 16.sp,
                                    fontWeight = FontWeight.Bold,
                                    color = LoginTextColor
                                )
                                Spacer(modifier = Modifier.height(12.dp))
                                Text(
                                    report?.summaryText ?: "Raporunuzun hazırlanabilmesi için en az 4 günlük sohbet geçmişi veya duygu durum kaydı gerekmektedir.",
                                    textAlign = TextAlign.Center,
                                    fontSize = 13.sp,
                                    color = LoginSecondaryText,
                                    modifier = Modifier.padding(horizontal = 16.dp)
                                )
                            }
                        } else {
                            // Main Wellness Report Contents
                            Column(
                                modifier = Modifier
                                    .fillMaxSize()
                                    .verticalScroll(scrollState)
                                    .padding(bottom = 24.dp)
                            ) {
                                val reportColor = when (report.dominantEmotion) {
                                    "crisis" -> Color(0xFFFEE2E2) // Gentle support pink
                                    "anexty", "anxiety" -> Color(0xFFEEF2FF) // Lavender blue
                                    "sadness" -> Color(0xFFF0FDF4).copy(alpha = 0.8f) // Peaceful mint
                                    "anger" -> Color(0xFFFFFBEB) // Soft warm gold
                                    else -> Color.White.copy(alpha = 0.9f)
                                }
                                
                                val accentColor = when (report.dominantEmotion) {
                                    "crisis" -> DangerRed
                                    "anexty", "anxiety" -> AccentPrimary
                                    "sadness" -> LoginButton
                                    "anger" -> Color(0xFFD97706)
                                    else -> LoginButton
                                }

                                // 3. Summary Container Card
                                Surface(
                                    modifier = Modifier.fillMaxWidth(),
                                    shape = RoundedCornerShape(28.dp),
                                    color = reportColor,
                                    shadowElevation = 1.dp
                                ) {
                                    Column(modifier = Modifier.padding(24.dp)) {
                                        Row(verticalAlignment = Alignment.CenterVertically) {
                                            Box(
                                                modifier = Modifier
                                                    .size(36.dp)
                                                    .clip(CircleShape)
                                                    .background(Color.White),
                                                contentAlignment = Alignment.Center
                                            ) {
                                                Icon(
                                                    Icons.Default.Info,
                                                    contentDescription = null,
                                                    tint = accentColor,
                                                    modifier = Modifier.size(20.dp)
                                                )
                                            }
                                            Spacer(modifier = Modifier.width(12.dp))
                                            Text(
                                                report.summaryTitle,
                                                fontSize = 15.sp,
                                                fontWeight = FontWeight.Bold,
                                                color = LoginTextColor
                                            )
                                        }
                                        Spacer(modifier = Modifier.height(16.dp))
                                        Text(
                                            report.summaryText,
                                            fontSize = 13.sp,
                                            lineHeight = 20.sp,
                                            color = LoginSecondaryText
                                        )
                                    }
                                }

                                // 4. Highlights Section
                                if (report.highlights.isNotEmpty()) {
                                    Spacer(modifier = Modifier.height(24.dp))
                                    Text(
                                        "Öne Çıkan Gözlemler",
                                        fontSize = 14.sp,
                                        fontWeight = FontWeight.Bold,
                                        color = LoginTextColor,
                                        modifier = Modifier.padding(start = 8.dp)
                                    )
                                    Spacer(modifier = Modifier.height(12.dp))
                                    report.highlights.forEach { highlight ->
                                        Row(
                                            modifier = Modifier
                                                .fillMaxWidth()
                                                .padding(vertical = 6.dp, horizontal = 8.dp),
                                            verticalAlignment = Alignment.Top
                                        ) {
                                            Icon(
                                                Icons.Default.Star,
                                                contentDescription = null,
                                                tint = accentColor,
                                                modifier = Modifier.size(16.dp).padding(top = 2.dp)
                                            )
                                            Spacer(modifier = Modifier.width(12.dp))
                                            Text(
                                                highlight,
                                                fontSize = 12.sp,
                                                lineHeight = 18.sp,
                                                color = LoginSecondaryText
                                            )
                                        }
                                    }
                                }

                                // 5. Suggestions Section
                                if (report.suggestions.isNotEmpty()) {
                                    Spacer(modifier = Modifier.height(24.dp))
                                    Text(
                                        "Destekleyici Öneriler",
                                        fontSize = 14.sp,
                                        fontWeight = FontWeight.Bold,
                                        color = LoginTextColor,
                                        modifier = Modifier.padding(start = 8.dp)
                                    )
                                    Spacer(modifier = Modifier.height(12.dp))
                                    report.suggestions.forEach { suggestion ->
                                        Row(
                                            modifier = Modifier
                                                .fillMaxWidth()
                                                .padding(vertical = 6.dp, horizontal = 8.dp),
                                            verticalAlignment = Alignment.Top
                                        ) {
                                            Icon(
                                                Icons.Default.Done,
                                                contentDescription = null,
                                                tint = LoginButton,
                                                modifier = Modifier.size(16.dp).padding(top = 2.dp)
                                            )
                                            Spacer(modifier = Modifier.width(12.dp))
                                            Text(
                                                suggestion,
                                                fontSize = 12.sp,
                                                lineHeight = 18.sp,
                                                color = LoginSecondaryText
                                            )
                                        }
                                    }
                                }

                                // 6. Clinical Disclaimer
                                Spacer(modifier = Modifier.height(32.dp))
                                Surface(
                                    color = Color.White.copy(alpha = 0.4f),
                                    shape = RoundedCornerShape(16.dp),
                                    modifier = Modifier.fillMaxWidth()
                                ) {
                                    Text(
                                        "Bu rapor, paylaştığınız duygu durum kayıtlarının gözlemsel bir özetidir. Kesinlikle tıbbi bir teşhis veya klinik tedavi planı niteliği taşımaz. Kendinizi dinlemek ve iyi gelen önerileri seçmek tamamen sizin kontrolünüzdedir.",
                                        fontSize = 10.sp,
                                        lineHeight = 16.sp,
                                        color = LoginSecondaryText.copy(alpha = 0.7f),
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
