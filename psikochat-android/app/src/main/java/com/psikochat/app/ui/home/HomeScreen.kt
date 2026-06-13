package com.psikochat.app.ui.home

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material.icons.automirrored.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavController
import coil.compose.AsyncImage
import com.psikochat.app.data.api.RetrofitClient
import com.psikochat.app.data.local.TokenManager
import com.psikochat.app.data.model.Resource
import com.psikochat.app.ui.theme.*
import com.psikochat.app.ui.components.*
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun HomeScreen(navController: NavController, tokenManager: TokenManager) {
    val username by tokenManager.getUsername().collectAsState(initial = "Kullanıcı")
    val fullName by tokenManager.getFullName().collectAsState(initial = null)
    val email by tokenManager.getEmail().collectAsState(initial = null)
    val scope = rememberCoroutineScope()
    val scrollState = rememberScrollState()

    // Dialog state controllers
    var showNotificationDialog by remember { mutableStateOf(false) }

    // Live backend services initialization
    val context = androidx.compose.ui.platform.LocalContext.current
    val db = com.psikochat.app.data.local.AppDatabase.getInstance(context)
    val syncManager = com.psikochat.app.data.sync.SyncManager.getInstance(context)
    val api = RetrofitClient.create(tokenManager)

    // Dynamic database observations for streaks and achievements
    val messagesFlow = remember(username) { db.chatDao().getAllCachedMessages(username) }
    val messages by messagesFlow.collectAsState(initial = emptyList())
    val moodsFlow = remember(username) { db.moodJournalDao().getCachedMoodJournals(username) }
    val moods by moodsFlow.collectAsState(initial = emptyList())

    // 1. Profile ViewModel Integration
    val profileRepo = com.psikochat.app.data.repository.ProfileRepository(api)
    val profileFactory = object : ViewModelProvider.Factory {
        @Suppress("UNCHECKED_CAST")
        override fun <T : ViewModel> create(modelClass: Class<T>): T {
            return ProfileViewModel(profileRepo, tokenManager) as T
        }
    }
    val mainGraphEntry = remember(navController) { navController.getBackStackEntry("main_graph") }
    val profileViewModel: ProfileViewModel = viewModel(viewModelStoreOwner = mainGraphEntry, factory = profileFactory)
    val profileState by profileViewModel.profileState.collectAsState()

    // 1b. Subscription ViewModel Integration
    val subscriptionRepo = com.psikochat.app.data.repository.SubscriptionRepository(api)
    val subscriptionFactory = object : ViewModelProvider.Factory {
        @Suppress("UNCHECKED_CAST")
        override fun <T : ViewModel> create(modelClass: Class<T>): T {
            return SubscriptionViewModel(subscriptionRepo) as T
        }
    }
    val subscriptionViewModel: SubscriptionViewModel = viewModel(factory = subscriptionFactory)
    val isPremiumUser by subscriptionViewModel.isPremium.collectAsState()

    // 2. Dashboard ViewModel Integration
    val dashboardRepo = com.psikochat.app.data.repository.WellnessDashboardRepository(api, db.dashboardDao())
    val progressRepo = com.psikochat.app.data.repository.ProgressRepository(db.scoreSnapshotDao())
    val dashboardFactory = object : ViewModelProvider.Factory {
        @Suppress("UNCHECKED_CAST")
        override fun <T : ViewModel> create(modelClass: Class<T>): T {
            return WellnessDashboardViewModel(dashboardRepo, tokenManager, syncManager, progressRepo) as T
        }
    }
    val dashboardViewModel: WellnessDashboardViewModel = viewModel(factory = dashboardFactory)
    val dashboardState by dashboardViewModel.dashboardState.collectAsState()

    // 3. Appointment ViewModel Integration
    val appointmentRepo = com.psikochat.app.data.repository.AppointmentRepository(api, db.appointmentDao())
    val appointmentFactory = object : ViewModelProvider.Factory {
        @Suppress("UNCHECKED_CAST")
        override fun <T : ViewModel> create(modelClass: Class<T>): T {
            return AppointmentViewModel(appointmentRepo) as T
        }
    }
    val appointmentViewModel: AppointmentViewModel = viewModel(factory = appointmentFactory)
    val nextAppointment by appointmentViewModel.nextAppointment.collectAsState()

    // Helper to get email prefix
    val getEmailPrefix = { emailStr: String? ->
        if (!emailStr.isNullOrBlank() && emailStr.contains("@")) {
            emailStr.substringBefore("@")
        } else {
            null
        }
    }

    // Dynamic Display Name Evaluation: full_name > username > email prefix > Kullanıcı
    val displayUsername = when {
        !profileState.data?.fullName.isNullOrBlank() -> profileState.data!!.fullName!!
        !fullName.isNullOrBlank() -> fullName!!
        !profileState.data?.username.isNullOrBlank() -> profileState.data!!.username
        !username.isNullOrBlank() && username != "Kullanıcı" -> username
        !getEmailPrefix(profileState.data?.email).isNullOrBlank() -> getEmailPrefix(profileState.data?.email)!!
        !getEmailPrefix(email).isNullOrBlank() -> getEmailPrefix(email)!!
        else -> "Kullanıcı"
    }

    // Dynamic Total Interactions evaluation
    val totalInteractionsText = when (val state = dashboardState) {
        is Resource.Success -> {
            "${state.data?.overview?.totalMessages ?: 0} Etkileşim"
        }
        else -> "0"
    }

    Scaffold(
        topBar = {
            CenterAlignedTopAppBar(
                title = {
                    Text(
                        "PsikoChat Paneli",
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Bold,
                        color = LoginTextColor
                    )
                },
                actions = {
                    IconButton(onClick = { /* Menu Action placeholder */ }) {
                        Icon(Icons.Default.Menu, contentDescription = "Menü", tint = LoginTextColor)
                    }
                },
                colors = TopAppBarDefaults.centerAlignedTopAppBarColors(
                    containerColor = Color.Transparent
                )
            )
        },
        bottomBar = {
            PremiumBottomNavigation(navController = navController, currentScreen = "home")
        },
        containerColor = LoginBackground
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .verticalScroll(scrollState)
                .padding(horizontal = 24.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Top
        ) {
            Spacer(modifier = Modifier.height(16.dp))

            // Profile Hero Section
            Box(
                contentAlignment = Alignment.BottomEnd,
                modifier = Modifier.size(108.dp)
            ) {
                // Circular profile avatar with live backend image fallback
                Surface(
                    shape = CircleShape,
                    color = Color.White,
                    shadowElevation = 4.dp,
                    border = BorderStroke(3.dp, Color.White),
                    modifier = Modifier.size(100.dp)
                ) {
                    val profilePhotoUrl = profileState.data?.profilePhotoUrl
                    if (!profilePhotoUrl.isNullOrBlank()) {
                        AsyncImage(
                            model = RetrofitClient.resolveProfilePhotoUrl(profilePhotoUrl),
                            contentDescription = "Profil Fotoğrafı",
                            modifier = Modifier
                                .fillMaxSize()
                                .clip(CircleShape)
                        )
                    } else {
                        Box(
                            modifier = Modifier
                                .fillMaxSize()
                                .background(SoftMintAccent),
                            contentAlignment = Alignment.Center
                        ) {
                            Icon(
                                imageVector = Icons.Default.Person,
                                contentDescription = "Profil Resmi",
                                modifier = Modifier.size(54.dp),
                                tint = DarkTealPrimary
                            )
                        }
                    }
                }

                // Small floating edit button that navigates directly to edit dialog in ProfileScreen
                Surface(
                    shape = CircleShape,
                    color = DarkTealPrimary,
                    shadowElevation = 2.dp,
                    modifier = Modifier
                        .size(32.dp)
                        .clickable { navController.navigate("profile") }
                ) {
                    Box(
                        contentAlignment = Alignment.Center,
                        modifier = Modifier.fillMaxSize()
                    ) {
                        Icon(
                            imageVector = Icons.Default.Edit,
                            contentDescription = "Düzenle",
                            tint = Color.White,
                            modifier = Modifier.size(14.dp)
                        )
                    }
                }
            }

            Spacer(modifier = Modifier.height(16.dp))

            // Live User Name Display
            Text(
                text = displayUsername,
                style = MaterialTheme.typography.titleLarge.copy(
                    fontWeight = FontWeight.Bold,
                    fontSize = 22.sp
                ),
                color = LoginTextColor,
                textAlign = TextAlign.Center
            )

            Spacer(modifier = Modifier.height(8.dp))

            // Row container holding Premium Badge and Streak Badge
            Row(
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                // Premium Member Badge
                if (isPremiumUser) {
                    Surface(
                        shape = RoundedCornerShape(12.dp),
                        color = SoftMintAccent.copy(alpha = 0.3f),
                        border = BorderStroke(1.dp, SoftMintAccent)
                    ) {
                        Row(
                            verticalAlignment = Alignment.CenterVertically,
                            modifier = Modifier.padding(horizontal = 12.dp, vertical = 6.dp)
                        ) {
                            Icon(
                                imageVector = Icons.Default.Star,
                                contentDescription = null,
                                tint = DarkTealPrimary,
                                modifier = Modifier.size(14.dp)
                            )
                            Spacer(modifier = Modifier.width(6.dp))
                            Text(
                                text = "Premium Üye",
                                color = DarkTealPrimary,
                                fontWeight = FontWeight.Bold,
                                fontSize = 12.sp
                            )
                        }
                    }
                } else {
                    Surface(
                        shape = RoundedCornerShape(12.dp),
                        color = Color.LightGray.copy(alpha = 0.2f),
                        border = BorderStroke(1.dp, Color.LightGray.copy(alpha = 0.5f))
                    ) {
                        Row(
                            verticalAlignment = Alignment.CenterVertically,
                            modifier = Modifier.padding(horizontal = 12.dp, vertical = 6.dp)
                        ) {
                            Icon(
                                imageVector = Icons.Default.Lock,
                                contentDescription = null,
                                tint = Color.Gray,
                                modifier = Modifier.size(14.dp)
                            )
                            Spacer(modifier = Modifier.width(6.dp))
                            Text(
                                text = "Ücretsiz Plan",
                                color = Color.Gray,
                                fontWeight = FontWeight.Bold,
                                fontSize = 12.sp
                            )
                            Spacer(modifier = Modifier.width(8.dp))
                            Text(
                                text = "Yükselt",
                                color = DarkTealPrimary,
                                fontWeight = FontWeight.ExtraBold,
                                fontSize = 12.sp,
                                modifier = Modifier.clickable {
                                    navController.navigate("payment_methods")
                                }
                            )
                        }
                    }
                }

                val streakText = remember(messages, moods) {
                    StreakEngine.computeStreakSummary(messages, moods).label
                }

                Surface(
                    shape = RoundedCornerShape(12.dp),
                    color = if (streakText.startsWith("🔥")) SoftMintAccent.copy(alpha = 0.5f) else SoftMintLight,
                    border = BorderStroke(1.dp, if (streakText.startsWith("🔥")) DarkTealPrimary.copy(alpha = 0.3f) else SoftMintAccent)
                ) {
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        modifier = Modifier.padding(horizontal = 12.dp, vertical = 6.dp)
                    ) {
                        Text(
                            text = streakText,
                            color = if (streakText.startsWith("🔥")) DarkTealPrimary else SecondaryTealText,
                            fontWeight = FontWeight.Bold,
                            fontSize = 12.sp
                        )
                    }
                }
            }

            Spacer(modifier = Modifier.height(28.dp))

            // Stats Section with Live Backend Data
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(16.dp)
            ) {
                // Card 1: Sıradaki Randevu (Dynamic Live Database observation)
                Surface(
                    modifier = Modifier.weight(1f),
                    shape = RoundedCornerShape(24.dp),
                    color = PremiumWhiteCard,
                    shadowElevation = 2.dp,
                    border = BorderStroke(1.dp, SoftMintAccent.copy(alpha = 0.5f))
                ) {
                    Column(
                        modifier = Modifier.padding(16.dp),
                        horizontalAlignment = Alignment.Start
                    ) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Icon(
                                imageVector = Icons.Default.DateRange,
                                contentDescription = null,
                                tint = DarkTealPrimary,
                                modifier = Modifier.size(16.dp)
                            )
                            Spacer(modifier = Modifier.width(6.dp))
                            Text(
                                text = "Sıradaki Randevu",
                                fontSize = 11.sp,
                                fontWeight = FontWeight.Bold,
                                color = LoginSecondaryText
                            )
                        }
                        Spacer(modifier = Modifier.height(12.dp))
                        
                        val appt = nextAppointment
                        if (appt != null) {
                            Text(
                                text = appt.psychologistName,
                                fontSize = 14.sp,
                                fontWeight = FontWeight.Bold,
                                color = LoginTextColor,
                                maxLines = 1
                            )
                            Text(
                                text = appt.psychologistSpecialty,
                                fontSize = 11.sp,
                                color = LoginSecondaryText,
                                maxLines = 1
                            )
                            Spacer(modifier = Modifier.height(8.dp))
                            Surface(
                                shape = RoundedCornerShape(8.dp),
                                color = SoftMintAccent.copy(alpha = 0.4f)
                            ) {
                                Text(
                                    text = "${appt.appointmentDate} ${appt.appointmentTime}",
                                    fontSize = 11.sp,
                                    fontWeight = FontWeight.Bold,
                                    color = DarkTealPrimary,
                                    modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp)
                                )
                            }
                        } else {
                            Text(
                                text = "Henüz randevun yok",
                                fontSize = 13.sp,
                                fontWeight = FontWeight.Bold,
                                color = LoginTextColor,
                                lineHeight = 16.sp
                            )
                            Spacer(modifier = Modifier.height(10.dp))
                            Text(
                                text = "Randevu Oluştur",
                                fontSize = 12.sp,
                                fontWeight = FontWeight.Bold,
                                color = DarkTealPrimary,
                                modifier = Modifier
                                    .clickable { navController.navigate("therapy") }
                                    .background(SoftMintAccent.copy(alpha = 0.3f), RoundedCornerShape(6.dp))
                                    .padding(horizontal = 8.dp, vertical = 4.dp)
                            )
                        }
                    }
                }

                // Card 2: Toplam Etkileşim (Live user wellness stats from backend)
                Surface(
                    modifier = Modifier.weight(1f),
                    shape = RoundedCornerShape(24.dp),
                    color = PremiumWhiteCard,
                    shadowElevation = 2.dp,
                    border = BorderStroke(1.dp, SoftMintAccent.copy(alpha = 0.5f))
                ) {
                    Column(
                        modifier = Modifier.padding(16.dp),
                        horizontalAlignment = Alignment.Start
                    ) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Icon(
                                imageVector = Icons.Default.Favorite,
                                contentDescription = null,
                                tint = DarkTealPrimary,
                                modifier = Modifier.size(16.dp)
                            )
                            Spacer(modifier = Modifier.width(6.dp))
                            Text(
                                text = "Toplam Etkileşim",
                                fontSize = 11.sp,
                                fontWeight = FontWeight.Bold,
                                color = LoginSecondaryText
                            )
                        }
                        Spacer(modifier = Modifier.height(12.dp))
                        Text(
                            text = totalInteractionsText,
                            fontSize = 18.sp,
                            fontWeight = FontWeight.Bold,
                            color = LoginTextColor
                        )
                        Spacer(modifier = Modifier.height(20.dp))
                    }
                }
            }

            Spacer(modifier = Modifier.height(28.dp))

            // Menu List Section with actual live route configurations
            Column(
                modifier = Modifier.fillMaxWidth(),
                verticalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                MenuRow(icon = Icons.Default.Person, title = "Kişisel Bilgiler") {
                    navController.navigate("profile")
                }
                MenuRow(icon = Icons.Default.DateRange, title = "Randevularım") {
                    navController.navigate("wellness_schedule")
                }
                MenuRow(icon = Icons.Default.Email, title = "Sohbet Geçmişim") {
                    navController.navigate("chat_history")
                }
                MenuRow(icon = Icons.Default.Info, title = "Gelişim ve Analizler") {
                    navController.navigate("wellness_dashboard")
                }
                MenuRow(icon = Icons.Default.DateRange, title = "Haftalık Özetim") {
                    navController.navigate("weekly_recap")
                }
                MenuRow(icon = Icons.Default.Favorite, title = "Öneriler") {
                    navController.navigate("recommendations")
                }
                MenuRow(icon = Icons.Default.Star, title = "Ödeme Yöntemleri") {
                    navController.navigate("payment_methods")
                }
                MenuRow(icon = Icons.Default.Notifications, title = "Bildirimler") {
                    showNotificationDialog = true
                }
                MenuRow(icon = Icons.Default.Lock, title = "Güvenlik") {
                    navController.navigate("privacy_data")
                }
            }

            Spacer(modifier = Modifier.height(24.dp))

            // Achievement Preview Section
            Surface(
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(20.dp),
                color = PremiumWhiteCard,
                shadowElevation = 1.dp,
                border = BorderStroke(1.dp, SoftMintAccent.copy(alpha = 0.5f))
            ) {
                Column(
                    modifier = Modifier.padding(16.dp),
                    horizontalAlignment = Alignment.Start
                ) {
                    // Header row with title + "Tümünü Gör"
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text(
                            text = "Başarılar",
                            style = MaterialTheme.typography.bodyMedium,
                            fontWeight = FontWeight.Bold,
                            color = LoginTextColor
                        )
                        Row(
                            verticalAlignment = Alignment.CenterVertically,
                            modifier = Modifier.clickable { navController.navigate("achievements") }
                        ) {
                            Text(
                                text = "Tümünü Gör",
                                fontSize = 12.sp,
                                fontWeight = FontWeight.Bold,
                                color = DarkTealPrimary
                            )
                            Icon(
                                imageVector = Icons.AutoMirrored.Filled.KeyboardArrowRight,
                                contentDescription = null,
                                tint = DarkTealPrimary,
                                modifier = Modifier.size(14.dp)
                            )
                        }
                    }
                    Text(
                        text = "Zihinsel sağlık hedeflerine ulaştıkça rozetlerin açılır.",
                        style = MaterialTheme.typography.labelSmall,
                        color = LoginSecondaryText,
                        modifier = Modifier.padding(bottom = 12.dp)
                    )

                    // Fetch actual data states asynchronously for local evaluation
                    val appointmentsFlow = remember { db.appointmentDao().getAllAppointments() }
                    val appointments by appointmentsFlow.collectAsState(initial = emptyList())

                    val isFirstChatUnlocked = messages.isNotEmpty()
                    val isFirstApptUnlocked = appointments.isNotEmpty()
                    val isMoodDetectiveUnlocked = moods.size >= 5

                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        // Achievement 1: İlk Sohbet
                        AchievementBadgeItem(
                            title = "İlk Sohbet",
                            desc = "İlk sohbetini tamamla",
                            isUnlocked = isFirstChatUnlocked,
                            modifier = Modifier.weight(1f)
                        )

                        // Achievement 2: İlk Randevu
                        AchievementBadgeItem(
                            title = "İlk Randevu",
                            desc = "Uzman randevusu al",
                            isUnlocked = isFirstApptUnlocked,
                            modifier = Modifier.weight(1f)
                        )

                        // Achievement 3: Ruh Hali Dedektifi
                        AchievementBadgeItem(
                            title = "Ruh Dedektifi",
                            desc = "En az 5 duygu kaydı gir",
                            isUnlocked = isMoodDetectiveUnlocked,
                            modifier = Modifier.weight(1f)
                        )
                    }

                    Spacer(modifier = Modifier.height(14.dp))

                    // "Tümünü Gör" → full Achievement Gallery
                    Surface(
                        modifier = Modifier
                            .fillMaxWidth()
                            .clickable { navController.navigate("achievements") },
                        shape = RoundedCornerShape(12.dp),
                        color = SoftMintAccent.copy(alpha = 0.25f),
                        border = BorderStroke(1.dp, SoftMintAccent.copy(alpha = 0.5f))
                    ) {
                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(horizontal = 14.dp, vertical = 10.dp),
                            horizontalArrangement = Arrangement.Center,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Text(
                                text = "Tümünü Gör",
                                fontSize = 13.sp,
                                fontWeight = FontWeight.Bold,
                                color = DarkTealPrimary
                            )
                            Spacer(modifier = Modifier.width(6.dp))
                            Icon(
                                imageVector = Icons.AutoMirrored.Filled.KeyboardArrowRight,
                                contentDescription = null,
                                tint = DarkTealPrimary,
                                modifier = Modifier.size(16.dp)
                            )
                        }
                    }
                }
            }

            Spacer(modifier = Modifier.height(24.dp))

            // Logout Section with real authentication reset
            OutlinedButton(
                onClick = {
                    scope.launch {
                        tokenManager.clearAuthData()
                        ProfileViewModel.clearCache()
                        SubscriptionViewModel.clearCache()
                        navController.navigate("auth_graph") {
                            popUpTo("main_graph") { inclusive = true }
                            launchSingleTop = true
                        }
                    }
                },
                modifier = Modifier
                    .fillMaxWidth()
                    .height(56.dp),
                shape = RoundedCornerShape(16.dp),
                border = BorderStroke(1.5.dp, Color(0xFFDC2626)),
                colors = ButtonDefaults.outlinedButtonColors(
                    contentColor = Color(0xFFDC2626)
                )
            ) {
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.Center
                ) {
                    Icon(
                        imageVector = Icons.AutoMirrored.Filled.ExitToApp,
                        contentDescription = null,
                        tint = Color(0xFFDC2626),
                        modifier = Modifier.size(20.dp)
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    Text(
                        text = "Oturumu Kapat",
                        fontWeight = FontWeight.Bold,
                        fontSize = 16.sp
                    )
                }
            }

            Spacer(modifier = Modifier.height(24.dp))
        }
    }



    // B. Premium Dialog: Bildirimler
    if (showNotificationDialog) {
        AlertDialog(
            onDismissRequest = { showNotificationDialog = false },
            title = { Text("Bildirim Yönetimi", fontWeight = FontWeight.Bold) },
            text = { Text("Bildirim özelleştirme özellikleri yakında eklenecektir. Bildirim izinlerinizi ve kanal tercihlerinizi Genel Ayarlar sayfamızdan yönetebilirsiniz.") },
            confirmButton = {
                Button(
                    onClick = {
                        showNotificationDialog = false
                        navController.navigate("settings")
                    },
                    colors = ButtonDefaults.buttonColors(containerColor = DarkTealPrimary)
                ) {
                    Text("Ayarlara Git", color = Color.White)
                }
            },
            dismissButton = {
                TextButton(onClick = { showNotificationDialog = false }) {
                    Text("Kapat")
                }
            }
        )
    }
}

