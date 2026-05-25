package com.psikochat.app.ui.home

import androidx.compose.animation.*
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.ExperimentalMaterialApi
import androidx.compose.material.pullrefresh.PullRefreshIndicator
import androidx.compose.material.pullrefresh.pullRefresh
import androidx.compose.material.pullrefresh.rememberPullRefreshState
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavController
import com.psikochat.app.data.api.RetrofitClient
import com.psikochat.app.data.local.TokenManager
import com.psikochat.app.data.repository.RecommendationRepository
import com.psikochat.app.data.model.WellnessRecommendation
import com.psikochat.app.data.model.Resource
import com.psikochat.app.ui.theme.*
import kotlinx.coroutines.launch

/**
 * RecommendationScreen
 * ====================
 * Faz 10 Prompt 7 — Advanced Analytics & Recommendation Engine
 *
 * Displays personalised wellness recommendation cards.
 * UI language: calm, supportive, non-judgmental, diagnosis-free.
 *
 * Features:
 *   - Pull-to-refresh for fresh recommendations
 *   - Priority badges (high / medium / low)
 *   - Confidence gentle indicator (progress bar, no numeric overwhelm)
 *   - Action button per recommendation
 *   - Dismiss / Helpful / Not Helpful feedback
 *   - Loading / Empty / Error states
 *   - Consent-gated empty state (wellness_insights_consent = false)
 */
