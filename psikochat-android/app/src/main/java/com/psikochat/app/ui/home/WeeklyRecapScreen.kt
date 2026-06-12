package com.psikochat.app.ui.home

import androidx.compose.animation.core.*
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowLeft
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.navigation.NavController
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewmodel.compose.viewModel
import com.psikochat.app.data.api.RetrofitClient
import com.psikochat.app.data.repository.SubscriptionRepository
import com.psikochat.app.ui.home.SubscriptionViewModel
import com.psikochat.app.ui.components.PremiumLockedCard
import com.psikochat.app.data.local.AppDatabase
import com.psikochat.app.data.local.TokenManager
import com.psikochat.app.ui.theme.*

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun WeeklyRecapScreen(
    navController: NavController,
    tokenManager: TokenManager
) {
    val context = LocalContext.current
    val db = AppDatabase.getInstance(context)

    val api = remember { RetrofitClient.create(tokenManager) }
    val subscriptionRepo = remember { SubscriptionRepository(api) }
    val subscriptionFactory = remember {
        object : ViewModelProvider.Factory {
            @Suppress("UNCHECKED_CAST")
            override fun <T : ViewModel> create(modelClass: Class<T>): T {
                return SubscriptionViewModel(subscriptionRepo) as T
            }
        }
    }
    val subscriptionViewModel: SubscriptionViewModel = viewModel(factory = subscriptionFactory)
    val isPremiumUser by subscriptionViewModel.isPremium.collectAsState()
    val isLoadingSubscription by subscriptionViewModel.isLoading.collectAsState()

    val usernameFlow = remember { tokenManager.getUsername() }
    val username by usernameFlow.collectAsState(initial = "")

    // ── Local data flows ─────────────────────────────────────────────────────
    val messagesFlow = remember(username) { db.chatDao().getCachedMessages(username) }
    val messages by messagesFlow.collectAsState(initial = emptyList())

    val moodsFlow = remember(username) { db.moodJournalDao().getCachedMoodJournals(username) }
    val moods by moodsFlow.collectAsState(initial = emptyList())

    val appointmentsFlow = remember { db.appointmentDao().getAllAppointments() }
    val appointments by appointmentsFlow.collectAsState(initial = emptyList())

    val snapshotsFlow = remember { db.scoreSnapshotDao().getAllSnapshots() }
    val snapshots by snapshotsFlow.collectAsState(initial = emptyList())

    // ── Compute engines ──────────────────────────────────────────────────────
    val streak = remember(messages, moods) {
        StreakEngine.computeStreakSummary(messages, moods)
    }
    val achievements = remember(messages, moods, appointments, streak) {
        AchievementEngine.computeAchievements(messages, moods, appointments, streak)
    }
    val recap = remember(messages, moods, appointments, snapshots, streak, achievements) {
        WeeklyRecapEngine.compute(messages, moods, appointments, snapshots, streak, achievements)
    }

    val scrollState = rememberScrollState()

    Scaffold(
        topBar = {
            CenterAlignedTopAppBar(
                title = {
                    Text(
                        "Haftalık Özet",
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Bold,
                        color = LoginTextColor
                    )
                },
                navigationIcon = {
                    IconButton(onClick = { navController.popBackStack() }) {
                        Icon(
                            Icons.AutoMirrored.Filled.KeyboardArrowLeft,
                            contentDescription = "Geri",
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
        if (isLoadingSubscription && subscriptionViewModel.currentSubscription.value == null) {
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(padding),
                contentAlignment = Alignment.Center
            ) {
                CircularProgressIndicator(color = DarkTealPrimary)
            }
        } else if (!isPremiumUser) {
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(padding)
                    .padding(20.dp),
                contentAlignment = Alignment.Center
            ) {
                PremiumLockedCard(
                    title = "Premium Özet",
                    description = "Haftalık iyi oluş özetiniz, skor değişimleriniz ve kazanımlarınız Premium üyelikle açılır.",
                    ctaText = "Premium'a Geç",
                    onUpgradeClick = { navController.navigate("payment_methods") }
                )
            }
        } else {
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(padding)
                    .verticalScroll(scrollState)
                    .padding(horizontal = 20.dp, vertical = 8.dp)
            ) {

            // ── Empty state ───────────────────────────────────────────────────
            if (!recap.hasAnyActivity) {
                Spacer(modifier = Modifier.height(24.dp))
                EmptyWeeklyRecapCard()
                Spacer(modifier = Modifier.height(24.dp))
            }

            // ── Hero summary card ────────────────────────────────────────────
            Surface(
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(24.dp),
                color = DarkTealPrimary,
                shadowElevation = 3.dp
            ) {
                Column(modifier = Modifier.padding(20.dp)) {
                    Text(
                        text = "Bu haftaki iyi oluş yolculuğun",
                        fontSize = 12.sp,
                        color = Color.White.copy(alpha = 0.75f),
                        fontWeight = FontWeight.Medium
                    )
                    Spacer(modifier = Modifier.height(6.dp))
                    Text(
                        text = if (recap.hasAnyActivity)
                            "Geçen 7 günde ${recap.totalMessagesThisWeek + recap.moodEntriesThisWeek} aktivite tamamlandı"
                        else
                            "Bu hafta henüz veri oluşmadı",
                        fontSize = 18.sp,
                        fontWeight = FontWeight.Black,
                        color = Color.White
                    )
                    Spacer(modifier = Modifier.height(12.dp))
                    // Date range label
                    Text(
                        text = buildWeekRangeLabel(),
                        fontSize = 11.sp,
                        color = Color.White.copy(alpha = 0.6f)
                    )
                }
            }

            Spacer(modifier = Modifier.height(20.dp))

            // ── Metric cards 2×2 grid ────────────────────────────────────────
            Text(
                "Bu Hafta",
                fontSize = 13.sp,
                fontWeight = FontWeight.Bold,
                color = LoginTextColor,
                modifier = Modifier.padding(start = 4.dp, bottom = 12.dp)
            )

            Row(modifier = Modifier.fillMaxWidth()) {
                RecapMetricCard(
                    icon = Icons.Default.Email,
                    label = "Sohbet",
                    value = recap.totalMessagesThisWeek.toString(),
                    subtitle = "mesaj",
                    modifier = Modifier.weight(1f)
                )
                Spacer(modifier = Modifier.width(12.dp))
                RecapMetricCard(
                    icon = Icons.Default.Edit,
                    label = "Ruh Hali Kaydı",
                    value = recap.moodEntriesThisWeek.toString(),
                    subtitle = "kayıt",
                    modifier = Modifier.weight(1f)
                )
            }
            Spacer(modifier = Modifier.height(12.dp))
            Row(modifier = Modifier.fillMaxWidth()) {
                RecapMetricCard(
                    icon = Icons.Default.DateRange,
                    label = "Randevu",
                    value = recap.appointmentsThisWeek.toString(),
                    subtitle = "randevu",
                    modifier = Modifier.weight(1f)
                )
                Spacer(modifier = Modifier.width(12.dp))
                RecapMetricCard(
                    icon = Icons.Default.Star,
                    label = "Seri",
                    value = if (recap.activeStreakDays == 0) "—" else "${recap.activeStreakDays}",
                    subtitle = if (recap.activeStreakDays == 0) "başlayalım!" else "gün aktif",
                    modifier = Modifier.weight(1f)
                )
            }

            Spacer(modifier = Modifier.height(20.dp))

            // ── Wellness score delta card ─────────────────────────────────────
            Text(
                "Wellness Skoru",
                fontSize = 13.sp,
                fontWeight = FontWeight.Bold,
                color = LoginTextColor,
                modifier = Modifier.padding(start = 4.dp, bottom = 12.dp)
            )

            val isPositiveDelta = recap.wellnessScoreDeltaText.startsWith("+")
            val isNegativeDelta = recap.wellnessScoreDeltaText.startsWith("-")
            val deltaCardColor = when {
                isPositiveDelta -> SoftMintLight
                isNegativeDelta -> MildAlertBg
                else -> PremiumWhiteCard
            }
            val deltaBorderColor = when {
                isPositiveDelta -> DarkTealPrimary.copy(alpha = 0.2f)
                isNegativeDelta -> MildAlertText.copy(alpha = 0.2f)
                else -> SoftMintAccent.copy(alpha = 0.4f)
            }
            val deltaTextColor = when {
                isPositiveDelta -> DarkTealPrimary
                isNegativeDelta -> MildAlertText
                else -> LoginSecondaryText
            }

            Surface(
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(20.dp),
                color = deltaCardColor,
                border = BorderStroke(1.dp, deltaBorderColor)
            ) {
                Row(
                    modifier = Modifier.padding(16.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Box(
                        modifier = Modifier
                            .size(44.dp)
                            .clip(CircleShape)
                            .background(
                                if (isPositiveDelta) SoftMintAccent
                                else if (isNegativeDelta) MildAlertBg
                                else SoftMintAccent.copy(alpha = 0.3f)
                            ),
                        contentAlignment = Alignment.Center
                    ) {
                        Text(
                            text = when {
                                isPositiveDelta -> "📈"
                                isNegativeDelta -> "📉"
                                else -> "📊"
                            },
                            fontSize = 20.sp
                        )
                    }
                    Spacer(modifier = Modifier.width(14.dp))
                    Column {
                        Text(
                            text = "7 Günlük Değişim",
                            fontSize = 12.sp,
                            fontWeight = FontWeight.Bold,
                            color = LoginSecondaryText
                        )
                        Spacer(modifier = Modifier.height(3.dp))
                        Text(
                            text = recap.wellnessScoreDeltaText,
                            fontSize = 16.sp,
                            fontWeight = FontWeight.Black,
                            color = deltaTextColor
                        )
                    }
                }
            }

            Spacer(modifier = Modifier.height(20.dp))

            // ── Dominant mood card ────────────────────────────────────────────
            Text(
                "Baskın Duygu Durumu",
                fontSize = 13.sp,
                fontWeight = FontWeight.Bold,
                color = LoginTextColor,
                modifier = Modifier.padding(start = 4.dp, bottom = 12.dp)
            )

            Surface(
                modifier = Modifier.fillMaxWidth(),
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
                        Text("😊", fontSize = 22.sp)
                    }
                    Spacer(modifier = Modifier.width(14.dp))
                    Column {
                        Text(
                            text = "Bu haftaki dominant duygu",
                            fontSize = 12.sp,
                            color = LoginSecondaryText
                        )
                        Spacer(modifier = Modifier.height(3.dp))
                        Text(
                            text = recap.dominantMoodText,
                            fontSize = 16.sp,
                            fontWeight = FontWeight.Bold,
                            color = LoginTextColor
                        )
                    }
                }
            }

            Spacer(modifier = Modifier.height(20.dp))

            // ── Achievement summary card ──────────────────────────────────────
            Text(
                "Başarı Durumu",
                fontSize = 13.sp,
                fontWeight = FontWeight.Bold,
                color = LoginTextColor,
                modifier = Modifier.padding(start = 4.dp, bottom = 12.dp)
            )

            Surface(
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(20.dp),
                color = PremiumWhiteCard,
                border = BorderStroke(1.dp, SoftMintAccent.copy(alpha = 0.5f))
            ) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.SpaceBetween
                    ) {
                        Text(
                            text = "${recap.unlockedAchievementsCount} / 6 başarı tamamlandı",
                            fontWeight = FontWeight.Bold,
                            fontSize = 15.sp,
                            color = LoginTextColor
                        )
                        Text(text = "🏆", fontSize = 22.sp)
                    }
                    Spacer(modifier = Modifier.height(12.dp))

                    // Animated progress bar
                    val progressFraction = recap.unlockedAchievementsCount / 6f
                    val animatedProgress by animateFloatAsState(
                        targetValue = progressFraction,
                        animationSpec = tween(700, easing = FastOutSlowInEasing),
                        label = "achievementProgressRecap"
                    )
                    Box(
                        modifier = Modifier
                            .fillMaxWidth()
                            .height(7.dp)
                            .clip(CircleShape)
                            .background(SoftMintAccent.copy(alpha = 0.3f))
                    ) {
                        Box(
                            modifier = Modifier
                                .fillMaxWidth(animatedProgress)
                                .fillMaxHeight()
                                .clip(CircleShape)
                                .background(DarkTealPrimary)
                        )
                    }
                }
            }

            Spacer(modifier = Modifier.height(20.dp))

            // ── Motivational message card ─────────────────────────────────────
            Surface(
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(20.dp),
                color = DarkTealPrimary.copy(alpha = 0.07f),
                border = BorderStroke(1.dp, DarkTealPrimary.copy(alpha = 0.15f))
            ) {
                Row(
                    modifier = Modifier.padding(16.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text(text = "💡", fontSize = 24.sp)
                    Spacer(modifier = Modifier.width(14.dp))
                    Text(
                        text = recap.motivationalMessage,
                        fontSize = 13.sp,
                        color = LoginTextColor,
                        lineHeight = 19.sp,
                        fontWeight = FontWeight.Medium
                    )
                }
            }

            Spacer(modifier = Modifier.height(28.dp))

            // ── Disclaimer ────────────────────────────────────────────────────
            Surface(
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(16.dp),
                color = Color.White.copy(alpha = 0.4f)
            ) {
                Text(
                    text = "Bu özet, yalnızca yerel cihaz verilerinden hesaplanmıştır. Herhangi bir icat edilmiş değer içermez.",
                    fontSize = 10.sp,
                    lineHeight = 15.sp,
                    color = LoginTextColor.copy(alpha = 0.5f),
                    modifier = Modifier.padding(14.dp),
                    textAlign = TextAlign.Center
                )
            }

            Spacer(modifier = Modifier.height(24.dp))
        }
        }
    }
}

