package com.psikochat.app.ui.insights

import android.content.Intent
import android.net.Uri
import androidx.compose.animation.*
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.AutoAwesome
import androidx.compose.material.icons.filled.Call
import androidx.compose.material.icons.filled.Info
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavController
import com.psikochat.app.data.api.RetrofitClient
import com.psikochat.app.data.local.TokenManager
import com.psikochat.app.data.model.ReflectionResponse
import com.psikochat.app.data.repository.ReflectionRepository
import com.psikochat.app.ui.theme.*

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ReflectionScreen(navController: NavController, tokenManager: TokenManager) {
    val api = RetrofitClient.create(tokenManager)
    val repo = ReflectionRepository(api)
    val factory = object : ViewModelProvider.Factory {
        override fun <T : ViewModel> create(modelClass: Class<T>): T {
            return ReflectionViewModel(repo) as T
        }
    }
    val viewModel: ReflectionViewModel = viewModel(factory = factory)
    val uiState by viewModel.reflectionState.collectAsState()
    
    var selectedPeriod by remember { mutableStateOf("daily") } // "daily" or "weekly"

    LaunchedEffect(selectedPeriod) {
        viewModel.loadReflection(selectedPeriod)
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Text(
                        text = "Kişisel Refleksiyon",
                        fontWeight = FontWeight.Bold,
                        fontSize = 20.sp,
                        color = Color.White
                    )
                },
                navigationIcon = {
                    IconButton(onClick = { navController.popBackStack() }) {
                        Icon(
                            imageVector = Icons.Default.ArrowBack,
                            contentDescription = "Geri",
                            tint = Color.White
                        )
                    }
                },
                actions = {
                    IconButton(onClick = {
                        viewModel.loadReflection(selectedPeriod)
                    }) {
                        Icon(
                            imageVector = Icons.Default.Refresh,
                            contentDescription = "Yenile",
                            tint = Color.White
                        )
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = DarkSurface)
            )
        },
        containerColor = DarkBackground
    ) { padding ->
        Column(
            modifier = Modifier
                .padding(padding)
                .fillMaxSize()
        ) {
            // Period selector tabs
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(16.dp)
                    .background(DarkSurface, RoundedCornerShape(12.dp))
                    .padding(4.dp),
                horizontalArrangement = Arrangement.SpaceEvenly
            ) {
                listOf("daily" to "Günlük Refleksiyon", "weekly" to "Haftalık Refleksiyon").forEach { (periodKey, label) ->
                    val isSelected = selectedPeriod == periodKey
                    Box(
                        modifier = Modifier
                            .weight(1f)
                            .background(
                                color = if (isSelected) AccentPrimary else Color.Transparent,
                                shape = RoundedCornerShape(8.dp)
                            )
                            .clickable { selectedPeriod = periodKey }
                            .padding(vertical = 10.dp),
                        contentAlignment = Alignment.Center
                    ) {
                        Text(
                            text = label,
                            color = if (isSelected) Color.White else Color.Gray,
                            fontWeight = FontWeight.Bold,
                            fontSize = 14.sp
                        )
                    }
                }
            }

            AnimatedContent(
                targetState = uiState,
                transitionSpec = {
                    fadeIn() togetherWith fadeOut()
                },
                label = "reflection_state_transition"
            ) { state ->
                when (state) {
                    is ReflectionUiState.Loading -> {
                        Box(
                            modifier = Modifier.fillMaxSize(),
                            contentAlignment = Alignment.Center
                        ) {
                            CircularProgressIndicator(color = AccentPrimary)
                        }
                    }
                    is ReflectionUiState.Success -> {
                        ReflectionContent(reflection = state.reflection)
                    }
                    is ReflectionUiState.Empty -> {
                        EmptyReflectionView()
                    }
                    is ReflectionUiState.Error -> {
                        ErrorReflectionView(
                            message = state.message,
                            onRetry = {
                                viewModel.loadReflection(selectedPeriod)
                            }
                        )
                    }
                }
            }
        }
    }
}

