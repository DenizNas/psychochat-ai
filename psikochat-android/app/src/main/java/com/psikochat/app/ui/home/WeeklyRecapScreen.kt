package com.psikochat.app.ui.home

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowLeft
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.navigation.NavController
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.lifecycle.viewModelScope
import com.psikochat.app.data.api.RetrofitClient
import com.psikochat.app.data.local.TokenManager
import com.psikochat.app.data.model.Resource
import com.psikochat.app.data.model.WeeklySummaryResponse
import com.psikochat.app.data.repository.WeeklyRecapRepository
import com.psikochat.app.ui.theme.*
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch
import java.util.Locale

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun WeeklyRecapScreen(
    navController: NavController,
    tokenManager: TokenManager
) {
    val api = remember { RetrofitClient.create(tokenManager) }
    val repository = remember { WeeklyRecapRepository(api) }

    val factory = remember {
        object : ViewModelProvider.Factory {
            @Suppress("UNCHECKED_CAST")
            override fun <T : ViewModel> create(modelClass: Class<T>): T {
                return WeeklyRecapViewModel(repository) as T
            }
        }
    }
    val viewModel: WeeklyRecapViewModel = viewModel(factory = factory)
    val recapState by viewModel.recapState.collectAsState()
    val scrollState = rememberScrollState()

    Scaffold(
        topBar = {
            CenterAlignedTopAppBar(
                title = {
                    Text(
                        "Haftalık Özetim",
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Bold,
                        color = LoginTextColor
                    )
                },
                navigationIcon = {
                    IconButton(onClick = { navController.popBackStack() }) {
                        Icon(
                            Icons.AutoMirrored.Filled.KeyboardArrowLeft,
                            contentDescription = "Geri",
                            tint = LoginTextColor
                        )
                    }
                },
                actions = {
                    IconButton(onClick = { viewModel.loadRecap() }) {
                        Icon(Icons.Default.Refresh, contentDescription = "Yenile", tint = LoginTextColor)
                    }
                },
                colors = TopAppBarDefaults.centerAlignedTopAppBarColors(
                    containerColor = Color.Transparent
                )
            )
        },
        containerColor = LoginBackground
    ) { padding ->
        when (val state = recapState) {
            is Resource.Loading -> {
                Box(
                    modifier = Modifier
                        .fillMaxSize()
                        .padding(padding),
                    contentAlignment = Alignment.Center
                ) {
                    CircularProgressIndicator(color = LoginButton)
                }
            }
            is Resource.Error -> {
                Box(
                    modifier = Modifier
                        .fillMaxSize()
                        .padding(padding)
                        .padding(24.dp),
                    contentAlignment = Alignment.Center
                ) {
                    EmptyWeeklyRecapView(
                        message = "Özet yüklenirken bir sorun oluştu. İnternet bağlantınızı kontrol edip tekrar deneyin."
                    )
                }
            }
            is Resource.Success -> {
                val data = state.data
                val totalMessages = data?.totalMessages ?: 0
                val weeklyEvaluation = data?.weeklyEvaluation ?: ""

                if (data == null || totalMessages < 4 || weeklyEvaluation.isBlank()) {
                    Box(
                        modifier = Modifier
                            .fillMaxSize()
                            .padding(padding)
                            .padding(24.dp),
                        contentAlignment = Alignment.Center
                    ) {
                        EmptyWeeklyRecapView(
                            message = "Henüz haftalık özet oluşturacak kadar sohbet verisi bulunmuyor. Birkaç gün uygulamayı kullandıktan sonra burada özetini görebileceksin."
                        )
                    }
                } else {
                    Column(
                        modifier = Modifier
                            .fillMaxSize()
                            .padding(padding)
                            .verticalScroll(scrollState)
                            .padding(horizontal = 20.dp, vertical = 8.dp)
                    ) {
                        // 1. Son 7 Günlük Sohbet Sayısı & En Sık Görülen Duygu
                        Surface(
                            modifier = Modifier.fillMaxWidth(),
                            shape = RoundedCornerShape(24.dp),
                            color = DarkTealPrimary,
                            shadowElevation = 3.dp
                        ) {
                            Column(modifier = Modifier.padding(20.dp)) {
                                Text(
                                    text = "Son 7 Günlük Sohbet Sayısı",
                                    fontSize = 12.sp,
                                    color = Color.White.copy(alpha = 0.75f),
                                    fontWeight = FontWeight.Medium
                                )
                                Spacer(modifier = Modifier.height(4.dp))
                                Text(
                                    text = "$totalMessages sohbet",
                                    fontSize = 24.sp,
                                    fontWeight = FontWeight.Black,
                                    color = Color.White
                                )

                                Spacer(modifier = Modifier.height(16.dp))

                                Text(
                                    text = "En Sık Görülen Duygu",
                                    fontSize = 12.sp,
                                    color = Color.White.copy(alpha = 0.75f),
                                    fontWeight = FontWeight.Medium
                                )
                                Spacer(modifier = Modifier.height(4.dp))
                                Text(
                                    text = mapEmotion(data.dominantEmotion),
                                    fontSize = 20.sp,
                                    fontWeight = FontWeight.Bold,
                                    color = Color.White
                                )
                            }
                        }

                        Spacer(modifier = Modifier.height(20.dp))

                        // 2. Duygu Dağılımı
                        Text(
                            "Duygu Dağılımı",
                            fontSize = 13.sp,
                            fontWeight = FontWeight.Bold,
                            color = LoginTextColor,
                            modifier = Modifier.padding(start = 4.dp, bottom = 12.dp)
                        )

                        Surface(
                            modifier = Modifier.fillMaxWidth(),
                            shape = RoundedCornerShape(20.dp),
                            color = PremiumWhiteCard,
                            border = BorderStroke(1.dp, SoftMintAccent.copy(alpha = 0.5f))
                        ) {
                            Column(modifier = Modifier.padding(20.dp)) {
                                val distribution = data.emotionDistribution
                                val totalEmotions = distribution.values.sum().toFloat()
                                if (distribution.isEmpty()) {
                                    Text(
                                        text = "Duygu dağılım verisi bulunmuyor.",
                                        fontSize = 12.sp,
                                        color = LoginSecondaryText
                                    )
                                } else {
                                    distribution.forEach { (emotion, count) ->
                                        val pct = if (totalEmotions > 0) (count / totalEmotions * 100f).toInt() else 0
                                        val mappedEmotionName = mapEmotion(emotion)
                                        val color = when (emotion.lowercase(Locale.getDefault())) {
                                            "mutluluk", "joy", "happy", "happiness", "neşe" -> Color(0xFF34D399)
                                            "sakin", "calm" -> Color(0xFF60A5FA)
                                            "kaygı", "anxious", "stres", "stress" -> Color(0xFFFBBF24)
                                            "üzüntü", "sad", "sadness", "hüzün" -> Color(0xFF818CF8)
                                            "öfke", "anger", "angry" -> Color(0xFFF87171)
                                            "yorgun", "tired" -> Color(0xFFA78BFA)
                                            else -> Color.Gray
                                        }

                                        Column(modifier = Modifier.padding(vertical = 6.dp)) {
                                            Row(
                                                modifier = Modifier.fillMaxWidth(),
                                                horizontalArrangement = Arrangement.SpaceBetween
                                            ) {
                                                Text(mappedEmotionName, fontSize = 12.sp, color = LoginTextColor, fontWeight = FontWeight.Bold)
                                                Text("%$pct", fontSize = 12.sp, color = LoginSecondaryText)
                                            }
                                            Spacer(modifier = Modifier.height(4.dp))
                                            Box(
                                                modifier = Modifier
                                                    .fillMaxWidth()
                                                    .height(8.dp)
                                                    .clip(CircleShape)
                                                    .background(Color.LightGray.copy(alpha = 0.3f))
                                            ) {
                                                Box(
                                                    modifier = Modifier
                                                        .fillMaxWidth(if (totalEmotions > 0) count / totalEmotions else 0f)
                                                        .fillMaxHeight()
                                                        .clip(CircleShape)
                                                        .background(color)
                                                )
                                            }
                                        }
                                    }
                                }
                            }
                        }

                        Spacer(modifier = Modifier.height(20.dp))

                        // 3. Haftalık Kısa Değerlendirme
                        Text(
                            "Haftalık Kısa Değerlendirme",
                            fontSize = 13.sp,
                            fontWeight = FontWeight.Bold,
                            color = LoginTextColor,
                            modifier = Modifier.padding(start = 4.dp, bottom = 12.dp)
                        )

                        Surface(
                            modifier = Modifier.fillMaxWidth(),
                            shape = RoundedCornerShape(20.dp),
                            color = PremiumWhiteCard,
                            border = BorderStroke(1.dp, SoftMintAccent.copy(alpha = 0.5f))
                        ) {
                            Column(modifier = Modifier.padding(20.dp)) {
                                Text(
                                    text = weeklyEvaluation,
                                    fontSize = 12.sp,
                                    lineHeight = 18.sp,
                                    color = LoginSecondaryText
                                )
                            }
                        }

                        Spacer(modifier = Modifier.height(20.dp))

                        // 4. Destekleyici Not
                        Text(
                            "Destekleyici Not",
                            fontSize = 13.sp,
                            fontWeight = FontWeight.Bold,
                            color = LoginTextColor,
                            modifier = Modifier.padding(start = 4.dp, bottom = 12.dp)
                        )

                        Surface(
                            modifier = Modifier.fillMaxWidth(),
                            shape = RoundedCornerShape(20.dp),
                            color = DarkTealPrimary.copy(alpha = 0.07f),
                            border = BorderStroke(1.dp, DarkTealPrimary.copy(alpha = 0.15f))
                        ) {
                            Row(
                                modifier = Modifier.padding(16.dp),
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Text(text = "💡", fontSize = 24.sp)
                                Spacer(modifier = Modifier.width(14.dp))
                                Text(
                                    text = getSupportiveNote(data.dominantEmotion),
                                    fontSize = 12.sp,
                                    color = LoginTextColor,
                                    lineHeight = 18.sp,
                                    fontWeight = FontWeight.Medium
                                )
                            }
                        }

                        Spacer(modifier = Modifier.height(24.dp))
                    }
                }
            }
        }
    }
}