@OptIn(ExperimentalMaterial3Api::class, ExperimentalMaterialApi::class)
@Composable
fun RecommendationScreen(
    navController: NavController,
    tokenManager: TokenManager
) {
    val api = RetrofitClient.create(tokenManager)
    val repository = RecommendationRepository(api)
    val factory = object : ViewModelProvider.Factory {
        override fun <T : ViewModel> create(modelClass: Class<T>): T {
            return RecommendationViewModel(repository) as T
        }
    }
    val viewModel: RecommendationViewModel = viewModel(factory = factory)
    val state by viewModel.state.collectAsState()
    val isRefreshing by viewModel.isRefreshing.collectAsState()
    val feedbackState by viewModel.feedbackState.collectAsState()
    val snackbarHostState = remember { SnackbarHostState() }
    val scope = rememberCoroutineScope()

    val pullRefreshState = rememberPullRefreshState(
        refreshing = isRefreshing,
        onRefresh = { viewModel.refresh() }
    )

    // Handle feedback state → snackbar
    LaunchedEffect(feedbackState) {
        when (feedbackState) {
            is FeedbackUiState.Success -> {
                val fb = (feedbackState as FeedbackUiState.Success).feedback
                val msg = when (fb) {
                    "helpful" -> "Teşekkürler! Geri bildiriminiz kaydedildi."
                    "not_helpful" -> "Anlıyoruz. Öneri listenizi güncelliyoruz."
                    "dismissed" -> "Öneri kaldırıldı."
                    else -> "Geri bildirim kaydedildi."
                }
                snackbarHostState.showSnackbar(msg, duration = SnackbarDuration.Short)
                viewModel.resetFeedbackState()
            }
            is FeedbackUiState.Error -> {
                val err = (feedbackState as FeedbackUiState.Error).message
                snackbarHostState.showSnackbar(err, duration = SnackbarDuration.Short)
                viewModel.resetFeedbackState()
            }
            else -> {}
        }
    }

    Scaffold(
        snackbarHost = { SnackbarHost(snackbarHostState) },
        topBar = {
            CenterAlignedTopAppBar(
                title = {
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        Text(
                            "Wellness Önerileri",
                            style = MaterialTheme.typography.titleMedium,
                            fontWeight = FontWeight.Bold,
                            color = LoginTextColor
                        )
                        Text(
                            "Sana özel, destekleyici ipuçları",
                            style = MaterialTheme.typography.labelSmall,
                            color = LoginTextColor.copy(alpha = 0.6f)
                        )
                    }
                },
                navigationIcon = {
                    IconButton(onClick = { navController.popBackStack() }) {
                        Icon(
                            Icons.Default.ArrowBack,
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

        Box(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .pullRefresh(pullRefreshState)
        ) {
            when (state) {
                is Resource.Loading -> {
                    RecommendationLoadingState()
                }

                is Resource.Error -> {
                    RecommendationErrorState(
                        message = (state as Resource.Error).message ?: "Öneriler alınamadı.",
                        onRetry = { viewModel.loadRecommendations() }
                    )
                }

                is Resource.Success -> {
                    val recs = (state as Resource.Success<List<WellnessRecommendation>>).data
                        ?.filter { it.status == "active" }
                        ?: emptyList()

                    if (recs.isEmpty()) {
                        RecommendationEmptyState(onRefresh = { viewModel.refresh() })
                    } else {
                        LazyColumn(
                            modifier = Modifier.fillMaxSize(),
                            contentPadding = PaddingValues(
                                horizontal = 20.dp,
                                vertical = 12.dp
                            ),
                            verticalArrangement = Arrangement.spacedBy(14.dp)
                        ) {
                            item {
                                RecommendationHeaderNote()
                            }
                            items(recs, key = { it.id }) { rec ->
                                RecommendationCard(
                                    recommendation = rec,
                                    onAction = { actionType ->
                                        handleRecommendationAction(navController, actionType)
                                    },
                                    onHelpful = {
                                        viewModel.submitFeedback(rec.id, "helpful")
                                    },
                                    onNotHelpful = {
                                        viewModel.submitFeedback(rec.id, "not_helpful")
                                    },
                                    onDismiss = {
                                        viewModel.submitFeedback(rec.id, "dismissed")
                                    }
                                )
                            }
                            item { Spacer(modifier = Modifier.height(24.dp)) }
                        }
                    }
                }
            }

            PullRefreshIndicator(
                refreshing = isRefreshing,
                state = pullRefreshState,
                modifier = Modifier.align(Alignment.TopCenter),
                backgroundColor = Color.White,
                contentColor = LoginButton
            )
        }
    }
}

// ── Recommendation Card ───────────────────────────────────────────────────────

@Composable
fun RecommendationCard(
    recommendation: WellnessRecommendation,
    onAction: (String) -> Unit,
    onHelpful: () -> Unit,
    onNotHelpful: () -> Unit,
    onDismiss: () -> Unit
) {
    var feedbackExpanded by remember { mutableStateOf(false) }

    val (priorityColor, priorityLabel) = when (recommendation.priority) {
        "high"   -> Pair(Color(0xFFFF6B6B), "Önemli")
        "medium" -> Pair(Color(0xFFFFB347), "Orta")
        else     -> Pair(Color(0xFF6BCB77), "Genel")
    }

    val recIcon = recommendationIcon(recommendation.recommendationType)
    val cardGradient = when (recommendation.priority) {
        "high"   -> Brush.linearGradient(listOf(Color(0xFFFFF0F0), Color(0xFFFFE4E4)))
        "medium" -> Brush.linearGradient(listOf(Color(0xFFFFFBF0), Color(0xFFFFF3DC)))
        else     -> Brush.linearGradient(listOf(Color(0xFFF0FFF4), Color(0xFFE8F5E9)))
    }

    Surface(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(20.dp),
        color = Color.Transparent,
        shadowElevation = 3.dp
    ) {
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .background(cardGradient, RoundedCornerShape(20.dp))
        ) {
            Column(modifier = Modifier.padding(18.dp)) {

                // ── Header row: icon + title + priority badge
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    // Recommendation type icon
                    Surface(
                        shape = RoundedCornerShape(12.dp),
                        color = priorityColor.copy(alpha = 0.15f),
                        modifier = Modifier.size(44.dp)
                    ) {
                        Icon(
                            imageVector = recIcon,
                            contentDescription = null,
                            tint = priorityColor,
                            modifier = Modifier.padding(10.dp)
                        )
                    }

                    Spacer(modifier = Modifier.width(12.dp))

                    Column(modifier = Modifier.weight(1f)) {
                        Text(
                            text = recommendation.title,
                            style = MaterialTheme.typography.titleSmall,
                            fontWeight = FontWeight.Bold,
                            color = LoginTextColor,
                            maxLines = 2,
                            overflow = TextOverflow.Ellipsis
                        )
                    }

                    // Priority badge
                    Surface(
                        shape = RoundedCornerShape(8.dp),
                        color = priorityColor.copy(alpha = 0.18f)
                    ) {
                        Text(
                            text = priorityLabel,
                            modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp),
                            color = priorityColor,
                            fontSize = 11.sp,
                            fontWeight = FontWeight.SemiBold
                        )
                    }

                    // Dismiss button
                    IconButton(
                        onClick = onDismiss,
                        modifier = Modifier.size(28.dp)
                    ) {
                        Icon(
                            Icons.Default.Close,
                            contentDescription = "Kaldır",
                            tint = LoginTextColor.copy(alpha = 0.4f),
                            modifier = Modifier.size(16.dp)
                        )
                    }
                }

                Spacer(modifier = Modifier.height(12.dp))

                // ── Description
                Text(
                    text = recommendation.description,
                    style = MaterialTheme.typography.bodySmall,
                    color = LoginTextColor.copy(alpha = 0.78f),
                    lineHeight = 20.sp
                )

                Spacer(modifier = Modifier.height(10.dp))

                // ── Reason (gentle, wellness-safe)
                Surface(
                    shape = RoundedCornerShape(10.dp),
                    color = Color.White.copy(alpha = 0.6f)
                ) {
                    Row(
                        modifier = Modifier.padding(horizontal = 10.dp, vertical = 7.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Icon(
                            Icons.Default.Info,
                            contentDescription = null,
                            tint = LoginButton.copy(alpha = 0.6f),
                            modifier = Modifier.size(14.dp)
                        )
                        Spacer(modifier = Modifier.width(6.dp))
                        Text(
                            text = recommendation.reason,
                            style = MaterialTheme.typography.labelSmall,
                            color = LoginTextColor.copy(alpha = 0.65f),
                            lineHeight = 16.sp
                        )
                    }
                }

                Spacer(modifier = Modifier.height(10.dp))

                // ── Confidence gentle indicator (no number shown — just a progress bar)
                Column {
                    Text(
                        text = "Öneri gücü",
                        style = MaterialTheme.typography.labelSmall,
                        color = LoginTextColor.copy(alpha = 0.5f)
                    )
                    Spacer(modifier = Modifier.height(4.dp))
                    LinearProgressIndicator(
                        progress = recommendation.confidence.coerceIn(0f, 1f),
                        modifier = Modifier
                            .fillMaxWidth()
                            .height(4.dp)
                            .clip(RoundedCornerShape(2.dp)),
                        color = priorityColor,
                        trackColor = priorityColor.copy(alpha = 0.15f)
                    )
                }

                Spacer(modifier = Modifier.height(14.dp))

                // ── Action buttons
                recommendation.actions.firstOrNull()?.let { action ->
                    Button(
                        onClick = { onAction(action.actionType) },
                        modifier = Modifier.fillMaxWidth(),
                        shape = RoundedCornerShape(14.dp),
                        colors = ButtonDefaults.buttonColors(containerColor = LoginButton)
                    ) {
                        Icon(
                            recIcon,
                            contentDescription = null,
                            modifier = Modifier.size(16.dp)
                        )
                        Spacer(modifier = Modifier.width(8.dp))
                        Text(
                            text = action.label,
                            style = MaterialTheme.typography.labelLarge,
                            color = Color.White
                        )
                    }
                }

                Spacer(modifier = Modifier.height(8.dp))

                // ── Feedback row
                AnimatedVisibility(
                    visible = feedbackExpanded,
                    enter = expandVertically() + fadeIn(),
                    exit = shrinkVertically() + fadeOut()
                ) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        OutlinedButton(
                            onClick = {
                                onHelpful()
                                feedbackExpanded = false
                            },
                            modifier = Modifier.weight(1f),
                            shape = RoundedCornerShape(12.dp),
                            colors = ButtonDefaults.outlinedButtonColors(contentColor = Color(0xFF6BCB77))
                        ) {
                            Icon(Icons.Default.ThumbUp, contentDescription = null, modifier = Modifier.size(14.dp))
                            Spacer(modifier = Modifier.width(4.dp))
                            Text("Faydalı", fontSize = 12.sp)
                        }
                        OutlinedButton(
                            onClick = {
                                onNotHelpful()
                                feedbackExpanded = false
                            },
                            modifier = Modifier.weight(1f),
                            shape = RoundedCornerShape(12.dp),
                            colors = ButtonDefaults.outlinedButtonColors(contentColor = Color(0xFFFF6B6B))
                        ) {
                            Icon(Icons.Default.ThumbUp, contentDescription = null, modifier = Modifier.size(14.dp))
                            Spacer(modifier = Modifier.width(4.dp))
                            Text("Değildi", fontSize = 12.sp)
                        }
                    }
                }

                // Toggle feedback
                TextButton(
                    onClick = { feedbackExpanded = !feedbackExpanded },
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Text(
                        text = if (feedbackExpanded) "Gizle" else "Bu öneri nasıldı?",
                        style = MaterialTheme.typography.labelSmall,
                        color = LoginButton.copy(alpha = 0.7f)
                    )
                }
            }
        }
    }
}