@Composable
fun ReflectionContent(reflection: ReflectionResponse) {
    val context = LocalContext.current
    val isCrisis = reflection.tone == "supportive_crisis" || reflection.dominant_emotion.lowercase() == "crisis"

    val pastelAccent = when (reflection.dominant_emotion.lowercase()) {
        "mutluluk", "happiness", "joy" -> Color(0xFF86EFAC)
        "kaygı", "anxiety", "stres", "stress" -> Color(0xFFFCD34D)
        "üzüntü", "sadness", "sad" -> Color(0xFF93C5FD)
        "öfke", "anger", "angry" -> Color(0xFFFCA5A5)
        "crisis" -> Color(0xFFFCA5A5)
        else -> Color(0xFF94A3B8)
    }

    LazyColumn(
        modifier = Modifier
            .fillMaxSize()
            .padding(horizontal = 16.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
        contentPadding = PaddingValues(bottom = 24.dp)
    ) {
        // Main Reflection Card
        item {
            Card(
                modifier = Modifier.fillMaxWidth(),
                colors = CardDefaults.cardColors(containerColor = DarkSurface),
                border = BorderStroke(
                    1.5.dp, 
                    Brush.verticalGradient(
                        if (isCrisis) listOf(DangerRed, Color(0xFFEF4444)) 
                        else listOf(AccentPrimary, pastelAccent)
                    )
                ),
                shape = RoundedCornerShape(20.dp)
            ) {
                Column(
                    modifier = Modifier.padding(20.dp)
                ) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Icon(
                                imageVector = Icons.Default.AutoAwesome,
                                contentDescription = "AI",
                                tint = if (isCrisis) DangerRed else AccentPrimary,
                                modifier = Modifier.size(20.dp)
                            )
                            Spacer(modifier = Modifier.width(8.dp))
                            Text(
                                text = reflection.reflection_title,
                                fontWeight = FontWeight.Bold,
                                fontSize = 18.sp,
                                color = Color.White
                            )
                        }
                    }
                    Spacer(modifier = Modifier.height(16.dp))
                    Text(
                        text = reflection.reflection_text,
                        fontSize = 14.sp,
                        color = Color.White.copy(alpha = 0.95f),
                        lineHeight = 22.sp,
                        fontWeight = FontWeight.Medium
                    )
                }
            }
        }

        // Crisis Redirect Actions
        if (isCrisis) {
            item {
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    colors = CardDefaults.cardColors(containerColor = DangerRed.copy(alpha = 0.15f)),
                    border = BorderStroke(1.dp, DangerRed.copy(alpha = 0.5f)),
                    shape = RoundedCornerShape(16.dp)
                ) {
                    Column(
                        modifier = Modifier.padding(16.dp),
                        horizontalAlignment = Alignment.CenterHorizontally
                    ) {
                        Row(
                            verticalAlignment = Alignment.CenterVertically,
                            modifier = Modifier.fillMaxWidth()
                        ) {
                            Icon(
                                imageVector = Icons.Default.Info,
                                contentDescription = "Destek",
                                tint = DangerRed,
                                modifier = Modifier.size(20.dp)
                            )
                            Spacer(modifier = Modifier.width(8.dp))
                            Text(
                                text = "Acil ve Profesyonel Destek Hatları",
                                fontWeight = FontWeight.Bold,
                                fontSize = 14.sp,
                                color = Color.White
                            )
                        }
                        Spacer(modifier = Modifier.height(12.dp))
                        Text(
                            text = "Kendinizi yalnız hissettiğinizde veya konuşacak bir uzmana ihtiyaç duyduğunuzda, aşağıdaki resmi kanallardan tamamen ücretsiz destek alabilirsiniz.",
                            fontSize = 12.sp,
                            color = Color.White.copy(alpha = 0.8f),
                            lineHeight = 18.sp,
                            textAlign = TextAlign.Start
                        )
                        Spacer(modifier = Modifier.height(16.dp))
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceEvenly
                        ) {
                            Button(
                                onClick = {
                                    val intent = Intent(Intent.ACTION_DIAL, Uri.parse("tel:112"))
                                    context.startActivity(intent)
                                },
                                colors = ButtonDefaults.buttonColors(containerColor = DangerRed),
                                shape = RoundedCornerShape(10.dp)
                            ) {
                                Icon(Icons.Default.Call, contentDescription = null, modifier = Modifier.size(16.dp))
                                Spacer(modifier = Modifier.width(6.dp))
                                Text("112 Acil", fontSize = 12.sp, fontWeight = FontWeight.Bold)
                            }
                            Button(
                                onClick = {
                                    val intent = Intent(Intent.ACTION_DIAL, Uri.parse("tel:114"))
                                    context.startActivity(intent)
                                },
                                colors = ButtonDefaults.buttonColors(containerColor = AccentPrimary),
                                shape = RoundedCornerShape(10.dp)
                            ) {
                                Icon(Icons.Default.Call, contentDescription = null, modifier = Modifier.size(16.dp))
                                Spacer(modifier = Modifier.width(6.dp))
                                Text("114 Psikolojik Destek", fontSize = 12.sp, fontWeight = FontWeight.Bold)
                            }
                        }
                    }
                }
            }
        }

        // Generated From sources card
        if (reflection.generated_from.isNotEmpty()) {
            item {
                Column(
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Text(
                        text = "Analiz Edilen Kanallar",
                        fontWeight = FontWeight.Bold,
                        fontSize = 14.sp,
                        color = Color.Gray,
                        modifier = Modifier.padding(start = 4.dp, bottom = 8.dp)
                    )
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        reflection.generated_from.forEach { source ->
                            val label = when (source) {
                                "emotion_summary" -> "Duygu Seyri"
                                "behavioral_insights" -> "Davranış Örüntüleri"
                                "mood_journal" -> "Günlük Kayıtları"
                                "scheduled_interventions" -> "Zihinsel Egzersizler"
                                else -> source
                            }
                            Box(
                                modifier = Modifier
                                    .background(DarkSurface, RoundedCornerShape(20.dp))
                                    .border(1.dp, pastelAccent.copy(alpha = 0.3f), RoundedCornerShape(20.dp))
                                    .padding(horizontal = 12.dp, vertical = 6.dp)
                            ) {
                                Text(
                                    text = label,
                                    color = Color.White.copy(alpha = 0.85f),
                                    fontSize = 11.sp,
                                    fontWeight = FontWeight.SemiBold
                                )
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
fun EmptyReflectionView() {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(24.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center
    ) {
        Box(
            modifier = Modifier
                .size(64.dp)
                .background(AccentPrimary.copy(alpha = 0.1f), RoundedCornerShape(16.dp)),
            contentAlignment = Alignment.Center
        ) {
            Icon(
                imageVector = Icons.Default.AutoAwesome,
                contentDescription = null,
                tint = AccentPrimary,
                modifier = Modifier.size(32.dp)
            )
        }
        Spacer(modifier = Modifier.height(16.dp))
        Text(
            text = "Yetersiz Veri",
            fontWeight = FontWeight.Bold,
            fontSize = 18.sp,
            color = Color.White,
            textAlign = TextAlign.Center
        )
        Spacer(modifier = Modifier.height(8.dp))
        Text(
            text = "Kişisel zihinsel refleksiyonlarınızı hazırlayabilmemiz için son zamanlarda en az 4 adet sohbet mesajı veya mood günlüğü kaydı girmelisiniz.",
            fontSize = 14.sp,
            color = Color.Gray,
            textAlign = TextAlign.Center,
            lineHeight = 20.sp
        )
    }
}

@Composable
fun ErrorReflectionView(message: String, onRetry: () -> Unit) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(24.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center
    ) {
        Text(
            text = "Refleksiyon Yüklenemedi",
            fontWeight = FontWeight.Bold,
            fontSize = 18.sp,
            color = DangerRed,
            textAlign = TextAlign.Center
        )
        Spacer(modifier = Modifier.height(8.dp))
        Text(
            text = message,
            fontSize = 14.sp,
            color = Color.Gray,
            textAlign = TextAlign.Center
        )
        Spacer(modifier = Modifier.height(16.dp))
        Button(
            onClick = onRetry,
            colors = ButtonDefaults.buttonColors(containerColor = AccentPrimary)
        ) {
            Text("Yeniden Dene", color = Color.White)
        }
    }
}
