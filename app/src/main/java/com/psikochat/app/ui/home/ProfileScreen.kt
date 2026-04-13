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
fun ProfileScreen(navController: NavController, tokenManager: TokenManager) {
    val username by tokenManager.getUsername().collectAsState(initial = "Kullanıcı")
    val scope = rememberCoroutineScope()

    Scaffold(
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
                            navController.navigate("login") {
                                popUpTo("home") { inclusive = true }
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
                    label = { Text("Gelişim", fontSize = 10.sp) },
                    selected = true,
                    onClick = { }
                )
                NavigationBarItem(
                    icon = { Icon(Icons.Default.Settings, contentDescription = null) },
                    label = { Text("Ayarlar", fontSize = 10.sp) },
                    selected = false,
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
            
            // Profile Header
            Box(
                modifier = Modifier
                    .size(100.dp)
                    .clip(CircleShape)
                    .background(Color.White)
                    .padding(4.dp)
            ) {
                Box(
                    modifier = Modifier
                        .fillMaxSize()
                        .clip(CircleShape)
                        .background(Color.LightGray),
                    contentAlignment = Alignment.Center
                ) {
                    Icon(Icons.Default.Person, contentDescription = null, modifier = Modifier.size(60.dp), tint = Color.White)
                }
            }
            
            Spacer(modifier = Modifier.height(16.dp))
            
            Text(
                text = username ?: "Kullanıcı",
                style = MaterialTheme.typography.headlineSmall.copy(fontWeight = FontWeight.Bold),
                color = LoginTextColor
            )
            
            Text(
                text = "Kişisel Gelişim Yolculuğunda",
                style = MaterialTheme.typography.bodyMedium,
                color = LoginSecondaryText
            )
            
            Spacer(modifier = Modifier.height(32.dp))

            // Profile Stats/Options
            Surface(
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(24.dp),
                color = Color.White.copy(alpha = 0.9f)
            ) {
                Column(modifier = Modifier.padding(16.dp)) {
                    ProfileOptionItem(Icons.Default.Person, "Kişisel Bilgiler")
                    Divider(color = Color.LightGray.copy(alpha = 0.3f), modifier = Modifier.padding(vertical = 8.dp))
                    ProfileOptionItem(Icons.Default.DateRange, "Sohbet Geçmişi")
                    Divider(color = Color.LightGray.copy(alpha = 0.3f), modifier = Modifier.padding(vertical = 8.dp))
                    ProfileOptionItem(Icons.Default.Star, "Favori Meditasyonlar")
                    Divider(color = Color.LightGray.copy(alpha = 0.3f), modifier = Modifier.padding(vertical = 8.dp))
                    ProfileOptionItem(Icons.Default.Notifications, "Bildirim Ayarları")
                }
            }
            
            Spacer(modifier = Modifier.height(24.dp))
            
            // Support Section
            Surface(
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(24.dp),
                color = LoginButton.copy(alpha = 0.1f)
            ) {
                Row(
                    modifier = Modifier.padding(16.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Icon(Icons.Default.Info, contentDescription = null, tint = LoginButton)
                    Spacer(modifier = Modifier.width(12.dp))
                    Text(
                        "Daha fazla destek için bize her zaman ulaşabilirsin.",
                        fontSize = 12.sp,
                        color = LoginTextColor,
                        modifier = Modifier.weight(1f)
                    )
                }
            }
        }
    }
}

@Composable
fun ProfileOptionItem(icon: ImageVector, title: String) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clickable { /* Navigate */ }
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
