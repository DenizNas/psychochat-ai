package com.psikochat.app.ui.insights

// ============================================================================
// DEPRECATED / UNUSED DUPLICATE
// ============================================================================
// DO NOT USE THIS CLASS. The active and maintained version of WellnessReportScreen
// is located under `com.psikochat.app.ui.home.WellnessReportScreen` which is mapped
// in `MainActivity.kt`'s navigation host.
// ============================================================================

import androidx.compose.animation.*
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.Star
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Brush
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
import com.psikochat.app.data.model.WellnessReport
import com.psikochat.app.data.repository.ReflectionRepository
import com.psikochat.app.ui.theme.*
import com.psikochat.app.ui.components.PremiumLockedCard

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun WellnessReportScreen(navController: NavController, tokenManager: TokenManager) {
    val api = RetrofitClient.create(tokenManager)
    val repo = ReflectionRepository(api)
    val factory = object : ViewModelProvider.Factory {
        override fun <T : ViewModel> create(modelClass: Class<T>): T {
            return ReflectionViewModel(repo) as T
        }
    }
    val viewModel: ReflectionViewModel = viewModel(factory = factory)
    val uiState by viewModel.reportState.collectAsState()

    var selectedPeriod by remember { mutableStateOf("daily") } // "daily" or "weekly"

    LaunchedEffect(selectedPeriod) {
        val days = if (selectedPeriod == "daily") 1 else 7
        viewModel.loadWellnessReport(selectedPeriod, days)
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Text(
                        text = "Wellness Raporları",
                        fontWeight = FontWeight.Bold,
                        fontSize = 20.sp,
                        color = LoginTextColor
                    )
                },
                navigationIcon = {
                    IconButton(onClick = { navController.popBackStack() }) {
                        Icon(
                            imageVector = Icons.Default.ArrowBack,
                            contentDescription = "Geri",
                            tint = LoginTextColor
                        )
                    }
                },
                actions = {
                    IconButton(onClick = {
                        val days = if (selectedPeriod == "daily") 1 else 7
                        viewModel.loadWellnessReport(selectedPeriod, days)
                    }) {
                        Icon(
                            imageVector = Icons.Default.Refresh,
                            contentDescription = "Yenile",
                            tint = LoginTextColor
                        )
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = LoginBackground,
                    titleContentColor = LoginTextColor,
                    navigationIconContentColor = LoginTextColor,
                    actionIconContentColor = LoginTextColor
                )
            )
        },
        containerColor = LoginBackground
    ) { padding ->
        Column(
            modifier = Modifier
                .padding(padding)
                .fillMaxSize()
        ) {
            // Period selector tabs
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(16.dp)
                    .background(PremiumWhiteCard, RoundedCornerShape(12.dp))
                    .padding(4.dp),
                horizontalArrangement = Arrangement.SpaceEvenly
            ) {
                listOf("daily" to "Günlük Rapor", "weekly" to "Haftalık Rapor").forEach { (periodKey, label) ->
                    val isSelected = selectedPeriod == periodKey
                    Box(
                        modifier = Modifier
                            .weight(1f)
                            .background(
                                color = if (isSelected) AccentPrimary else Color.Transparent,
                                shape = RoundedCornerShape(8.dp)
                            )
                            .clickable { selectedPeriod = periodKey }
                            .padding(vertical = 10.dp),
                        contentAlignment = Alignment.Center
                    ) {
                        Text(
                            text = label,
                            color = if (isSelected) DarkTealPrimary else LoginSecondaryText,
                            fontWeight = FontWeight.Bold,
                            fontSize = 14.sp
                        )
                    }
                }
            }

            AnimatedContent(
                targetState = uiState,
                transitionSpec = {
                    fadeIn() togetherWith fadeOut()
                },
                label = "wellness_state_transition"
            ) { state ->
                when (state) {
                    is WellnessReportUiState.Loading -> {
                        Box(
                            modifier = Modifier.fillMaxSize(),
                            contentAlignment = Alignment.Center
                        ) {
                            CircularProgressIndicator(color = DarkTealPrimary)
                        }
                    }
                    is WellnessReportUiState.Success -> {
                        ReportContent(
                            report = state.report,
                            onNavigateToReflections = {
                                navController.navigate("reflections")
                            }
                        )
                    }
                    is WellnessReportUiState.Empty -> {
                        WellnessEmptyStateView()
                    }
                    is WellnessReportUiState.Error -> {
                        if (state.isPremiumRequired) {
                            Box(
                                modifier = Modifier.fillMaxSize().padding(16.dp),
                                contentAlignment = Alignment.Center
                            ) {
                                PremiumLockedCard(
                                    title = "Premium Rapor",
                                    description = "Gelişmiş iyi oluş analizleri ve kişisel raporlar Premium üyelikle açılır.",
                                    ctaText = "Premium'a Geç",
                                    onUpgradeClick = { navController.navigate("payment_methods") }
                                )
                            }
                        } else {
                            WellnessErrorStateView(
                                message = state.message,
                                onRetry = {
                                    val days = if (selectedPeriod == "daily") 1 else 7
                                    viewModel.loadWellnessReport(selectedPeriod, days)
                                }
                            )
                        }
                    }
                }
            }
        }
    }
}

