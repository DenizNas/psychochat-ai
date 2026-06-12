package com.psikochat.app.ui.components

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import com.psikochat.app.ui.theme.PremiumWhiteCard
import com.psikochat.app.ui.theme.SoftMintAccent
import com.psikochat.app.ui.theme.DarkBackground

@Composable
fun PremiumCard(
    modifier: Modifier = Modifier,
    backgroundColor: Color = Color.Unspecified,
    cornerRadius: Dp = 24.dp,
    elevation: Dp = 1.dp,
    border: BorderStroke? = null,
    content: @Composable ColumnScope.() -> Unit
) {
    val resolvedBg = if (backgroundColor == Color.Unspecified) PremiumWhiteCard else backgroundColor
    val isDark = MaterialTheme.colorScheme.background == DarkBackground
    val resolvedBorder = border ?: BorderStroke(
        1.dp,
        if (isDark) Color(0xFF1E3F39) else SoftMintAccent.copy(alpha = 0.5f)
    )
    Surface(
        modifier = modifier,
        shape = RoundedCornerShape(cornerRadius),
        color = resolvedBg,
        shadowElevation = elevation,
        border = resolvedBorder
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            content()
        }
    }
}
