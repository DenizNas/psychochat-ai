package com.psikochat.app.ui.home

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
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
            return ProfileViewModel(repository) as T
        }
    }
    val viewModel: ProfileViewModel = viewModel(factory = factory)
    
    val profileState by viewModel.profileState.collectAsState()
    val updateState by viewModel.updateState.collectAsState()
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
                        Icon(Icons.Default.KeyboardArrowLeft, contentDescription = "Geri", tint = LoginTextColor)
                    }
                },
                actions = {
                    IconButton(onClick = { 
                        scope.launch {
                            tokenManager.clearAuthData()
                            navController.navigate("auth_graph") {
                                popUpTo("main_graph") { inclusive = true }
                                launchSingleTop = true
                            }
                        }
                    }) {
                        Icon(Icons.Default.ExitToApp, contentDescription = "Çıkış Yap", tint = Color.Red)
                    }
                },
                colors = TopAppBarDefaults.centerAlignedTopAppBarColors(containerColor = Color.Transparent)
            )
        },
        bottomBar = {
            NavigationBar(
                containerColor = Color.White,
                tonalElevation = 8.dp,
                modifier = Modifier.height(80.dp)
            ) {
                NavigationBarItem(
                    icon = { Icon(Icons.Default.Home, contentDescription = null) },
                    label = { Text("Ana Sayfa", fontSize = 10.sp) },
                    selected = false,
                    onClick = { navController.navigate("home") { popUpTo("home") { inclusive = true } } }
                )
                NavigationBarItem(
                    icon = { Icon(Icons.Default.Share, contentDescription = null) },
                    label = { Text("Terapi", fontSize = 10.sp) },
                    selected = false,
                    onClick = { }
                )
                
                Box(
                    modifier = Modifier
                        .weight(1f)
                        .fillMaxHeight()
                        .clickable { navController.navigate("chat") },
                    contentAlignment = Alignment.Center
                ) {
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        Surface(
                            shape = CircleShape,
                            color = LoginButton,
                            modifier = Modifier.size(44.dp),
                            shadowElevation = 2.dp
                        ) {
                            Icon(Icons.Default.Face, contentDescription = "PsikoChat", tint = Color.White, modifier = Modifier.padding(10.dp))
                        }
                        Text("PsikoChat", fontSize = 10.sp, fontWeight = FontWeight.Bold, color = LoginButton)
                    }
                }

                NavigationBarItem(
                    icon = { Icon(Icons.Default.Person, contentDescription = null) },
                    label = { Text("Profilim", fontSize = 10.sp) },
                    selected = true,
                    onClick = { }
                )
                NavigationBarItem(
                    icon = { Icon(Icons.Default.Settings, contentDescription = null) },
                    label = { Text("Ayarlar", fontSize = 10.sp) },
                    selected = false,
                    onClick = { navController.navigate("settings") }
                )
            }
        },
        containerColor = LoginBackground
    ) { padding ->
        Box(modifier = Modifier.fillMaxSize().padding(padding)) {
            when (profileState) {
                is Resource.Loading -> {
                    CircularProgressIndicator(modifier = Modifier.align(Alignment.Center), color = LoginButton)
                }
                is Resource.Error -> {
                    Column(
                        modifier = Modifier.align(Alignment.Center).padding(24.dp),
                        horizontalAlignment = Alignment.CenterHorizontally
                    ) {
                        Icon(Icons.Default.Warning, contentDescription = null, tint = Color.Red, modifier = Modifier.size(48.dp))
                        Spacer(modifier = Modifier.height(16.dp))
                        Text(profileState.message ?: "Bir hata oluştu", textAlign = TextAlign.Center, color = LoginTextColor)
                        Button(onClick = { viewModel.loadProfile() }, colors = ButtonDefaults.buttonColors(containerColor = LoginButton)) {
                            Text("Tekrar Dene")
                        }
                    }
                }
                is Resource.Success -> {
                    val profile = profileState.data!!
                    Column(
                        modifier = Modifier
                            .fillMaxSize()
                            .padding(horizontal = 24.dp)
                            .verticalScroll(rememberScrollState()),
                        horizontalAlignment = Alignment.CenterHorizontally
                    ) {
                        Spacer(modifier = Modifier.height(24.dp))
                        
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
                                    model = "${RetrofitClient.BASE_URL}${profile.profilePhotoUrl}",
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
                            text = profile.displayName ?: profile.username,
                            style = MaterialTheme.typography.headlineSmall.copy(fontWeight = FontWeight.Bold),
                            color = LoginTextColor
                        )
                        
                        Text(
                            text = profile.bio ?: "Henüz bir biyografi eklenmemiş.",
                            style = MaterialTheme.typography.bodyMedium,
                            color = LoginSecondaryText,
                            textAlign = TextAlign.Center,
                            modifier = Modifier.padding(horizontal = 16.dp)
                        )
                        
                        Spacer(modifier = Modifier.height(16.dp))
                        
                        Button(
                            onClick = { showEditDialog = true },
                            colors = ButtonDefaults.buttonColors(containerColor = LoginButton),
                            shape = RoundedCornerShape(12.dp)
                        ) {
                            Icon(Icons.Default.Edit, contentDescription = null, size = 18.dp)
                            Spacer(modifier = Modifier.width(8.dp))
                            Text("Profili Düzenle")
                        }
                        
                        Spacer(modifier = Modifier.height(32.dp))

                        // Profile Options Section
                        Surface(
                            modifier = Modifier.fillMaxWidth(),
                            shape = RoundedCornerShape(24.dp),
                            color = Color.White.copy(alpha = 0.9f)
                        ) {
                            Column(modifier = Modifier.padding(16.dp)) {
                                ProfileOptionItem(Icons.Default.Settings, "Uygulama Ayarları")
                                Divider(color = Color.LightGray.copy(alpha = 0.3f), modifier = Modifier.padding(vertical = 8.dp))
                                ProfileOptionItem(Icons.Default.DateRange, "Wellness Planım") {
                                    navController.navigate("wellness_schedule")
                                }
                                Divider(color = Color.LightGray.copy(alpha = 0.3f), modifier = Modifier.padding(vertical = 8.dp))
                                ProfileOptionItem(Icons.Default.Edit, "Duygu Günlüğüm") {
                                    navController.navigate("mood_journal")
                                }
                                Divider(color = Color.LightGray.copy(alpha = 0.3f), modifier = Modifier.padding(vertical = 8.dp))
                                ProfileOptionItem(Icons.Default.Notifications, "Bildirimler")
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
                    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                        listOf("supportive" to "Destekleyici", "empathetic" to "Empatik", "direct" to "Net/Doğrudan").forEach { (code, label) ->
                            Row(
                                verticalAlignment = Alignment.CenterVertically,
                                modifier = Modifier.fillMaxWidth().clickable { editStyle = code }.padding(vertical = 4.dp)
                            ) {
                                RadioButton(selected = editStyle == code, onClick = { editStyle = code })
                                Text(label, style = MaterialTheme.typography.bodyMedium)
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
        Icon(Icons.Default.KeyboardArrowRight, contentDescription = null, tint = Color.Gray)
    }
}

@Composable
private fun Icon(imageVector: ImageVector, contentDescription: String?, size: androidx.compose.ui.unit.Dp) {
    Icon(imageVector, contentDescription, modifier = Modifier.size(size))
}

private fun createMultipartFromUri(context: android.content.Context, uri: android.net.Uri): MultipartBody.Part? {
    return try {
        val inputStream = context.contentResolver.openInputStream(uri) ?: return null
        val tempFile = File(context.cacheDir, "temp_profile_photo.jpg")
        val outputStream = FileOutputStream(tempFile)
        inputStream.use { input ->
            outputStream.use { output ->
                input.copyTo(output)
            }
        }
        val requestFile = tempFile.asRequestBody("image/jpeg".toMediaTypeOrNull())
        MultipartBody.Part.createFormData("file", tempFile.name, requestFile)
    } catch (e: Exception) {
        null
    }
}