@Composable
fun MenuRow(icon: ImageVector, title: String, onClick: () -> Unit) {
    Surface(
        modifier = Modifier
            .fillMaxWidth()
            .clickable { onClick() },
        shape = RoundedCornerShape(20.dp),
        color = PremiumWhiteCard,
        shadowElevation = 1.dp,
        border = BorderStroke(1.dp, SoftMintAccent.copy(alpha = 0.3f))
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(vertical = 12.dp, horizontal = 16.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            // Left circular mint icon container
            Box(
                modifier = Modifier
                    .size(40.dp)
                    .clip(CircleShape)
                    .background(SoftMintAccent.copy(alpha = 0.4f)),
                contentAlignment = Alignment.Center
            ) {
                Icon(
                    imageVector = icon,
                    contentDescription = null,
                    tint = DarkTealPrimary,
                    modifier = Modifier.size(20.dp)
                )
            }
            
            Spacer(modifier = Modifier.width(16.dp))
            
            // Text Title
            Text(
                text = title,
                fontSize = 15.sp,
                fontWeight = FontWeight.Medium,
                color = LoginTextColor,
                modifier = Modifier.weight(1f)
            )
            
            // Right chevron icon
            Icon(
                imageVector = Icons.AutoMirrored.Filled.KeyboardArrowRight,
                contentDescription = null,
                tint = SecondaryTealText,
                modifier = Modifier.size(20.dp)
            )
        }
    }
}