// ── Header Note ───────────────────────────────────────────────────────────────

@Composable
private fun RecommendationHeaderNote() {
    Surface(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(16.dp),
        color = LoginButton.copy(alpha = 0.08f)
    ) {
        Row(
            modifier = Modifier.padding(14.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Icon(
                Icons.Default.Lock,
                contentDescription = null,
                tint = LoginButton.copy(alpha = 0.7f),
                modifier = Modifier.size(18.dp)
            )
            Spacer(modifier = Modifier.width(10.dp))
            Text(
                text = "Bu öneriler yalnızca duygu özeti ve ruh hali verilerinden üretilir. " +
                        "Hiçbir sohbet içeriğin kullanılmaz.",
                style = MaterialTheme.typography.labelSmall,
                color = LoginTextColor.copy(alpha = 0.65f),
                lineHeight = 16.sp
            )
        }
    }
}

// ── Empty State ───────────────────────────────────────────────────────────────

@Composable
private fun RecommendationEmptyState(onRefresh: () -> Unit) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(40.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center
    ) {
        Icon(
            Icons.Default.Star,
            contentDescription = null,
            tint = LoginButton.copy(alpha = 0.35f),
            modifier = Modifier.size(72.dp)
        )
        Spacer(modifier = Modifier.height(20.dp))
        Text(
            text = "Henüz önerin yok",
            style = MaterialTheme.typography.titleMedium,
            fontWeight = FontWeight.Bold,
            color = LoginTextColor
        )
        Spacer(modifier = Modifier.height(10.dp))
        Text(
            text = "Biraz daha etkileşimden sonra sana özel kişiselleştirilmiş öneriler burada görünecek. " +
                    "Ya da yenilemek için butona dokun.",
            style = MaterialTheme.typography.bodySmall,
            color = LoginTextColor.copy(alpha = 0.6f),
            lineHeight = 20.sp
        )
        Spacer(modifier = Modifier.height(28.dp))
        Button(
            onClick = onRefresh,
            shape = RoundedCornerShape(14.dp),
            colors = ButtonDefaults.buttonColors(containerColor = LoginButton)
        ) {
            Icon(Icons.Default.Refresh, contentDescription = null, modifier = Modifier.size(18.dp))
            Spacer(modifier = Modifier.width(8.dp))
            Text("Önerileri Yenile")
        }
    }
}

