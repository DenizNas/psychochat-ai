package com.psikochat.app.ui.theme
import androidx.compose.runtime.Composable
import androidx.compose.material3.MaterialTheme
import androidx.compose.ui.graphics.Color

val Purple80 = Color(0xFFD0BCFF)
val PurpleGrey80 = Color(0xFFCCC2DC)
val Pink80 = Color(0xFFEFB8C8)
val DarkBackground = Color(0xFF0F172A)
val DarkSurface = Color(0xFF1E293B)
val AccentPrimary = Color(0xFF6366F1)
val DangerRed = Color(0xFFEF4444)
val SystemChatBubble = Color(0xFF334155)

// Static original colors for fallback/LightColorScheme initialization
val LoginBackgroundStatic = Color(0xFFBEE3D3)
val LoginButtonStatic = Color(0xFF78B2A6)
val LoginInputBackgroundStatic = Color(0xFFFFFFFF)
val LoginTextColorStatic = Color(0xFF1A1A1A)
val LoginSecondaryTextStatic = Color(0xFF4A4A4A)

// Theme-aware Composable properties that evaluate dynamically
val LoginBackground: Color
    @Composable
    get() = MaterialTheme.colorScheme.background

val LoginButton: Color
    @Composable
    get() = MaterialTheme.colorScheme.primary

val LoginTextColor: Color
    @Composable
    get() = MaterialTheme.colorScheme.onBackground

val LoginSecondaryText: Color
    @Composable
    get() = MaterialTheme.colorScheme.onSurface

val LoginInputBackground: Color
    @Composable
    get() = MaterialTheme.colorScheme.surface

val PremiumCardSurface: Color
    @Composable
    get() = if (MaterialTheme.colorScheme.background == DarkBackground) DarkSurface else Color.White

val PremiumWhiteCard: Color
    @Composable
    get() = if (MaterialTheme.colorScheme.background == DarkBackground) DarkSurface else Color.White.copy(alpha = 0.9f)

