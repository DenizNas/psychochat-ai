package com.psikochat.app.ui.components

import androidx.compose.foundation.layout.height
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Call
import androidx.compose.material.icons.filled.Email
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.navigation.NavController
import com.psikochat.app.ui.theme.DarkTealPrimary
import com.psikochat.app.ui.theme.SecondaryTealText
import com.psikochat.app.ui.theme.SoftMintAccent

@Composable
fun PremiumBottomNavigation(
    navController: NavController,
    currentScreen: String
) {
    val isDark = MaterialTheme.colorScheme.background == com.psikochat.app.ui.theme.DarkBackground
    val selectedColor = MaterialTheme.colorScheme.primary
    val unselectedColor = SecondaryTealText
    val indicator = if (isDark) com.psikochat.app.ui.theme.DarkTealPrimary else SoftMintAccent

    NavigationBar(
        containerColor = MaterialTheme.colorScheme.surface,
        tonalElevation = 8.dp,
        modifier = Modifier.height(80.dp)
    ) {
        // 1. Ana Sayfa (maps to "home" route)
        NavigationBarItem(
            icon = { Icon(Icons.Default.Person, contentDescription = "Ana Sayfa") },
            label = { Text("Ana Sayfa", fontSize = 10.sp) },
            selected = currentScreen == "home" || currentScreen == "profile",
            colors = NavigationBarItemDefaults.colors(
                selectedIconColor = selectedColor,
                selectedTextColor = selectedColor,
                unselectedIconColor = unselectedColor,
                unselectedTextColor = unselectedColor,
                indicatorColor = indicator
            ),
            onClick = {
                if (currentScreen != "home") {
                    navController.navigate("home") {
                        popUpTo("home") { inclusive = true }
                        launchSingleTop = true
                    }
                }
            }
        )

        // 2. Destek (maps to "therapy" route)
        NavigationBarItem(
            icon = { Icon(Icons.Default.Call, contentDescription = "Destek") },
            label = { Text("Destek", fontSize = 10.sp) },
            selected = currentScreen == "therapy",
            colors = NavigationBarItemDefaults.colors(
                selectedIconColor = selectedColor,
                selectedTextColor = selectedColor,
                unselectedIconColor = unselectedColor,
                unselectedTextColor = unselectedColor,
                indicatorColor = indicator
            ),
            onClick = {
                if (currentScreen != "therapy") {
                    navController.navigate("therapy") {
                        launchSingleTop = true
                    }
                }
            }
        )

        // 3. Sohbet (maps to "chat" route)
        NavigationBarItem(
            icon = { Icon(Icons.Default.Email, contentDescription = "Sohbet") },
            label = { Text("Sohbet", fontSize = 10.sp) },
            selected = currentScreen == "chat",
            colors = NavigationBarItemDefaults.colors(
                selectedIconColor = selectedColor,
                selectedTextColor = selectedColor,
                unselectedIconColor = unselectedColor,
                unselectedTextColor = unselectedColor,
                indicatorColor = indicator
            ),
            onClick = {
                if (currentScreen != "chat") {
                    navController.navigate("chat") {
                        launchSingleTop = true
                    }
                }
            }
        )

        // 4. Ayarlar (maps to "settings" route)
        NavigationBarItem(
            icon = { Icon(Icons.Default.Settings, contentDescription = "Ayarlar") },
            label = { Text("Ayarlar", fontSize = 10.sp) },
            selected = currentScreen == "settings",
            colors = NavigationBarItemDefaults.colors(
                selectedIconColor = selectedColor,
                selectedTextColor = selectedColor,
                unselectedIconColor = unselectedColor,
                unselectedTextColor = unselectedColor,
                indicatorColor = indicator
            ),
            onClick = {
                if (currentScreen != "settings") {
                    navController.navigate("settings") {
                        launchSingleTop = true
                    }
                }
            }
        )
    }
}