@Composable
private fun EmptyWeeklyRecapView(message: String) {
    Surface(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(20.dp),
        color = PremiumWhiteCard,
        border = BorderStroke(1.dp, SoftMintAccent.copy(alpha = 0.5f))
    ) {
        Column(
            modifier = Modifier.padding(20.dp),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            Text(text = "🌱", fontSize = 36.sp)
            Spacer(modifier = Modifier.height(10.dp))
            Text(
                text = "Haftalık Özet Hazırlanıyor",
                fontWeight = FontWeight.Bold,
                fontSize = 15.sp,
                color = LoginTextColor,
                textAlign = TextAlign.Center
            )
            Spacer(modifier = Modifier.height(8.dp))
            Text(
                text = message,
                fontSize = 12.sp,
                color = LoginSecondaryText,
                lineHeight = 18.sp,
                textAlign = TextAlign.Center
            )
        }
    }
}

class WeeklyRecapViewModel(
    private val repository: WeeklyRecapRepository
) : ViewModel() {

    private val _recapState = MutableStateFlow<Resource<WeeklySummaryResponse>>(Resource.Loading())
    val recapState: StateFlow<Resource<WeeklySummaryResponse>> = _recapState

    init {
        loadRecap()
    }

    fun loadRecap() {
        viewModelScope.launch {
            _recapState.value = Resource.Loading()
            val result = repository.getWeeklySummary()
            _recapState.value = result
        }
    }
}