@Composable
fun AchievementBadgeItem(
    title: String,
    desc: String,
    isUnlocked: Boolean,
    modifier: Modifier = Modifier
) {
    Surface(
        shape = RoundedCornerShape(14.dp),
        color = if (isUnlocked) SoftMintLight else SoftMintLight.copy(alpha = 0.4f),
        border = BorderStroke(
            width = 1.dp,
            color = if (isUnlocked) DarkTealAccent else SoftMintAccent.copy(alpha = 0.3f)
        ),
        modifier = modifier
    ) {
        Column(
            modifier = Modifier.padding(10.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center
        ) {
            Box(
                modifier = Modifier
                    .size(36.dp)
                    .clip(CircleShape)
                    .background(if (isUnlocked) SoftMintAccent else SoftMintAccent.copy(alpha = 0.3f)),
                contentAlignment = Alignment.Center
            ) {
                Icon(
                    imageVector = if (isUnlocked) Icons.Default.Favorite else Icons.Default.Lock,
                    contentDescription = null,
                    tint = if (isUnlocked) DarkTealPrimary else SecondaryTealText,
                    modifier = Modifier.size(16.dp)
                )
            }
            Spacer(modifier = Modifier.height(8.dp))
            Text(
                text = title,
                style = MaterialTheme.typography.bodySmall,
                fontWeight = FontWeight.Bold,
                color = if (isUnlocked) LoginTextColor else LoginSecondaryText,
                textAlign = TextAlign.Center,
                fontSize = 11.sp
            )
            Spacer(modifier = Modifier.height(2.dp))
            Text(
                text = desc,
                style = MaterialTheme.typography.labelSmall,
                color = LoginSecondaryText,
                textAlign = TextAlign.Center,
                fontSize = 9.sp,
                lineHeight = 11.sp
            )
        }
    }
}
