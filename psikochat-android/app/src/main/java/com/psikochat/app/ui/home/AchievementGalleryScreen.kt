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
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Lock
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
import androidx.navigation.NavController
import com.psikochat.app.data.local.AppDatabase
import com.psikochat.app.data.local.TokenManager
import com.psikochat.app.ui.theme.*

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AchievementGalleryScreen(
    navController: NavController,
    tokenManager: TokenManager
) {
    val context = androidx.compose.ui.platform.LocalContext.current
    val db = AppDatabase.getInstance(context)

    val usernameFlow = remember { tokenManager.getUsername() }
    val username by usernameFlow.collectAsState(initial = "")

    // Observe all local Room flows
    val messagesFlow = remember(username) { db.chatDao().getAllCachedMessages(username) }
    val messages by messagesFlow.collectAsState(initial = emptyList())

    val moodsFlow = remember(username) { db.moodJournalDao().getCachedMoodJournals(username) }
    val moods by moodsFlow.collectAsState(initial = emptyList())

    val appointmentsFlow = remember { db.appointmentDao().getAllAppointments() }
    val appointments by appointmentsFlow.collectAsState(initial = emptyList())

    // Compute streak and achievements
    val streak = remember(messages, moods) {
        StreakEngine.computeStreakSummary(messages, moods)
    }
    val achievements = remember(messages, moods, appointments, streak) {
        AchievementEngine.computeAchievements(messages, moods, appointments, streak)
    }

    val unlockedCount = achievements.count { it.unlocked }
    val totalCount = achievements.size
    val progressFraction = if (totalCount > 0) unlockedCount.toFloat() / totalCount else 0f

    val scrollState = rememberScrollState()

    Scaffold(
        topBar = {
            CenterAlignedTopAppBar(
                title = {
                    Text(
                        "Başarılar",
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
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .verticalScroll(scrollState)
                .padding(horizontal = 20.dp, vertical = 8.dp)
        ) {

            // ── Summary Card ──────────────────────────────────────────────────
            Surface(
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(24.dp),
                color = PremiumWhiteCard,
                shadowElevation = 2.dp,
                border = BorderStroke(1.dp, SoftMintAccent.copy(alpha = 0.5f))
            ) {
                Column(modifier = Modifier.padding(20.dp)) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.SpaceBetween
                    ) {
                        Column {
                            Text(
                                text = "$unlockedCount / $totalCount başarı tamamlandı",
                                fontWeight = FontWeight.Bold,
                                fontSize = 17.sp,
                                color = LoginTextColor
                            )
                            Spacer(modifier = Modifier.height(2.dp))
                            Text(
                                text = if (unlockedCount == 0)
                                    "Küçük adımlarla başarılarını açmaya başlayabilirsin."
                                else if (unlockedCount == totalCount)
                                    "Tüm başarıları tamamladın! 🎉"
                                else
                                    "Harika gidiyorsun, devam et! 💪",
                                fontSize = 12.sp,
                                color = LoginSecondaryText,
                                lineHeight = 16.sp
                            )
                        }
                        // Circle badge with count
                        Box(
                            modifier = Modifier
                                .size(52.dp)
                                .clip(CircleShape)
                                .background(
                                    if (unlockedCount > 0) SoftMintAccent
                                    else SoftMintAccent.copy(alpha = 0.3f)
                                ),
                            contentAlignment = Alignment.Center
                        ) {
                            Text(
                                text = "$unlockedCount",
                                fontSize = 20.sp,
                                fontWeight = FontWeight.Black,
                                color = DarkTealPrimary
                            )
                        }
                    }

                    Spacer(modifier = Modifier.height(14.dp))

                    // Progress bar
                    Box(
                        modifier = Modifier
                            .fillMaxWidth()
                            .height(8.dp)
                            .clip(CircleShape)
                            .background(SoftMintAccent.copy(alpha = 0.3f))
                    ) {
                        val animatedProgress by animateFloatAsState(
                            targetValue = progressFraction,
                            animationSpec = tween(durationMillis = 700, easing = FastOutSlowInEasing),
                            label = "achievementProgress"
                        )
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

            Spacer(modifier = Modifier.height(24.dp))

            // ── Category groups ───────────────────────────────────────────────
            val categories = achievements.map { it.category }.distinct()
            categories.forEach { category ->
                val categoryItems = achievements.filter { it.category == category }

                Text(
                    text = category,
                    fontSize = 13.sp,
                    fontWeight = FontWeight.Bold,
                    color = SecondaryTealText,
                    modifier = Modifier.padding(start = 4.dp, bottom = 10.dp)
                )

                Column(
                    verticalArrangement = Arrangement.spacedBy(10.dp),
                    modifier = Modifier.padding(bottom = 20.dp)
                ) {
                    categoryItems.forEach { achievement ->
                        AchievementCard(achievement = achievement)
                    }
                }
            }

            Spacer(modifier = Modifier.height(16.dp))

            // ── Disclaimer ────────────────────────────────────────────────────
            Surface(
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(16.dp),
                color = Color.White.copy(alpha = 0.4f)
            ) {
                Text(
                    text = "Başarılar, yalnızca uygulama içi etkileşimlerine göre hesaplanır ve tamamen yerel verilerden türetilir. Hiçbir başarı yapay olarak atanmaz.",
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

@Composable
private fun AchievementCard(achievement: AchievementItem) {
    val unlockedBg = SoftMintLight
    val lockedBg = Color(0xFFF8F8F8)
    val unlockedBorder = DarkTealPrimary.copy(alpha = 0.2f)
    val lockedBorder = SoftMintAccent.copy(alpha = 0.3f)

    Surface(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(18.dp),
        color = if (achievement.unlocked) unlockedBg else lockedBg,
        border = BorderStroke(1.dp, if (achievement.unlocked) unlockedBorder else lockedBorder),
        shadowElevation = if (achievement.unlocked) 1.dp else 0.dp
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 16.dp, vertical = 14.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            // Icon container
            Box(
                modifier = Modifier
                    .size(48.dp)
                    .clip(CircleShape)
                    .background(
                        if (achievement.unlocked)
                            SoftMintAccent
                        else
                            Color.LightGray.copy(alpha = 0.25f)
                    ),
                contentAlignment = Alignment.Center
            ) {
                Icon(
                    imageVector = achievement.icon,
                    contentDescription = null,
                    tint = if (achievement.unlocked) DarkTealPrimary else Color.Gray.copy(alpha = 0.5f),
                    modifier = Modifier.size(22.dp)
                )
            }

            Spacer(modifier = Modifier.width(14.dp))

            // Text content
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = achievement.title,
                    fontWeight = FontWeight.Bold,
                    fontSize = 14.sp,
                    color = if (achievement.unlocked) LoginTextColor else LoginSecondaryText
                )
                Spacer(modifier = Modifier.height(3.dp))
                Text(
                    text = achievement.description,
                    fontSize = 11.sp,
                    color = LoginSecondaryText.copy(alpha = if (achievement.unlocked) 1f else 0.65f),
                    lineHeight = 15.sp
                )
                Spacer(modifier = Modifier.height(5.dp))
                // Progress / status chip
                Surface(
                    shape = RoundedCornerShape(8.dp),
                    color = if (achievement.unlocked)
                        DarkTealPrimary.copy(alpha = 0.08f)
                    else
                        Color.Gray.copy(alpha = 0.08f)
                ) {
                    Text(
                        text = achievement.progressText,
                        fontSize = 10.sp,
                        fontWeight = FontWeight.Medium,
                        color = if (achievement.unlocked) DarkTealPrimary else SecondaryTealText,
                        modifier = Modifier.padding(horizontal = 8.dp, vertical = 3.dp)
                    )
                }
            }

            Spacer(modifier = Modifier.width(10.dp))

            // Lock / check badge
            Box(
                modifier = Modifier
                    .size(28.dp)
                    .clip(CircleShape)
                    .background(
                        if (achievement.unlocked)
                            DarkTealPrimary.copy(alpha = 0.12f)
                        else
                            Color.Gray.copy(alpha = 0.08f)
                    ),
                contentAlignment = Alignment.Center
            ) {
                Icon(
                    imageVector = if (achievement.unlocked)
                        Icons.Default.CheckCircle
                    else
                        Icons.Default.Lock,
                    contentDescription = if (achievement.unlocked) "Tamamlandı" else "Kilitli",
                    tint = if (achievement.unlocked) DarkTealPrimary else Color.Gray.copy(alpha = 0.4f),
                    modifier = Modifier.size(16.dp)
                )
            }
        }
    }
}
