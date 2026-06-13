package com.psikochat.app

import android.content.Intent
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.navigation
import androidx.navigation.compose.rememberNavController
import com.psikochat.app.ui.auth.LoginScreen
import com.psikochat.app.ui.auth.SplashScreen
import com.psikochat.app.ui.auth.RegistrationScreen
import com.psikochat.app.ui.auth.ForgotPasswordScreen
import com.psikochat.app.ui.auth.OnboardingWizardScreen
import com.psikochat.app.ui.home.HomeScreen
import com.psikochat.app.ui.home.ProfileScreen
import com.psikochat.app.ui.home.SettingsScreen
import com.psikochat.app.ui.home.TherapyScreen
import com.psikochat.app.ui.home.WellnessScheduleScreen
import com.psikochat.app.ui.home.WellnessReportScreen
import com.psikochat.app.ui.home.MoodJournalScreen
import com.psikochat.app.ui.home.WellnessDashboardScreen
import com.psikochat.app.ui.home.MemorySettingsScreen
import com.psikochat.app.ui.home.PrivacyDataScreen
import com.psikochat.app.ui.home.RecommendationScreen
import com.psikochat.app.ui.home.AchievementGalleryScreen
import com.psikochat.app.ui.home.WeeklyRecapScreen
import com.psikochat.app.ui.home.PaymentMethodsScreen
import com.psikochat.app.ui.chat.ChatScreen
import com.psikochat.app.ui.insights.ReflectionScreen
import com.psikochat.app.ui.insights.InsightsScreen

import com.psikochat.app.ui.theme.PsikochatTheme
import com.psikochat.app.data.local.TokenManager
import com.psikochat.app.ui.notification.NotificationHelper
import com.psikochat.app.data.repository.NotificationRepository
import com.psikochat.app.data.api.RetrofitClient
import com.psikochat.app.data.model.Resource
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.first
import androidx.work.Constraints
import androidx.work.NetworkType
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.BackoffPolicy
import androidx.work.WorkManager
import androidx.work.ExistingPeriodicWorkPolicy
import java.util.concurrent.TimeUnit
import com.psikochat.app.ui.notification.NotificationWorker

class MainActivity : ComponentActivity() {

    private val targetRouteFlow = MutableSharedFlow<String>(extraBufferCapacity = 1)

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        
        // 1. Initialize local notification channel and check permissions
        NotificationHelper.createNotificationChannel(this)
        NotificationHelper.checkAndRequestPermission(this)

        // 2. Initialize WorkManager background polling for production/release mode
        if (!BuildConfig.DEBUG) {
            setupProductionWorkManager()
        }

        // Emit initial notification route target if started from intent tap
        intent.getStringExtra("route")?.let { targetRouteFlow.tryEmit(it) }
        handleIntentData(intent)