// WellnessReport is the real model from Models.kt (not WellnessReportResponse)
@Composable
fun ReportContent(report: WellnessReport, onNavigateToReflections: () -> Unit) {
    // Use camelCase fields from WellnessReport data class
    val pastelAccent = when (report.dominantEmotion.lowercase()) {
        "mutluluk", "happiness", "joy" -> Color(0xFF86EFAC)
        "kaygı", "anxiety", "stres", "stress" -> Color(0xFFFCD34D)
        "üzüntü", "sadness", "sad" -> Color(0xFF93C5FD)
        "öfke", "anger", "angry" -> Color(0xFFFCA5A5)
        else -> Color(0xFF94A3B8)
    }

    LazyColumn(
        modifier = Modifier
            .fillMaxSize()
            .padding(horizontal = 16.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
        contentPadding = PaddingValues(bottom = 24.dp)
    ) {
        // AI Reflection Entry Banner
        item {
            Card(
                modifier = Modifier
                    .fillMaxWidth()
                    .clickable { onNavigateToReflections() },
                colors = CardDefaults.cardColors(containerColor = PremiumWhiteCard),
                border = BorderStroke(1.5.dp, Brush.horizontalGradient(listOf(DarkTealPrimary, pastelAccent))),
                shape = RoundedCornerShape(16.dp)
            ) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(16.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Box(
                        modifier = Modifier
                            .size(48.dp)
                            .background(DarkTealPrimary.copy(alpha = 0.1f), RoundedCornerShape(12.dp)),
                        contentAlignment = Alignment.Center
                    ) {
                        // Icons.Default.AutoAwesome is not available — using Icons.Default.Star instead
                        Icon(
                            imageVector = Icons.Default.Star,
                            contentDescription = "AI Reflection",
                            tint = DarkTealPrimary,
                            modifier = Modifier.size(24.dp)
                        )
                    }
                    Spacer(modifier = Modifier.width(16.dp))
                    Column(
                        modifier = Modifier.weight(1f)
                    ) {
                        Text(
                            text = "AI Refleksiyon Özetleri",
                            fontWeight = FontWeight.Bold,
                            fontSize = 16.sp,
                            color = LoginTextColor
                        )
                        Text(
                            text = "Duygu dalgalanmalarınızı ve kişisel seyrinizi derinlemesine inceleyin.",
                            fontSize = 12.sp,
                            color = LoginSecondaryText
                        )
                    }
                }
            }
        }

        // Summary Card — using camelCase: summaryTitle, dominantEmotion, summaryText
        item {
            Card(
                modifier = Modifier.fillMaxWidth(),
                colors = CardDefaults.cardColors(containerColor = PremiumWhiteCard),
                shape = RoundedCornerShape(16.dp)
            ) {
                Column(
                    modifier = Modifier.padding(16.dp)
                ) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text(
                            text = report.summaryTitle,
                            fontWeight = FontWeight.Bold,
                            fontSize = 18.sp,
                            color = LoginTextColor,
                            modifier = Modifier.weight(1f)
                        )
                        Spacer(modifier = Modifier.width(8.dp))
                        Box(
                            modifier = Modifier
                                .background(pastelAccent.copy(alpha = 0.2f), RoundedCornerShape(8.dp))
                                .padding(horizontal = 10.dp, vertical = 4.dp)
                        ) {
                            Text(
                                text = report.dominantEmotion.uppercase(),
                                color = pastelAccent,
                                fontWeight = FontWeight.Bold,
                                fontSize = 11.sp
                            )
                        }
                    }
                    Spacer(modifier = Modifier.height(12.dp))
                    Text(
                        text = report.summaryText,
                        fontSize = 14.sp,
                        color = LoginTextColor.copy(alpha = 0.9f),
                        lineHeight = 20.sp
                    )
                }
            }
        }

        // Highlights Card — using camelCase: highlights
        if (report.highlights.isNotEmpty()) {
            item {
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    colors = CardDefaults.cardColors(containerColor = PremiumWhiteCard),
                    shape = RoundedCornerShape(16.dp)
                ) {
                    Column(
                        modifier = Modifier.padding(16.dp)
                    ) {
                        Text(
                            text = "Öne Çıkan Gözlemler",
                            fontWeight = FontWeight.Bold,
                            fontSize = 16.sp,
                            color = LoginTextColor
                        )
                        Spacer(modifier = Modifier.height(12.dp))
                        report.highlights.forEach { highlight: String ->
                            Row(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .padding(vertical = 4.dp),
                                verticalAlignment = Alignment.Top
                            ) {
                                Text(
                                    text = "•",
                                    color = pastelAccent,
                                    fontWeight = FontWeight.Bold,
                                    fontSize = 18.sp,
                                    modifier = Modifier.padding(end = 8.dp)
                                )
                                Text(
                                    text = highlight,
                                    fontSize = 13.sp,
                                    color = LoginSecondaryText,
                                    lineHeight = 18.sp
                                )
                            }
                        }
                    }
                }
            }
        }

        // Suggestions Card — using camelCase: suggestions
        if (report.suggestions.isNotEmpty()) {
            item {
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    colors = CardDefaults.cardColors(containerColor = PremiumWhiteCard),
                    shape = RoundedCornerShape(16.dp)
                ) {
                    Column(
                        modifier = Modifier.padding(16.dp)
                    ) {
                        Text(
                            text = "Zihinsel Sağlık Önerileri",
                            fontWeight = FontWeight.Bold,
                            fontSize = 16.sp,
                            color = LoginTextColor
                        )
                        Spacer(modifier = Modifier.height(12.dp))
                        report.suggestions.forEach { suggestion: String ->
                            Row(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .padding(vertical = 4.dp),
                                verticalAlignment = Alignment.Top
                            ) {
                                Text(
                                    text = "✦",
                                    color = DarkTealPrimary,
                                    fontWeight = FontWeight.Bold,
                                    fontSize = 14.sp,
                                    modifier = Modifier.padding(end = 8.dp, top = 2.dp)
                                )
                                Text(
                                    text = suggestion,
                                    fontSize = 13.sp,
                                    color = LoginSecondaryText,
                                    lineHeight = 18.sp
                                )
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
fun WellnessEmptyStateView() {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(24.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center
    ) {
        Text(
            text = "Yetersiz Veri",
            fontWeight = FontWeight.Bold,
            fontSize = 18.sp,
            color = LoginTextColor,
            textAlign = TextAlign.Center
        )
        Spacer(modifier = Modifier.height(8.dp))
        Text(
            text = "Kişiselleştirilmiş bir wellness raporu hazırlayabilmemiz için son günlerde en az 4 sohbet mesajı veya mood günlüğü kaydı girmelisiniz.",
            fontSize = 14.sp,
            color = LoginSecondaryText,
            textAlign = TextAlign.Center,
            lineHeight = 20.sp
        )
    }
}

@Composable
fun WellnessErrorStateView(message: String, onRetry: () -> Unit) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(24.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center
    ) {
        Text(
            text = "Rapor Yüklenemedi",
            fontWeight = FontWeight.Bold,
            fontSize = 18.sp,
            color = DangerRed,
            textAlign = TextAlign.Center
        )
        Spacer(modifier = Modifier.height(8.dp))
        Text(
            text = message,
            fontSize = 14.sp,
            color = LoginSecondaryText,
            textAlign = TextAlign.Center
        )
        Spacer(modifier = Modifier.height(16.dp))
        Button(
            onClick = onRetry,
            colors = ButtonDefaults.buttonColors(containerColor = DarkTealPrimary)
        ) {
            Text("Yeniden Dene", color = Color.White)
        }
    }
}
