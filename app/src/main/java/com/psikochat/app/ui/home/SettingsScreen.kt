package com.psikochat.app.ui.home

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
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
import androidx.navigation.NavController
import com.psikochat.app.data.local.TokenManager
import com.psikochat.app.ui.theme.*
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsScreen(navController: NavController, tokenManager: TokenManager) {
    val scope = rememberCoroutineScope()
    var notificationsEnabled by remember { mutableStateOf(true) }
    var darkModeEnabled by remember { mutableStateOf(false) }

    Scaffold(
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
                    label = { Text("Gelişim", fontSize = 10.sp) },
                    selected = false,
                    onClick = { navController.navigate("profile") }
                )
                NavigationBarItem(
                    icon = { Icon(Icons.Default.Settings, contentDescription = null) },
                    label = { Text("Ayarlar", fontSize = 10.sp) },
                    selected = true,
                    onClick = { }
                )
            }
        },
        containerColor = LoginBackground
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(horizontal = 24.dp),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            Spacer(modifier = Modifier.height(24.dp))

            Surface(
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(24.dp),
                color = Color.White.copy(alpha = 0.9f)
            ) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Text("Uygulama Ayarları", fontWeight = FontWeight.Bold, color = LoginTextColor, modifier = Modifier.padding(bottom = 8.dp))
                    
                    SettingSwitchItem(Icons.Default.Notifications, "Bildirimler", notificationsEnabled) { notificationsEnabled = it }
                    Divider(color = Color.LightGray.copy(alpha = 0.3f), modifier = Modifier.padding(vertical = 8.dp))
                    SettingSwitchItem(Icons.Default.Build, "Karanlık Mod", darkModeEnabled) { darkModeEnabled = it }
                    Divider(color = Color.LightGray.copy(alpha = 0.3f), modifier = Modifier.padding(vertical = 8.dp))
                    SettingClickItem(Icons.Default.Info, "Dil Seçeneği", "Türkçe")
                }
            }

            Spacer(modifier = Modifier.height(24.dp))

            Surface(
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(24.dp),
                color = Color.White.copy(alpha = 0.9f)
            ) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Text("Hesap ve Güvenlik", fontWeight = FontWeight.Bold, color = LoginTextColor, modifier = Modifier.padding(bottom = 8.dp))
                    
                    SettingClickItem(Icons.Default.Lock, "Şifre Değiştir")
                    Divider(color = Color.LightGray.copy(alpha = 0.3f), modifier = Modifier.padding(vertical = 8.dp))
                    SettingClickItem(Icons.Default.Email, "E-posta Güncelle")
                    Divider(color = Color.LightGray.copy(alpha = 0.3f), modifier = Modifier.padding(vertical = 8.dp))
                    
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .clickable { 
                                scope.launch {
                                    tokenManager.clearAuthData()
                                    navController.navigate("login") {
                                        popUpTo(0) { inclusive = true }
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
            }
            
            Spacer(modifier = Modifier.height(24.dp))
            
            Text("Versiyon 1.0.0", fontSize = 12.sp, color = LoginSecondaryText)
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
fun SettingClickItem(icon: ImageVector, title: String, value: String? = null) {
    Row(
        modifier = Modifier.fillMaxWidth().clickable { }.padding(vertical = 12.dp),
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