private fun mapEmotion(emotion: String): String {
    return when (emotion.lowercase(Locale.getDefault())) {
        "anxiety", "kaygı", "stres", "stress" -> "Kaygı"
        "sadness", "üzüntü", "sad", "hüzün" -> "Üzüntü"
        "anger", "öfke", "angry" -> "Öfke"
        "happiness", "happy", "mutluluk", "neşe", "joy" -> "Mutluluk"
        "calm", "sakin" -> "Sakin"
        "crisis" -> "Hassas Dönem"
        "neutral", "nötr" -> "Nötr"
        else -> emotion.replaceFirstChar { if (it.isLowerCase()) it.titlecase(Locale.getDefault()) else it.toString() }
    }
}

private fun getSupportiveNote(dominantEmotion: String): String {
    return when (dominantEmotion.lowercase(Locale.getDefault())) {
        "anxiety", "kaygı", "stres", "stress", "sadness", "üzüntü", "sad", "hüzün", "anger", "öfke", "angry", "crisis" -> {
            "Bu hafta zorlayıcı duygular yaşamış olsan da duygularını ifade etmek için uygulamayı aktif kullanmış olman önemli bir adım."
        }
        else -> {
            "Bu hafta duygusal dengenizi korumuş ve iyi hissettiğiniz anları pekiştirmek için uygulamayı aktif kullanmış olmanız harika bir adım."
        }
    }
}