// ── Loading State ─────────────────────────────────────────────────────────────

@Composable
private fun RecommendationLoadingState() {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(20.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center
    ) {
        CircularProgressIndicator(color = LoginButton)
        Spacer(modifier = Modifier.height(16.dp))
        Text(
            text = "Öneriler hazırlanıyor...",
            style = MaterialTheme.typography.bodyMedium,
            color = LoginTextColor.copy(alpha = 0.6f)
        )
    }
}

// ── Error State ───────────────────────────────────────────────────────────────

@Composable
private fun RecommendationErrorState(message: String, onRetry: () -> Unit) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(40.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center
    ) {
        Icon(
            Icons.Default.Warning,
            contentDescription = null,
            tint = Color(0xFFFF6B6B),
            modifier = Modifier.size(56.dp)
        )
        Spacer(modifier = Modifier.height(16.dp))
        Text(
            text = "Öneriler yüklenemedi",
            style = MaterialTheme.typography.titleMedium,
            fontWeight = FontWeight.SemiBold,
            color = LoginTextColor
        )
        Spacer(modifier = Modifier.height(8.dp))
        Text(
            text = message,
            style = MaterialTheme.typography.bodySmall,
            color = LoginTextColor.copy(alpha = 0.55f)
        )
        Spacer(modifier = Modifier.height(24.dp))
        OutlinedButton(
            onClick = onRetry,
            shape = RoundedCornerShape(12.dp)
        ) {
            Text("Tekrar Dene")
        }
    }
}

// ── Helpers ───────────────────────────────────────────────────────────────────

/** Maps recommendation_type to a meaningful Material icon. */
@Composable
private fun recommendationIcon(type: String): ImageVector = when (type) {
    "breathing_break"      -> Icons.Default.Favorite
    "grounding_exercise"   -> Icons.Default.Place
    "short_walk"           -> Icons.Default.PlayArrow
    "hydration_reminder"   -> Icons.Default.Info
    "sleep_routine"        -> Icons.Default.Star
    "journaling_prompt"    -> Icons.Default.Edit
    "social_connection"    -> Icons.Default.Person
    "positive_reflection"  -> Icons.Default.Face
    "professional_support" -> Icons.Default.Phone
    "reduce_screen_time"   -> Icons.Default.Warning
    "focus_break"          -> Icons.Default.Settings
    "mood_checkin"         -> Icons.Default.Check
    else                   -> Icons.Default.Notifications
}

/** Routes action_type to in-app navigation or system action. */
private fun handleRecommendationAction(navController: NavController, actionType: String) {
    when (actionType) {
        "open_journal"              -> navController.navigate("mood_journal")
        "open_mood_checkin"         -> navController.navigate("mood_journal")
        "open_breathing_timer"      -> navController.navigate("wellness_dashboard")
        "open_grounding_exercise"   -> navController.navigate("wellness_dashboard")
        "open_walk_tracker"         -> navController.navigate("wellness_dashboard")
        "show_professional_support_info" -> navController.navigate("therapy")
        "open_positive_reflection"  -> navController.navigate("wellness_dashboard")
        "start_focus_timer"         -> navController.navigate("wellness_dashboard")
        else                        -> navController.navigate("wellness_dashboard")
    }
}
