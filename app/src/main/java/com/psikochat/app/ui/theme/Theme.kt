package com.psikochat.app.ui.theme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

private val DarkColorScheme = darkColorScheme(
    primary = LoginButtonStatic,
    secondary = PurpleGrey80,
    tertiary = Pink80,
    background = DarkBackground,
    surface = DarkSurface,
    onBackground = Color.White,
    onSurface = Color(0xFF94A3B8),
    surfaceVariant = DarkSurface,
    outline = Color(0xFF475569),
    error = DangerRed
)

private val LightColorScheme = lightColorScheme(
    primary = LoginButtonStatic,
    secondary = PurpleGrey80,
    tertiary = Pink80,
    background = LoginBackgroundStatic,
    surface = Color.White,
    onBackground = LoginTextColorStatic,
    onSurface = LoginSecondaryTextStatic,
    surfaceVariant = Color.White.copy(alpha = 0.9f),
    outline = Color.LightGray.copy(alpha = 0.5f),
    error = DangerRed
)

@Composable
fun PsikochatTheme(
    themePreference: String = "system",
    content: @Composable () -> Unit
) {
    val darkTheme = when (themePreference) {
        "dark" -> true
        "light" -> false
        else -> isSystemInDarkTheme()
    }
    
    val colorScheme = if (darkTheme) DarkColorScheme else LightColorScheme
    
    MaterialTheme(
        colorScheme = colorScheme,
        content = content
    )
}
