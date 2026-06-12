package com.psikochat.app.ui.home

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.*
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
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavController
import coil.compose.AsyncImage
import com.psikochat.app.data.api.RetrofitClient
import com.psikochat.app.data.local.TokenManager
import com.psikochat.app.data.model.Resource
import com.psikochat.app.data.repository.ProfileRepository
import com.psikochat.app.ui.theme.*
import com.psikochat.app.ui.components.*
import kotlinx.coroutines.launch
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.MultipartBody
import okhttp3.RequestBody.Companion.asRequestBody
import java.io.File
import java.io.FileOutputStream

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ProfileScreen(navController: NavController, tokenManager: TokenManager) {
    val api = RetrofitClient.create(tokenManager)
    val repository = ProfileRepository(api)
    val factory = object : ViewModelProvider.Factory {
        override fun <T : ViewModel> create(modelClass: Class<T>): T {
            return ProfileViewModel(repository, tokenManager) as T
        }
    }
    val viewModel: ProfileViewModel = viewModel(factory = factory)
    
    val subscriptionRepo = com.psikochat.app.data.repository.SubscriptionRepository(api)
    val subscriptionFactory = object : ViewModelProvider.Factory {
        override fun <T : ViewModel> create(modelClass: Class<T>): T {
            return SubscriptionViewModel(subscriptionRepo) as T
        }
    }
    val subscriptionViewModel: SubscriptionViewModel = viewModel(factory = subscriptionFactory)
    val isPremiumUser by subscriptionViewModel.isPremium.collectAsState()
    
    val profileState by viewModel.profileState.collectAsState()
    val updateState by viewModel.updateState.collectAsState()
    val username by tokenManager.getUsername().collectAsState(initial = "Kullanıcı")
    val fullNamePref by tokenManager.getFullName().collectAsState(initial = null)
    val emailPref by tokenManager.getEmail().collectAsState(initial = null)
    val scope = rememberCoroutineScope()
    val snackbarHostState = remember { SnackbarHostState() }
    val context = LocalContext.current

    var showEditDialog by remember { mutableStateOf(false) }

    val photoPickerLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.GetContent()
    ) { uri ->
        uri?.let {
            val part = createMultipartFromUri(context, it)
            if (part != null) {
                viewModel.uploadPhoto(part)
            } else {
                scope.launch { snackbarHostState.showSnackbar("Dosya hazırlanamadı") }
            }
        }
    }

    LaunchedEffect(updateState) {
        if (updateState is Resource.Error) {
            snackbarHostState.showSnackbar(updateState?.message ?: "İşlem başarısız")
            viewModel.clearUpdateState()
        } else if (updateState is Resource.Success) {
            snackbarHostState.showSnackbar("İşlem başarılı")
            viewModel.clearUpdateState()
            showEditDialog = false
        }
    }

    Scaffold(
        snackbarHost = { SnackbarHost(snackbarHostState) },
        topBar = {
            CenterAlignedTopAppBar(
                title = {
                    Text(
                        "Profilim",
                        style = MaterialTheme.typography.titleMedium,
                        color = LoginTextColor
                    )
                },
                navigationIcon = {
                    IconButton(onClick = { navController.popBackStack() }) {
                        Icon(Icons.AutoMirrored.Filled.KeyboardArrowLeft, contentDescription = "Geri", tint = LoginTextColor)
                    }
                },
                actions = {
                    IconButton(onClick = { 
                        scope.launch {
                            tokenManager.clearAuthData()
                            ProfileViewModel.clearCache()
                            SubscriptionViewModel.clearCache()
                            navController.navigate("auth_graph") {
                                popUpTo("main_graph") { inclusive = true }
                                launchSingleTop = true
                            }
                        }
                    }) {
                        Icon(Icons.AutoMirrored.Filled.ExitToApp, contentDescription = "Çıkış Yap", tint = Color.Red)
                    }
                },
                colors = TopAppBarDefaults.centerAlignedTopAppBarColors(containerColor = Color.Transparent)
            )
        },
        bottomBar = {
            PremiumBottomNavigation(navController = navController, currentScreen = "profile")
        },
        containerColor = LoginBackground
    ) { padding ->
        Box(modifier = Modifier.fillMaxSize().padding(padding)) {
            val profile = profileState.data
            val isOffline = profileState is Resource.Error && profile != null

            if (profileState is Resource.Loading && profile == null) {
                CircularProgressIndicator(modifier = Modifier.align(Alignment.Center), color = LoginButton)
            } else if (profileState is Resource.Error && profile == null) {
                Column(
                    modifier = Modifier.align(Alignment.Center).padding(24.dp),
                    horizontalAlignment = Alignment.CenterHorizontally
                ) {
                    Icon(Icons.Default.Warning, contentDescription = null, tint = Color.Red, modifier = Modifier.size(48.dp))
                    Spacer(modifier = Modifier.height(16.dp))
                    Text(profileState.message ?: "Bir hata oluştu", textAlign = TextAlign.Center, color = LoginTextColor)
                    Spacer(modifier = Modifier.height(16.dp))
                    Button(onClick = { viewModel.loadProfile() }, colors = ButtonDefaults.buttonColors(containerColor = LoginButton)) {
                        Text("Tekrar Dene")
                    }
                }
            } else if (profile != null) {
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
                    !profile.fullName.isNullOrBlank() -> profile.fullName!!
                    !fullNamePref.isNullOrBlank() -> fullNamePref!!
                    !profile.username.isNullOrBlank() -> profile.username
                    !username.isNullOrBlank() && username != "Kullanıcı" -> username
                    !getEmailPrefix(profile.email).isNullOrBlank() -> getEmailPrefix(profile.email)!!
                    !getEmailPrefix(emailPref).isNullOrBlank() -> getEmailPrefix(emailPref)!!
                    else -> "Kullanıcı"
                }

                Column(
                    modifier = Modifier
                        .fillMaxSize()
                        .padding(horizontal = 24.dp)
                        .verticalScroll(rememberScrollState()),
                    horizontalAlignment = Alignment.CenterHorizontally
                ) {
                    if (isOffline) {
                        Surface(
                            color = MildAlertBg,
                            border = androidx.compose.foundation.BorderStroke(1.dp, MildAlertText.copy(alpha = 0.3f)),
                            shape = RoundedCornerShape(12.dp),
                            modifier = Modifier.fillMaxWidth().padding(top = 16.dp),
                            shadowElevation = 1.dp
                        ) {
                            Row(
                                modifier = Modifier.padding(12.dp),
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Text(
                                    text = "Profil bilgileri çevrimdışı görüntüleniyor.",
                                    fontSize = 12.sp,
                                    fontWeight = FontWeight.SemiBold,
                                    color = MildAlertText,
                                    modifier = Modifier.weight(1f)
                                )
                                Spacer(modifier = Modifier.width(8.dp))
                                Text(
                                    text = "Yenile",
                                    fontSize = 12.sp,
                                    fontWeight = FontWeight.Bold,
                                    color = DarkTealPrimary,
                                    modifier = Modifier.clickable { viewModel.loadProfile() }
                                )
                            }
                        }
                    } else {
                        Spacer(modifier = Modifier.height(24.dp))
                    }
                        
                        // Profile Header
                        Box(
                            modifier = Modifier
                                .size(100.dp)
                                .clip(CircleShape)
                                .background(Color.White)
                                .clickable { photoPickerLauncher.launch("image/*") }
                                .padding(4.dp)
                        ) {
                            if (profile.profilePhotoUrl != null) {
                                AsyncImage(
                                    model = RetrofitClient.resolveProfilePhotoUrl(profile.profilePhotoUrl),
                                    contentDescription = "Profil Fotoğrafı",
                                    modifier = Modifier
                                        .fillMaxSize()
                                        .clip(CircleShape)
                                )
                            } else {
                                Box(
                                    modifier = Modifier
                                        .fillMaxSize()
                                        .clip(CircleShape)
                                        .background(Color.LightGray),
                                    contentAlignment = Alignment.Center
                                ) {
                                    Icon(
                                        Icons.Default.Person,
                                        contentDescription = null,
                                        modifier = Modifier.size(60.dp),
                                        tint = Color.White
                                    )
                                }
                            }
                            
                            // Upload Overlay
                            if (updateState is Resource.Loading) {
                                Box(
                                    modifier = Modifier
                                        .fillMaxSize()
                                        .clip(CircleShape)
                                        .background(Color.Black.copy(alpha = 0.3f)),
                                    contentAlignment = Alignment.Center
                                ) {
                                    CircularProgressIndicator(color = Color.White, modifier = Modifier.size(24.dp))
                                }
                            }
                        }
                        
                        Spacer(modifier = Modifier.height(16.dp))
                        
                        Text(
                            text = displayUsername,
                            style = MaterialTheme.typography.headlineSmall.copy(fontWeight = FontWeight.Bold),
                            color = LoginTextColor
                        )
                        
                        Spacer(modifier = Modifier.height(4.dp))

                        // Retrieve active streak dynamically from cached Room SQLite timestamps
                        val db = com.psikochat.app.data.local.AppDatabase.getInstance(LocalContext.current)
                        val messagesFlow = remember(profile.username) { db.chatDao().getCachedMessages(profile.username) }
                        val messages by messagesFlow.collectAsState(initial = emptyList())
                        val moodsFlow = remember(profile.username) { db.moodJournalDao().getCachedMoodJournals(profile.username) }
                        val moods by moodsFlow.collectAsState(initial = emptyList())

                        val streakText = remember(messages, moods) {
                            StreakEngine.computeStreakSummary(messages, moods).label
                        }

                        // Row container holding Premium Badge and Streak Badge
                        Row(
                            horizontalArrangement = Arrangement.spacedBy(8.dp),
                            verticalAlignment = Alignment.CenterVertically,
                            modifier = Modifier.padding(vertical = 4.dp)
                        ) {
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

                        Spacer(modifier = Modifier.height(8.dp))

                        Text(
                            text = profile.bio ?: "Henüz bir biyografi eklenmemiş.",
                            style = MaterialTheme.typography.bodyMedium,
                            color = LoginSecondaryText,
                            textAlign = TextAlign.Center,
                            modifier = Modifier.padding(horizontal = 16.dp)
                        )
                        
                        Spacer(modifier = Modifier.height(16.dp))
                        
                        PremiumButton(
                            onClick = { showEditDialog = true },
                            cornerRadius = 16.dp,
                            height = 40.dp
                        ) {
                            Icon(Icons.Default.Edit, contentDescription = null, modifier = Modifier.size(18.dp))
                            Spacer(modifier = Modifier.width(8.dp))
                            Text("Profili Düzenle")
                        }
                        
                        Spacer(modifier = Modifier.height(32.dp))

                        // Profile Options Section
                        PremiumCard(
                            modifier = Modifier.fillMaxWidth()
                        ) {
                            ProfileOptionItem(Icons.Default.Settings, "Uygulama Ayarları") {
                                navController.navigate("settings")
                            }
                            Divider(color = Color.LightGray.copy(alpha = 0.3f), modifier = Modifier.padding(vertical = 8.dp))
                            ProfileOptionItem(Icons.Default.DateRange, "Wellness Planım") {
                                navController.navigate("wellness_schedule")
                            }
                            Divider(color = Color.LightGray.copy(alpha = 0.3f), modifier = Modifier.padding(vertical = 8.dp))
                            ProfileOptionItem(Icons.Default.Edit, "Duygu Günlüğüm") {
                                navController.navigate("mood_journal")
                            }
                            Divider(color = Color.LightGray.copy(alpha = 0.3f), modifier = Modifier.padding(vertical = 8.dp))
                            ProfileOptionItem(Icons.Default.Star, "Başarılarım") {
                                navController.navigate("achievements")
                            }
                            Divider(color = Color.LightGray.copy(alpha = 0.3f), modifier = Modifier.padding(vertical = 8.dp))
                            ProfileOptionItem(Icons.Default.Notifications, "Bildirimler") {
                                navController.navigate("settings")
                            }
                        }

                        
                        Spacer(modifier = Modifier.height(24.dp))
                        
                        // Response Style Badge
                        Surface(
                            modifier = Modifier.fillMaxWidth(),
                            shape = RoundedCornerShape(24.dp),
                            color = LoginButton.copy(alpha = 0.1f)
                        ) {
                            Row(
                                modifier = Modifier.padding(16.dp),
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Icon(Icons.Default.Star, contentDescription = null, tint = LoginButton)
                                Spacer(modifier = Modifier.width(12.dp))
                                Column {
                                    Text("Cevap Stili", fontSize = 10.sp, color = LoginSecondaryText)
                                    val styleText = when(profile.responseStyle) {
                                        "direct" -> "Doğrudan"
                                        "empathetic" -> "Empatik"
                                        else -> "Destekleyici"
                                    }
                                    Text(styleText, fontWeight = FontWeight.Bold, color = LoginTextColor)
                                }
                            }
                        }
                        Spacer(modifier = Modifier.height(24.dp))
                    }
                }
            }
        }

    if (showEditDialog && profileState is Resource.Success) {
        val profile = (profileState as Resource.Success).data!!
        
        var editName by remember { mutableStateOf(profile.displayName ?: "") }
        var editBio by remember { mutableStateOf(profile.bio ?: "") }
        var editLang by remember { mutableStateOf(profile.preferredLanguage) }
        var editStyle by remember { mutableStateOf(profile.responseStyle) }

        var nameError by remember { mutableStateOf<String?>(null) }
        var bioError by remember { mutableStateOf<String?>(null) }

        val isFormValid = nameError == null && bioError == null && editName.isNotBlank()

        AlertDialog(
            onDismissRequest = { showEditDialog = false },
            title = { Text("Profili Düzenle", fontWeight = FontWeight.Bold) },
            text = {
                Column(modifier = Modifier.verticalScroll(rememberScrollState())) {
                    // Display Name Field
                    OutlinedTextField(
                        value = editName,
                        onValueChange = { 
                            editName = it
                            nameError = when {
                                it.isBlank() -> "Görünen ad boş olamaz."
                                it.length > 50 -> "Maksimum 50 karakter."
                                else -> null
                            }
                        },
                        label = { Text("Görünen Ad") },
                        modifier = Modifier.fillMaxWidth(),
                        isError = nameError != null,
                        supportingText = { nameError?.let { Text(it) } ?: Text("${editName.length}/50") },
                        singleLine = true
                    )
                    
                    Spacer(modifier = Modifier.height(12.dp))

                    // Bio Field
                    OutlinedTextField(
                        value = editBio,
                        onValueChange = { 
                            editBio = it
                            bioError = if (it.length > 250) "Maksimum 250 karakter." else null
                        },
                        label = { Text("Biyografi") },
                        modifier = Modifier.fillMaxWidth(),
                        isError = bioError != null,
                        supportingText = { bioError?.let { Text(it) } ?: Text("${editBio.length}/250") },
                        minLines = 3
                    )

                    Spacer(modifier = Modifier.height(12.dp))

                    // Language Selection
                    Text("Tercih Edilen Dil", style = MaterialTheme.typography.labelMedium, color = LoginSecondaryText)
                    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        listOf("tr" to "Türkçe", "en" to "English").forEach { (code, label) ->
                            FilterChip(
                                selected = editLang == code,
                                onClick = { editLang = code },
                                label = { Text(label) },
                                modifier = Modifier.weight(1f)
                            )
                        }
                    }

                    Spacer(modifier = Modifier.height(12.dp))

                    // Response Style Selection
                    Text("Cevap Stili", style = MaterialTheme.typography.labelMedium, color = LoginSecondaryText)
                    Spacer(modifier = Modifier.height(4.dp))
                    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        listOf(
                            Triple("supportive", "Destekleyici", "Daha motive edici ve güven veren yanıtlar."),
                            Triple("empathetic", "Empatik", "Duygularını daha çok yansıtan ve anlayan yanıtlar."),
                            Triple("direct", "Net/Doğrudan", "Daha kısa, net ve çözüm odaklı yanıtlar.")
                        ).forEach { (code, label, desc) ->
                            Row(
                                verticalAlignment = Alignment.Top,
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .clickable { editStyle = code }
                                    .padding(vertical = 4.dp)
                            ) {
                                RadioButton(
                                    selected = editStyle == code,
                                    onClick = { editStyle = code },
                                    modifier = Modifier.padding(top = 2.dp)
                                )
                                Spacer(modifier = Modifier.width(8.dp))
                                Column {
                                    Text(label, style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.Bold, color = LoginTextColor)
                                    Text(desc, style = MaterialTheme.typography.labelSmall, color = LoginSecondaryText, lineHeight = 14.sp)
                                }
                            }
                        }
                    }
                }
            },
            confirmButton = {
                Button(
                    onClick = { 
                        if (isFormValid) {
                            viewModel.updateProfile(editName.trim(), editBio.trim(), editLang, editStyle)
                        }
                    },
                    enabled = isFormValid && updateState !is Resource.Loading,
                    colors = ButtonDefaults.buttonColors(containerColor = LoginButton)
                ) {
                    if (updateState is Resource.Loading) {
                        CircularProgressIndicator(modifier = Modifier.size(20.dp), color = Color.White)
                    } else {
                        Text("Kaydet")
                    }
                }
            },
            dismissButton = {
                TextButton(onClick = { showEditDialog = false }, enabled = updateState !is Resource.Loading) {
                    Text("İptal")
                }
            }
        )
    }
}

