package com.psikochat.app.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

val Purple80 = Color(0xFFD0BCFF)
val PurpleGrey80 = Color(0xFFCCC2DC)
val Pink80 = Color(0xFFEFB8C8)
val DarkBackground = Color(0xFF0F1E1B) // calm very dark teal
val DarkSurface = Color(0xFF152C28) // calm dark teal card
val AccentPrimary = Color(0xFF0F4A42) // dark teal primary
val DangerRed = Color(0xFFEF4444)
val SystemChatBubble = Color(0xFF334155)

// Helper to detect dark theme from MaterialTheme context
val isDarkTheme: Boolean
    @Composable
    get() = MaterialTheme.colorScheme.background == DarkBackground

// New Colors for Login/Wellness redesign
val LoginBackground: Color
    @Composable
    get() = if (isDarkTheme) DarkBackground else Color(0xFFECF5F1) // soft mint background

val LoginButton: Color
    @Composable
    get() = if (isDarkTheme) SoftMintAccent else Color(0xFF0F4A42) // dark teal primary

val LoginInputBackground: Color
    @Composable
    get() = if (isDarkTheme) Color(0xFF1C3732) else Color(0xFFFFFFFF)

val LoginTextColor: Color
    @Composable
    get() = if (isDarkTheme) Color(0xFFE2EBE8) else Color(0xFF1E3531) // premium charcoal text

val LoginSecondaryText: Color
    @Composable
    get() = if (isDarkTheme) Color(0xFF8BA5A0) else Color(0xFF5D7B75) // muted secondary teal text

// Premium Stitch-Style Palette
val SoftMintBackground: Color
    @Composable
    get() = if (isDarkTheme) DarkBackground else Color(0xFFECF5F1)

val DarkTealPrimary = Color(0xFF0F4A42)
val DarkTealAccent = Color(0xFF1E6F63)

val CharcoalText: Color
    @Composable
    get() = if (isDarkTheme) Color(0xFFE2EBE8) else Color(0xFF1E3531)

val SecondaryTealText: Color
    @Composable
    get() = if (isDarkTheme) Color(0xFF8BA5A0) else Color(0xFF5D7B75)

val PremiumWhiteCard: Color
    @Composable
    get() = if (isDarkTheme) DarkSurface else Color(0xFFFFFFFF)

val SoftMintAccent = Color(0xFFD3EBE1)

val SoftMintLight: Color
    @Composable
    get() = if (isDarkTheme) Color(0xFF1E3531) else Color(0xFFF1F8F5)

val MildAlertBg: Color
    @Composable
    get() = if (isDarkTheme) Color(0xFF2C1616) else Color(0xFFFFF0EF)

val MildAlertText: Color
    @Composable
    get() = if (isDarkTheme) Color(0xFFE57373) else Color(0xFFD35C58)