@Composable
private fun EmptyWeeklyRecapCard() {
    Surface(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(20.dp),
        color = PremiumWhiteCard,
        border = BorderStroke(1.dp, SoftMintAccent.copy(alpha = 0.5f))
    ) {
        Column(
            modifier = Modifier.padding(20.dp),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            Text(text = "🌱", fontSize = 36.sp)
            Spacer(modifier = Modifier.height(10.dp))
            Text(
                text = "Bu hafta henüz veri oluşmadı",
                fontWeight = FontWeight.Bold,
                fontSize = 15.sp,
                color = LoginTextColor,
                textAlign = TextAlign.Center
            )
            Spacer(modifier = Modifier.height(6.dp))
            Text(
                text = "Bir sohbet başlatarak veya ruh hali kaydı ekleyerek haftalık özetini oluşturmaya başlayabilirsin.",
                fontSize = 12.sp,
                color = LoginSecondaryText,
                lineHeight = 17.sp,
                textAlign = TextAlign.Center
            )
        }
    }
}

@Composable
private fun RecapMetricCard(
    icon: ImageVector,
    label: String,
    value: String,
    subtitle: String,
    modifier: Modifier = Modifier
) {
    Surface(
        modifier = modifier,
        shape = RoundedCornerShape(18.dp),
        color = PremiumWhiteCard,
        border = BorderStroke(1.dp, SoftMintAccent.copy(alpha = 0.5f)),
        shadowElevation = 1.dp
    ) {
        Column(
            modifier = Modifier.padding(14.dp)
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Box(
                    modifier = Modifier
                        .size(30.dp)
                        .clip(CircleShape)
                        .background(SoftMintAccent.copy(alpha = 0.4f)),
                    contentAlignment = Alignment.Center
                ) {
                    Icon(
                        imageVector = icon,
                        contentDescription = null,
                        tint = DarkTealPrimary,
                        modifier = Modifier.size(14.dp)
                    )
                }
                Spacer(modifier = Modifier.width(8.dp))
                Text(
                    text = label,
                    fontSize = 11.sp,
                    fontWeight = FontWeight.Bold,
                    color = LoginSecondaryText
                )
            }
            Spacer(modifier = Modifier.height(10.dp))
            Text(
                text = value,
                fontSize = 28.sp,
                fontWeight = FontWeight.Black,
                color = LoginTextColor
            )
            Text(
                text = subtitle,
                fontSize = 11.sp,
                color = SecondaryTealText
            )
        }
    }
}

private fun buildWeekRangeLabel(): String {
    val sdf = java.text.SimpleDateFormat("d MMM", java.util.Locale("tr"))
    val end = java.util.Calendar.getInstance()
    val start = java.util.Calendar.getInstance().apply { add(java.util.Calendar.DAY_OF_YEAR, -6) }
    return "${sdf.format(start.time)} – ${sdf.format(end.time)}"
}
