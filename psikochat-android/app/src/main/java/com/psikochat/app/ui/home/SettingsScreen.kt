package com.psikochat.app.ui.home

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
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavController
import com.psikochat.app.data.api.RetrofitClient
import com.psikochat.app.data.local.TokenManager
import com.psikochat.app.data.model.Resource
import com.psikochat.app.data.repository.ProfileRepository
import com.psikochat.app.ui.theme.*
import com.psikochat.app.ui.components.*
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsScreen(navController: NavController, tokenManager: TokenManager) {
    val api = RetrofitClient.create(tokenManager)
    val repository = ProfileRepository(api)
    val factory = object : ViewModelProvider.Factory {
        override fun <T : ViewModel> create(modelClass: Class<T>): T {
            return ProfileViewModel(repository, tokenManager) as T
        }
    }
    val viewModel: ProfileViewModel = viewModel(factory = factory)
    
    val profileState by viewModel.profileState.collectAsState()
    val updateState by viewModel.updateState.collectAsState()
    val scope = rememberCoroutineScope()
    val snackbarHostState = remember { SnackbarHostState() }

    var showThemeDialog by remember { mutableStateOf(false) }
    var showLanguageDialog by remember { mutableStateOf(false) }
    var showAnswerLengthDialog by remember { mutableStateOf(false) }

    LaunchedEffect(updateState) {
        if (updateState is Resource.Error) {
            snackbarHostState.showSnackbar(updateState?.message ?: "Ayarlar kaydedilemedi")
            viewModel.clearUpdateState()
        } else if (updateState is Resource.Success) {
            snackbarHostState.showSnackbar("Ayarlar başarıyla güncellendi")
            viewModel.clearUpdateState()
        }
    }

    Scaffold(
        snackbarHost = { SnackbarHost(snackbarHostState) },
        topBar = {
            CenterAlignedTopAppBar(
                title = {
                    Text(
                        "Ayarlar",
                        style = MaterialTheme.typography.titleMedium,
                        color = LoginTextColor
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
        bottomBar = {
            PremiumBottomNavigation(navController = navController, currentScreen = "settings")
        },
        containerColor = LoginBackground
    ) { padding ->
        Box(modifier = Modifier.fillMaxSize().padding(padding)) {
            when (profileState) {
                is Resource.Loading -> {
                    CircularProgressIndicator(modifier = Modifier.align(Alignment.Center), color = LoginButton)
                }
                is Resource.Error -> {
                    Text(profileState.message ?: "Hata", modifier = Modifier.align(Alignment.Center))
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

                        // Uygulama Ayarları Grubu
                        PremiumCard(
                            modifier = Modifier.fillMaxWidth()
                        ) {
                            Text("Görünüm ve Dil", fontWeight = FontWeight.Bold, color = LoginTextColor, modifier = Modifier.padding(bottom = 8.dp))
                            
                            SettingClickItem(
                                Icons.Default.Build, 
                                "Tema", 
                                when(profile.themePreference) {
                                    "light" -> "Açık"
                                    "dark" -> "Koyu"
                                    else -> "Sistem"
                                }
                            ) { showThemeDialog = true }
                            
                            Divider(color = Color.LightGray.copy(alpha = 0.3f), modifier = Modifier.padding(vertical = 8.dp))
                            
                            SettingClickItem(
                                Icons.Default.Info, 
                                "Uygulama Dili", 
                                if(profile.preferredLanguage == "tr") "Türkçe" else "English"
                            ) { showLanguageDialog = true }
                        }

                        Spacer(modifier = Modifier.height(24.dp))

                        // Tercihler Grubu
                        PremiumCard(
                            modifier = Modifier.fillMaxWidth()
                        ) {
                            Text("Tercihler ve Gizlilik", fontWeight = FontWeight.Bold, color = LoginTextColor, modifier = Modifier.padding(bottom = 8.dp))
                            
                            SettingSwitchItem(
                                Icons.Default.Notifications, 
                                "Bildirimler", 
                                profile.notificationsEnabled
                            ) { viewModel.updateProfile(notifications = it) }
                            
                            Divider(color = Color.LightGray.copy(alpha = 0.3f), modifier = Modifier.padding(vertical = 8.dp))
                            
                            SettingSwitchItem(
                                Icons.Default.Lock, 
                                "Gizlilik Modu", 
                                profile.privacyMode
                            ) { viewModel.updateProfile(privacy = it) }
                            
                            Divider(color = Color.LightGray.copy(alpha = 0.3f), modifier = Modifier.padding(vertical = 8.dp))
                            
                            SettingClickItem(
                                Icons.Default.List, 
                                "Hatırlanan Bilgiler (Hafıza)", 
                                null
                            ) { navController.navigate("memory_settings") }

                            Divider(color = Color.LightGray.copy(alpha = 0.3f), modifier = Modifier.padding(vertical = 8.dp))

                            SettingClickItem(
                                Icons.Default.Lock, 
                                "Kişisel Veriler ve Onaylar", 
                                null
                            ) { navController.navigate("privacy_data") }
                        }

                        Spacer(modifier = Modifier.height(24.dp))

                        // AI Özelleştirme Grubu
                        PremiumCard(
                            modifier = Modifier.fillMaxWidth()
                        ) {
                            Text("AI Özelleştirme", fontWeight = FontWeight.Bold, color = LoginTextColor, modifier = Modifier.padding(bottom = 8.dp))
                            
                            SettingClickItem(
                                Icons.Default.List, 
                                "Yanıt Uzunluğu", 
                                when(profile.answerLengthPreference) {
                                    "short" -> "Kısa"
                                    "detailed" -> "Detaylı"
                                    else -> "Normal"
                                }
                            ) { showAnswerLengthDialog = true }
                            
                            Divider(color = Color.LightGray.copy(alpha = 0.3f), modifier = Modifier.padding(vertical = 8.dp))
                            
                            SettingClickItem(
                                Icons.Default.Star, 
                                "Yanıt Tarzı", 
                                when(profile.responseStyle) {
                                    "direct" -> "Doğrudan"
                                    "empathetic" -> "Empatik"
                                    else -> "Destekleyici"
                                }
                            ) { navController.navigate("profile") }
                        }

                        Spacer(modifier = Modifier.height(24.dp))

                        // Hesap Grubu
                        PremiumCard(
                            modifier = Modifier.fillMaxWidth()
                        ) {
                            Text("Hesap İşlemleri", fontWeight = FontWeight.Bold, color = LoginTextColor, modifier = Modifier.padding(bottom = 8.dp))
                            
                            Row(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .clickable { 
                                        scope.launch {
                                            tokenManager.clearAuthData()
                                            ProfileViewModel.clearCache()
                                            navController.navigate("auth_graph") {
                                                popUpTo("main_graph") { inclusive = true }
                                                launchSingleTop = true
                                            }
                                        }
                                    }
                                    .padding(vertical = 12.dp),
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Icon(Icons.Default.ExitToApp, contentDescription = null, tint = Color.Red)
                                Spacer(modifier = Modifier.width(16.dp))
                                Text("Oturumu Kapat", color = Color.Red, fontWeight = FontWeight.Medium)
                            }
                        }
                        
                        Spacer(modifier = Modifier.height(24.dp))
                        Text("Versiyon 1.1.0", fontSize = 12.sp, color = LoginSecondaryText)
                        Spacer(modifier = Modifier.height(24.dp))
                    }
                    
                    // Dialogs
                    if (showThemeDialog) {
                        AlertDialog(
                            onDismissRequest = { showThemeDialog = false },
                            title = { Text("Tema Seçin") },
                            text = {
                                Column {
                                    listOf("system" to "Sistem Varsayılanı", "light" to "Açık Tema", "dark" to "Koyu Tema").forEach { (code, label) ->
                                        Row(
                                            modifier = Modifier.fillMaxWidth().clickable { 
                                                viewModel.updateProfile(theme = code)
                                                showThemeDialog = false
                                            }.padding(vertical = 12.dp),
                                            verticalAlignment = Alignment.CenterVertically
                                        ) {
                                            RadioButton(selected = profile.themePreference == code, onClick = null)
                                            Spacer(modifier = Modifier.width(12.dp))
                                            Text(label)
                                        }
                                    }
                                }
                            },
                            confirmButton = {}
                        )
                    }

                    if (showLanguageDialog) {
                        AlertDialog(
                            onDismissRequest = { showLanguageDialog = false },
                            title = { Text("Dil Seçin") },
                            text = {
                                Column {
                                    listOf("tr" to "Türkçe", "en" to "English").forEach { (code, label) ->
                                        Row(
                                            modifier = Modifier.fillMaxWidth().clickable { 
                                                viewModel.updateProfile(language = code)
                                                showLanguageDialog = false
                                            }.padding(vertical = 12.dp),
                                            verticalAlignment = Alignment.CenterVertically
                                        ) {
                                            RadioButton(selected = profile.preferredLanguage == code, onClick = null)
                                            Spacer(modifier = Modifier.width(12.dp))
                                            Text(label)
                                        }
                                    }
                                }
                            },
                            confirmButton = {}
                        )
                    }

                    if (showAnswerLengthDialog) {
                        AlertDialog(
                            onDismissRequest = { showAnswerLengthDialog = false },
                            title = { Text("Yanıt Uzunluğu Seçin") },
                            text = {
                                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                                    listOf(
                                        Triple("short", "Kısa (1-2 Cümle)", "1-2 cümlelik kısa yanıtlar."),
                                        Triple("medium", "Normal (3-5 Cümle)", "3-5 cümlelik dengeli yanıtlar."),
                                        Triple("detailed", "Detaylı (Kapsamlı)", "Daha kapsamlı ve açıklayıcı yanıtlar.")
                                    ).forEach { (code, label, desc) ->
                                        Row(
                                            modifier = Modifier
                                                .fillMaxWidth()
                                                .clickable { 
                                                    viewModel.updateProfile(answerLength = code)
                                                    showAnswerLengthDialog = false
                                                }
                                                .padding(vertical = 6.dp),
                                            verticalAlignment = Alignment.Top
                                        ) {
                                            RadioButton(
                                                selected = profile.answerLengthPreference == code,
                                                onClick = null,
                                                modifier = Modifier.padding(top = 2.dp)
                                            )
                                            Spacer(modifier = Modifier.width(12.dp))
                                            Column {
                                                Text(label, style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.Bold, color = LoginTextColor)
                                                Text(desc, style = MaterialTheme.typography.labelSmall, color = LoginSecondaryText, lineHeight = 14.sp)
                                            }
                                        }
                                    }
                                }
                            },
                            confirmButton = {}
                        )
                    }
                }
            }
        }
    }
}

@Composable
fun SettingSwitchItem(icon: ImageVector, title: String, checked: Boolean, onCheckedChange: (Boolean) -> Unit) {
    Row(
        modifier = Modifier.fillMaxWidth().padding(vertical = 8.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.SpaceBetween
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Icon(icon, contentDescription = null, tint = LoginButton, modifier = Modifier.size(24.dp))
            Spacer(modifier = Modifier.width(16.dp))
            Text(text = title, fontWeight = FontWeight.Medium, color = LoginTextColor)
        }
        Switch(
            checked = checked, 
            onCheckedChange = onCheckedChange,
            colors = SwitchDefaults.colors(checkedThumbColor = LoginButton, checkedTrackColor = LoginButton.copy(alpha = 0.5f))
        )
    }
}

@Composable
fun SettingClickItem(icon: ImageVector, title: String, value: String? = null, onClick: () -> Unit) {
    Row(
        modifier = Modifier.fillMaxWidth().clickable { onClick() }.padding(vertical = 12.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Icon(icon, contentDescription = null, tint = LoginButton, modifier = Modifier.size(24.dp))
        Spacer(modifier = Modifier.width(16.dp))
        Text(text = title, fontWeight = FontWeight.Medium, color = LoginTextColor, modifier = Modifier.weight(1f))
        if (value != null) {
            Text(text = value, color = LoginSecondaryText, fontSize = 14.sp, modifier = Modifier.padding(horizontal = 8.dp))
        }
        Icon(Icons.Default.KeyboardArrowRight, contentDescription = null, tint = Color.Gray)
    }
}
