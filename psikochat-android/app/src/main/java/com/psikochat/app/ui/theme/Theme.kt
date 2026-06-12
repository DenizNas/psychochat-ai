package com.psikochat.app.ui.theme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

private val LightColorScheme = lightColorScheme(
    primary = DarkTealPrimary,
    onPrimary = Color.White,
    secondary = DarkTealAccent,
    onSecondary = Color.White,
    background = Color(0xFFECF5F1),
    onBackground = Color(0xFF1E3531),
    surface = Color(0xFFFFFFFF),
    onSurface = Color(0xFF1E3531)
)

private val DarkColorScheme = darkColorScheme(
    primary = DarkTealAccent,
    onPrimary = Color.White,
    secondary = SoftMintAccent,
    onSecondary = Color(0xFF1E3531),
    background = DarkBackground,
    onBackground = Color(0xFFE2EBE8),
    surface = DarkSurface,
    onSurface = Color(0xFFE2EBE8)
)

@Composable
fun PsikochatTheme(
    darkTheme: Boolean = false,
    content: @Composable () -> Unit
) {
    val colorScheme = if (darkTheme) DarkColorScheme else LightColorScheme
    MaterialTheme(
        colorScheme = colorScheme,
        content = content
    )
}