        val tokenManager = TokenManager(this)
        setContent {
            val themePreference by tokenManager.getThemePreference().collectAsState(initial = "system")
            val darkTheme = when (themePreference) {
                "light" -> false
                "dark" -> true
                else -> androidx.compose.foundation.isSystemInDarkTheme()
            }
            PsikochatTheme(darkTheme = darkTheme) {
                Surface(
                    modifier = Modifier.fillMaxSize(),
                    color = MaterialTheme.colorScheme.background
                ) {
                    val navController = rememberNavController()

                    // Route intent transition observer
                    LaunchedEffect(navController) {
                        targetRouteFlow.collect { route ->
                            if (route.isNotEmpty()) {
                                navController.navigate(route)
                            }
                        }
                    }

                    // Background notification poller triggering every 10 seconds (only in debug mode)
                    if (BuildConfig.DEBUG) {
                        LaunchedEffect(Unit) {
                            while (true) {
                                try {
                                    val token = tokenManager.getToken().first()
                                    if (!token.isNullOrEmpty()) {
                                        val api = RetrofitClient.create(tokenManager)
                                        val repository = NotificationRepository(api)
                                        val result = repository.getNotifications()
                                        if (result is Resource.Success && result.data != null) {
                                            val pending = result.data.filter { it.status == "pending" }
                                            for (event in pending) {
                                                // 1. Fire system notification
                                                NotificationHelper.showNotification(
                                                    this@MainActivity,
                                                    event.id,
                                                    event.title,
                                                    event.body,
                                                    event.notificationType
                                                )
                                                // 2. Report delivery back to database
                                                repository.markNotificationDelivered(event.id)
                                            }
                                        }
                                    }
                                } catch (e: Exception) {
                                    // Graceful connection loss shield
                                }
                                kotlinx.coroutines.delay(10000)
                            }
                        }
                    }

                    NavHost(navController = navController, startDestination = "splash") {
                        composable("splash") { SplashScreen(navController, tokenManager) }
                        composable("onboarding_wizard") { OnboardingWizardScreen(navController, tokenManager) }
                        
                        navigation(startDestination = "login", route = "auth_graph") {
                            composable("login") { LoginScreen(navController, tokenManager) }
                            composable("register") { RegistrationScreen(navController, tokenManager) }
                            composable("forgot_password") { ForgotPasswordScreen(navController) }
                        }
                        
                        navigation(startDestination = "home", route = "main_graph") {
                            composable("home") { HomeScreen(navController, tokenManager) }
                            composable("profile") { ProfileScreen(navController, tokenManager) }
                            composable("settings") { SettingsScreen(navController, tokenManager) }
                            composable("therapy") { TherapyScreen(navController, tokenManager) }
                            composable("chat") { ChatScreen(navController, tokenManager) }
                            composable("chat/{conversationId}") { backStackEntry ->
                                val conversationId = backStackEntry.arguments?.getString("conversationId")
                                val decodedId = java.net.URLDecoder.decode(conversationId ?: "", java.nio.charset.StandardCharsets.UTF_8.toString())
                                ChatScreen(navController, tokenManager, conversationId = decodedId)
                            }
                            composable("chat_history") { com.psikochat.app.ui.chat.ChatHistoryScreen(navController, tokenManager) }
                            composable("wellness_schedule") { WellnessScheduleScreen(navController, tokenManager) }
                            composable("wellness_report") { WellnessReportScreen(navController, tokenManager) }
                            composable("mood_journal") { MoodJournalScreen(navController, tokenManager) }
                            composable("wellness_dashboard") { WellnessDashboardScreen(navController, tokenManager) }
                            composable("reflections") { ReflectionScreen(navController, tokenManager) }
                            composable("insights") { InsightsScreen(navController, tokenManager) }
                            composable("memory_settings") { MemorySettingsScreen(navController, tokenManager) }
                            composable("privacy_data") { PrivacyDataScreen(navController, tokenManager) }
                            // Faz 10 Prompt 7: Recommendation Engine Screen
                            composable("recommendations") { RecommendationScreen(navController, tokenManager) }
                            // Phase 8B.4: Achievement Gallery
                            composable("achievements") { AchievementGalleryScreen(navController, tokenManager) }
                            // Phase 8B.5: Weekly Wellness Recap
                            composable("weekly_recap") { WeeklyRecapScreen(navController, tokenManager) }
                            composable(
                                route = "payment_methods?payment_result={payment_result}",
                                arguments = listOf(
                                    androidx.navigation.navArgument("payment_result") {
                                        type = androidx.navigation.NavType.StringType
                                        nullable = true
                                        defaultValue = null
                                    }
                                )
                            ) { backStackEntry ->
                                val paymentResult = backStackEntry.arguments?.getString("payment_result")
                                PaymentMethodsScreen(navController, tokenManager, paymentResult = paymentResult)
                            }
                        }

                        navigation(startDestination = "psychologist_dashboard", route = "psychologist_graph") {
                            composable("psychologist_dashboard") {
                                com.psikochat.app.ui.psychologist.PsychologistDashboardScreen(navController, tokenManager)
                            }
                        }
                    }
                }
            }
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        intent.getStringExtra("route")?.let { targetRouteFlow.tryEmit(it) }
        handleIntentData(intent)
    }

    private fun handleIntentData(intent: Intent?) {
        val data = intent?.data ?: return
        if (data.scheme == "psikochat" && data.host == "payment" && data.path == "/callback") {
            val paymentResult = data.getQueryParameter("payment_result") ?: "unknown"
            targetRouteFlow.tryEmit("payment_methods?payment_result=$paymentResult")
        }
    }

    private fun setupProductionWorkManager() {
        val constraints = Constraints.Builder()
            .setRequiredNetworkType(NetworkType.CONNECTED)
            .build()

        val workRequest = PeriodicWorkRequestBuilder<NotificationWorker>(
            15, TimeUnit.MINUTES
        )
            .setConstraints(constraints)
            .setBackoffCriteria(
                BackoffPolicy.EXPONENTIAL,
                30,
                TimeUnit.SECONDS
            )
            .build()

        WorkManager.getInstance(this).enqueueUniquePeriodicWork(
            "psychochat_notification_work",
            ExistingPeriodicWorkPolicy.KEEP,
            workRequest
        )
    }
}