@Composable
fun ProfileOptionItem(icon: ImageVector, title: String, onClick: () -> Unit = {}) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clickable { onClick() }
            .padding(vertical = 8.dp, horizontal = 4.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {

        Box(
            modifier = Modifier
                .size(40.dp)
                .clip(CircleShape)
                .background(LoginBackground.copy(alpha = 0.5f)),
            contentAlignment = Alignment.Center
        ) {
            Icon(icon, contentDescription = null, tint = LoginButton, modifier = Modifier.size(20.dp))
        }
        Spacer(modifier = Modifier.width(16.dp))
        Text(text = title, fontWeight = FontWeight.Medium, color = LoginTextColor, modifier = Modifier.weight(1f))
        Icon(Icons.AutoMirrored.Filled.KeyboardArrowRight, contentDescription = null, tint = Color.Gray)
    }
}

@Composable
private fun Icon(imageVector: ImageVector, contentDescription: String?, size: androidx.compose.ui.unit.Dp) {
    Icon(imageVector, contentDescription, modifier = Modifier.size(size))
}

private fun createMultipartFromUri(context: android.content.Context, uri: android.net.Uri): MultipartBody.Part? {
    val tempFile = File(context.cacheDir, "temp_profile_photo.jpg")
    var compressionSuccess = false

    try {
        val inputStream = context.contentResolver.openInputStream(uri)
        if (inputStream != null) {
            val originalBitmap = android.graphics.BitmapFactory.decodeStream(inputStream)
            inputStream.close()
            if (originalBitmap != null) {
                val width = originalBitmap.width
                val height = originalBitmap.height
                val maxDimension = 1024
                
                val scaledBitmap = if (width > maxDimension || height > maxDimension) {
                    val ratio = width.toFloat() / height.toFloat()
                    val newWidth: Int
                    val newHeight: Int
                    if (width > height) {
                        newWidth = maxDimension
                        newHeight = (maxDimension / ratio).toInt()
                    } else {
                        newHeight = maxDimension
                        newWidth = (maxDimension * ratio).toInt()
                    }
                    android.graphics.Bitmap.createScaledBitmap(originalBitmap, newWidth, newHeight, true)
                } else {
                    originalBitmap
                }
                
                val outputStream = FileOutputStream(tempFile)
                scaledBitmap.compress(android.graphics.Bitmap.CompressFormat.JPEG, 85, outputStream)
                outputStream.flush()
                outputStream.close()
                
                if (scaledBitmap != originalBitmap) {
                    scaledBitmap.recycle()
                }
                originalBitmap.recycle()
                compressionSuccess = true
            }
        }
    } catch (e: Exception) {
        // Fallback safely to copy
    }

    if (!compressionSuccess) {
        try {
            val inputStream = context.contentResolver.openInputStream(uri) ?: return null
            val outputStream = FileOutputStream(tempFile)
            inputStream.use { input ->
                outputStream.use { output ->
                    input.copyTo(output)
                }
            }
        } catch (e: Exception) {
            return null
        }
    }

    return try {
        val requestFile = tempFile.asRequestBody("image/jpeg".toMediaTypeOrNull())
        MultipartBody.Part.createFormData("file", tempFile.name, requestFile)
    } catch (e: Exception) {
        null
    }
}
