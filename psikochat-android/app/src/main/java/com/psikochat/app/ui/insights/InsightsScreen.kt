package com.psikochat.app.ui.insights

import androidx.compose.animation.*
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.Favorite
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.TrendingUp
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.drawscope.Stroke
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
import com.psikochat.app.data.model.BehavioralInsight
import com.psikochat.app.data.model.DailyTrendItem
import com.psikochat.app.data.model.EmotionSummaryResponse
import com.psikochat.app.data.model.SmartIntervention
import com.psikochat.app.data.repository.AnalyticsRepository
import com.psikochat.app.ui.theme.*

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun InsightsScreen(navController: NavController, tokenManager: TokenManager) {
    val api = RetrofitClient.create(tokenManager)
    val repo = AnalyticsRepository(api)
    val factory = object : ViewModelProvider.Factory {
        override fun <T : ViewModel> create(modelClass: Class<T>): T {
            return InsightsViewModel(repo) as T
        }
    }
    val viewModel: InsightsViewModel = viewModel(factory = factory)
    
    val uiState by viewModel.uiState.collectAsState()
    var selectedDays by remember { mutableStateOf(7) }

    LaunchedEffect(selectedDays) {
        viewModel.loadInsightsAndSummary(selectedDays)
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { 
                    Text(
                        text = "Gelişim ve Analizler", 
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
                    IconButton(onClick = { viewModel.loadInsightsAndSummary(selectedDays) }) {
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
                .padding(horizontal = 16.dp)
        ) {
            Spacer(modifier = Modifier.height(12.dp))
            
            // Period Filter Chip
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .background(DarkSurface, shape = RoundedCornerShape(12.dp))
                    .padding(4.dp),
                horizontalArrangement = Arrangement.SpaceEvenly
            ) {
                val daysOptions = listOf(7 to "Son 7 Gün", 30 to "Son 30 Gün")
                daysOptions.forEach { (days, label) ->
                    val isSelected = selectedDays == days
                    Box(
                        modifier = Modifier
                            .weight(1f)
                            .background(
                                color = if (isSelected) AccentPrimary else Color.Transparent,
                                shape = RoundedCornerShape(10.dp)
                            )
                            .clickable { selectedDays = days }
                            .padding(vertical = 10.dp),
                        contentAlignment = Alignment.Center
                    ) {
                        Text(
                            text = label,
                            color = if (isSelected) Color.White else Color.Gray,
                            fontWeight = if (isSelected) FontWeight.SemiBold else FontWeight.Normal,
                            fontSize = 14.sp
                        )
                    }
                }
            }

            Spacer(modifier = Modifier.height(16.dp))

            // State Renderer
            Box(
                modifier = Modifier.weight(1f).fillMaxWidth(),
                contentAlignment = Alignment.Center
            ) {
                when (val state = uiState) {
                    is InsightsUiState.Loading -> {
                        CircularProgressIndicator(color = AccentPrimary)
                    }
                    is InsightsUiState.Empty -> {
                        EmptyStateView()
                    }
                    is InsightsUiState.Error -> {
                        ErrorStateView(message = state.message) {
                            viewModel.loadInsightsAndSummary(selectedDays)
                        }
                    }
                    is InsightsUiState.Success -> {
                        LazyColumn(
                            verticalArrangement = Arrangement.spacedBy(16.dp),
                            contentPadding = PaddingValues(bottom = 24.dp),
                            modifier = Modifier.fillMaxSize()
                        ) {
                            // 1. Dominant Emotion Widget
                            item {
                                DominantEmotionCard(state.summary)
                            }
                            
                            // 2. Emotion Distribution Card
                            item {
                                EmotionDistributionCard(state.summary.emotion_distribution)
                            }

                            // 3. Daily Trend Canvas Plot
                            item {
                                DailyTrendLineChart(state.summary.daily_trend)
                            }

                            // 4. Crisis Comfort Indicator
                            item {
                                CrisisTrendIndicator(state.summary.crisis_count)
                            }

                            // 5. Smart Interventions List Section
                            if (state.interventions.isNotEmpty()) {
                                item {
                                    Text(
                                        text = "Önerilen Aktivite ve Destekler",
                                        color = Color.White,
                                        fontSize = 18.sp,
                                        fontWeight = FontWeight.Bold,
                                        modifier = Modifier.padding(top = 8.dp, bottom = 4.dp)
                                    )
                                }

                                items(state.interventions) { intervention ->
                                    SmartInterventionCard(intervention)
                                }
                            }

                            // 6. Header for Insight cards
                            if (state.insights.isNotEmpty()) {
                                item {
                                    Text(
                                        text = "Davranışsal İçgörüler",
                                        color = Color.White,
                                        fontSize = 18.sp,
                                        fontWeight = FontWeight.Bold,
                                        modifier = Modifier.padding(top = 8.dp, bottom = 4.dp)
                                    )
                                }
                                
                                items(state.insights) { insight ->
                                    BehavioralInsightCard(insight)
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
fun SmartInterventionCard(intervention: SmartIntervention) {
    val (color, tagLabel) = when (intervention.severity.lowercase()) {
        "priority_support" -> Color(0xFFFCA5A5) to "Öncelikli Gözlem & Rehberlik"  // Soft rose
        "supportive" -> Color(0xFFFCD34D) to "Zihinsel Egzersiz"                // Pastel amber
        else -> Color(0xFF86EFAC) to "Bedensel Mola"                            // Soft green
    }

    Card(
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(containerColor = DarkSurface),
        border = BorderStroke(1.dp, color.copy(alpha = 0.25f)),
        modifier = Modifier.fillMaxWidth()
    ) {
        Row(
            modifier = Modifier.padding(16.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Box(
                modifier = Modifier
                    .size(40.dp)
                    .background(color.copy(alpha = 0.15f), shape = RoundedCornerShape(10.dp)),
                contentAlignment = Alignment.Center
            ) {
                Icon(
                    imageVector = Icons.Default.Favorite,
                    contentDescription = "Aktivite",
                    tint = color,
                    modifier = Modifier.size(22.dp)
                )
            }
            Spacer(modifier = Modifier.width(16.dp))
            Column(modifier = Modifier.weight(1f)) {
                // Header with soft severity tag
                Surface(
                    color = color.copy(alpha = 0.1f),
                    shape = RoundedCornerShape(6.dp),
                    border = BorderStroke(0.5.dp, color.copy(alpha = 0.3f))
                ) {
                    Text(
                        text = tagLabel,
                        color = color,
                        fontSize = 10.sp,
                        fontWeight = FontWeight.Bold,
                        modifier = Modifier.padding(horizontal = 8.dp, vertical = 3.dp)
                    )
                }

                Spacer(modifier = Modifier.height(6.dp))

                // Title
                Text(
                    text = intervention.title,
                    color = Color.White,
                    fontSize = 15.sp,
                    fontWeight = FontWeight.Bold
                )

                Spacer(modifier = Modifier.height(4.dp))

                // Description
                Text(
                    text = intervention.description,
                    color = Color.LightGray,
                    fontSize = 12.sp,
                    lineHeight = 16.sp
                )
            }
        }
    }
}

@Composable
fun DominantEmotionCard(summary: EmotionSummaryResponse) {
    val rawEmotion = summary.dominant_emotion ?: "neutral"
    
    // Emotion mapping to supportive Turkish values
    val (emotionText, emotionDesc, color) = when (rawEmotion.lowercase()) {
        "joy", "happiness", "mutlu", "neşe", "mutluluk" -> Triple(
            "Huzur ve Neşe", 
            "Son sohbetlerinizde yüksek düzeyde olumlu duygular ve huzur gözlemlendi. Bu güzel gidişatı destekleyen alışkanlıklarınızı sürdürün.",
            Color(0xFF86EFAC)
        )
        "anxiety", "kaygı", "stres", "stress" -> Triple(
            "Kaygı ve Stres Yoğunluğu", 
            "Son günlerde zihniniz biraz yorgun veya kaygılı olabilir. Bu tamamen geçici bir süreçtir; kendinize dinlenmek ve nefes almak için küçük alanlar açın.",
            Color(0xFFFCD34D)
        )
        "sadness", "üzüntü", "sad", "durgun" -> Triple(
            "Hüzün ve Düşük Enerji", 
            "Paylaşımlarınızda sakin, durgun veya hüzünlü temalar ön planda. Kendinize karşı nazik olun, duygularınızı bastırmadan yaşamanız son derece sağlıklıdır.",
            Color(0xFF93C5FD)
        )
        "anger", "öfke", "angry", "kızgın" -> Triple(
            "Gerginlik ve Öfke Eğilimi", 
            "Sohbetlerinizde hayal kırıklığı veya gergin hisler yansımış. Bu hislerin altında yatan ihtiyaçlarınızı fark etmek ve dinlenmek size yardımcı olabilir.",
            Color(0xFFFCA5A5)
        )
        else -> Triple(
            "Stabil ve Dengeli", 
            "Duygu durumunuz genel olarak dengeli ve nötr bir çizgide seyrediyor. Zihinsel dengenizi korumaya devam ediyorsunuz.",
            Color(0xFF94A3B8)
        )
    }

    Card(
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(containerColor = DarkSurface),
        border = BorderStroke(1.dp, color.copy(alpha = 0.25f)),
        modifier = Modifier.fillMaxWidth()
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Text(
                text = "Haftalık Duygu Özeti",
                color = Color.Gray,
                fontSize = 12.sp,
                fontWeight = FontWeight.Medium
            )
            Spacer(modifier = Modifier.height(8.dp))
            Text(
                text = "En Sık Gözlemlenen Duygu: $emotionText",
                color = color,
                fontSize = 18.sp,
                fontWeight = FontWeight.Bold
            )
            Spacer(modifier = Modifier.height(8.dp))
            Text(
                text = emotionDesc,
                color = Color.LightGray,
                fontSize = 13.sp,
                lineHeight = 18.sp
            )
        }
    }
}

@Composable
fun EmotionDistributionCard(distribution: Map<String, Int>) {
    Card(
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(containerColor = DarkSurface),
        modifier = Modifier.fillMaxWidth()
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Text(
                text = "Duygu Dağılım Oranları",
                color = Color.White,
                fontSize = 15.sp,
                fontWeight = FontWeight.Bold
            )
            Spacer(modifier = Modifier.height(12.dp))
            
            val total = distribution.values.sum().coerceAtLeast(1)
            val sortedDist = distribution.entries.sortedByDescending { it.value }

            sortedDist.forEach { (emotion, count) ->
                val pct = (count.toFloat() / total * 100).toInt()
                val (color, name) = when (emotion.lowercase()) {
                    "joy", "happiness", "mutlu", "neşe", "mutluluk" -> Color(0xFF86EFAC) to "Huzur / Neşe"
                    "anxiety", "kaygı", "stres", "stress" -> Color(0xFFFCD34D) to "Kaygı / Stres"
                    "sadness", "üzüntü", "sad", "durgun" -> Color(0xFF93C5FD) to "Hüzün / Durgunluk"
                    "anger", "öfke", "angry", "kızgın" -> Color(0xFFFCA5A5) to "Öfke / Gerginlik"
                    else -> Color(0xFF94A3B8) to "Denge / Nötr"
                }

                Column(modifier = Modifier.padding(vertical = 4.dp)) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween
                    ) {
                        Text(text = name, color = Color.White, fontSize = 13.sp)
                        Text(text = "%$pct ($count mesaj)", color = Color.Gray, fontSize = 12.sp)
                    }
                    Spacer(modifier = Modifier.height(4.dp))
                    
                    // Simple custom progress bar matching the palette
                    Box(
                        modifier = Modifier
                            .fillMaxWidth()
                            .height(8.dp)
                            .background(Color(0xFF334155), shape = RoundedCornerShape(4.dp))
                    ) {
                        Box(
                            modifier = Modifier
                                .fillMaxHeight()
                                .fillMaxWidth(fraction = count.toFloat() / total)
                                .background(color, shape = RoundedCornerShape(4.dp))
                        )
                    }
                }
            }
        }
    }
}

@Composable
fun DailyTrendLineChart(dailyTrend: List<DailyTrendItem>) {
    Card(
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(containerColor = DarkSurface),
        modifier = Modifier.fillMaxWidth()
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Text(
                text = "Duygu Durum Zaman Çizelgesi",
                color = Color.White,
                fontSize = 15.sp,
                fontWeight = FontWeight.Bold
            )
            Spacer(modifier = Modifier.height(6.dp))
            Text(
                text = "Zaman içindeki duygusal denge değişimi (Yükselen çizgiler huzur eğilimini, düşen çizgiler stres/hassasiyeti simgeler).",
                color = Color.Gray,
                fontSize = 11.sp,
                lineHeight = 15.sp
            )
            Spacer(modifier = Modifier.height(16.dp))

            // Standardize sentiment scores for drawing: joy = 1.0, sadness = -0.5, anxiety/anger = -1.0
            val scores = dailyTrend.map { item ->
                val total = item.total_count.coerceAtLeast(1)
                var joy = 0
                var stress = 0
                var sad = 0
                
                item.emotions.forEach { (em, count) ->
                    when (em.lowercase()) {
                        "joy", "happiness", "mutlu", "neşe", "mutluluk" -> joy += count
                        "anxiety", "kaygı", "stres", "stress", "anger", "öfke", "angry" -> stress += count
                        "sadness", "üzüntü", "sad", "durgun" -> sad += count
                    }
                }
                // Calculate normalized score ranging from -1.0 to +1.0
                (joy.toFloat() - stress.toFloat() - 0.5f * sad.toFloat()) / total
            }

            if (scores.size < 2) {
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(140.dp),
                    contentAlignment = Alignment.Center
                ) {
                    Text(text = "Trend grafiği için daha fazla gün etkileşimi gerekiyor.", color = Color.Gray, fontSize = 12.sp)
                }
            } else {
                // Compose Custom Drawing Canvas
                Canvas(
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(140.dp)
                ) {
                    val width = size.width
                    val height = size.height
                    val stepX = width / (scores.size - 1)
                    
                    // Score range is -1.0 to +1.0. We map this to Y coordinates:
                    // +1.0 (joy) maps to 10% from the top
                    // -1.0 (stress) maps to 90% from the top
                    val points = scores.mapIndexed { idx, score ->
                        val x = idx * stepX
                        val normalizedScore = (score + 1f) / 2f
                        val y = height * 0.9f - (normalizedScore * height * 0.8f)
                        Offset(x, y)
                    }

                    // 1. Draw grid background lines
                    val gridLines = 3
                    for (i in 0..gridLines) {
                        val gridY = height * 0.1f + (i * height * 0.8f / gridLines)
                        drawLine(
                            color = Color(0xFF334155).copy(alpha = 0.4f),
                            start = Offset(0f, gridY),
                            end = Offset(width, gridY),
                            strokeWidth = 1.dp.toPx()
                        )
                    }

                    // 2. Draw smooth Bezier Curved Trend Path
                    val path = Path().apply {
                        moveTo(points.first().x, points.first().y)
                        for (i in 1 until points.size) {
                            val prev = points[i - 1]
                            val curr = points[i]
                            val cx = (prev.x + curr.x) / 2
                            cubicTo(cx, prev.y, cx, curr.y, curr.x, curr.y)
                        }
                    }

                    // 3. Draw gradient area below the curved line
                    val fillPath = Path().apply {
                        addPath(path)
                        lineTo(width, height)
                        lineTo(0f, height)
                        close()
                    }
                    drawPath(
                        path = fillPath,
                        brush = Brush.verticalGradient(
                            colors = listOf(AccentPrimary.copy(alpha = 0.25f), Color.Transparent)
                        )
                    )

                    // 4. Draw the actual curved line
                    drawPath(
                        path = path,
                        color = AccentPrimary,
                        style = Stroke(width = 3.dp.toPx())
                    )

                    // 5. Draw point dots
                    points.forEach { pt ->
                        drawCircle(
                            color = Color.White,
                            radius = 4.dp.toPx(),
                            center = pt
                        )
                        drawCircle(
                            color = AccentPrimary,
                            radius = 2.dp.toPx(),
                            center = pt
                        )
                    }
                }
                
                // Render Dates below the chart
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {
                    val firstDate = dailyTrend.first().date.substringAfter("-")
                    val lastDate = dailyTrend.last().date.substringAfter("-")
                    Text(text = firstDate, color = Color.Gray, fontSize = 10.sp)
                    Text(text = "Süreç Akışı", color = Color.Gray, fontSize = 10.sp, fontWeight = FontWeight.Bold)
                    Text(text = lastDate, color = Color.Gray, fontSize = 10.sp)
                }
            }
        }
    }
}

@Composable
fun CrisisTrendIndicator(crisisCount: Int) {
    val (statusTitle, statusDesc, color) = if (crisisCount == 0) {
        Triple(
            "Denge Seviyesi: Dengeli & Huzurlu",
            "Son görüşmelerinizde hiçbir kritik stres veya yoğun huzursuzluk belirtisi kaydedilmedi. Zihinsel dengeniz oldukça stabil seviyede.",
            Color(0xFF86EFAC)
        )
    } else {
        Triple(
            "Denge Seviyesi: Öncelikli Gözlem",
            "Son günlerde hassasiyet oranınız yükselmiş görünüyor. Zihninizin sakinleşmesine fırsat verin ve kendinize özen göstermeyi ihmal etmeyin.",
            Color(0xFFFCA5A5)
        )
    }

    Card(
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(containerColor = DarkSurface),
        modifier = Modifier.fillMaxWidth()
    ) {
        Row(
            modifier = Modifier.padding(16.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Box(
                modifier = Modifier
                    .size(44.dp)
                    .background(color.copy(alpha = 0.15f), shape = RoundedCornerShape(12.dp)),
                contentAlignment = Alignment.Center
            ) {
                Icon(
                    imageVector = Icons.Default.Warning,
                    contentDescription = "Denge",
                    tint = color,
                    modifier = Modifier.size(24.dp)
                )
            }
            Spacer(modifier = Modifier.width(16.dp))
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = statusTitle,
                    color = color,
                    fontSize = 14.sp,
                    fontWeight = FontWeight.Bold
                )
                Spacer(modifier = Modifier.height(4.dp))
                Text(
                    text = statusDesc,
                    color = Color.LightGray,
                    fontSize = 12.sp,
                    lineHeight = 16.sp
                )
            }
        }
    }
}

@Composable
fun BehavioralInsightCard(insight: BehavioralInsight) {
    val (severityColor, tagLabel) = when (insight.severity.lowercase()) {
        "high" -> Color(0xFFFCA5A5) to "Öncelikli Gözlem"
        "medium" -> Color(0xFFFCD34D) to "Odaklanma Alanı"
        else -> Color(0xFF86EFAC) to "Olumlu Gelişim"
    }

    Card(
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(containerColor = DarkSurface),
        border = BorderStroke(1.dp, severityColor.copy(alpha = 0.25f)),
        modifier = Modifier.fillMaxWidth()
    ) {
        Column(
            modifier = Modifier.padding(16.dp)
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Surface(
                    color = severityColor.copy(alpha = 0.15f),
                    shape = RoundedCornerShape(8.dp),
                    border = BorderStroke(0.5.dp, severityColor.copy(alpha = 0.4f))
                ) {
                    Text(
                        text = tagLabel,
                        color = severityColor,
                        fontSize = 11.sp,
                        fontWeight = FontWeight.Bold,
                        modifier = Modifier.padding(horizontal = 10.dp, vertical = 4.dp)
                    )
                }

                val confidencePct = (insight.confidence * 100).toInt()
                Text(
                    text = "%$confidencePct Tutarlılık",
                    color = Color.LightGray,
                    fontSize = 11.sp,
                    fontWeight = FontWeight.Medium
                )
            }

            Spacer(modifier = Modifier.height(10.dp))

            Text(
                text = insight.title,
                color = Color.White,
                fontSize = 16.sp,
                fontWeight = FontWeight.Bold
            )

            Spacer(modifier = Modifier.height(6.dp))

            Text(
                text = insight.description,
                color = Color.LightGray,
                fontSize = 13.sp,
                lineHeight = 18.sp
            )

            Spacer(modifier = Modifier.height(12.dp))

            val displayDate = try {
                insight.created_at.substringBefore("T")
            } catch (e: Exception) {
                insight.created_at
            }
            
            Text(
                text = "Analiz Tarihi: $displayDate",
                color = Color.Gray,
                fontSize = 10.sp,
                textAlign = TextAlign.End,
                modifier = Modifier.fillMaxWidth()
            )
        }
    }
}

@Composable
fun EmptyStateView() {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(24.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center
    ) {
        Icon(
            imageVector = Icons.Default.TrendingUp,
            contentDescription = "Veri Aranıyor",
            tint = AccentPrimary.copy(alpha = 0.6f),
            modifier = Modifier.size(64.dp)
        )
        Spacer(modifier = Modifier.height(16.dp))
        Text(
            text = "Yolculuk Başlıyor...",
            color = Color.White,
            fontWeight = FontWeight.Bold,
            fontSize = 18.sp
        )
        Spacer(modifier = Modifier.height(8.dp))
        Text(
            text = "Henüz yeterli veri oluşmadı. Sohbet ettikçe duygu durum örüntüleriniz analiz edilecek ve grafikleriniz burada görünecek.",
            color = Color.Gray,
            fontSize = 14.sp,
            textAlign = TextAlign.Center,
            lineHeight = 20.sp
        )
    }
}

@Composable
fun ErrorStateView(message: String, onRetry: () -> Unit) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(24.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center
    ) {
        Text(
            text = "Bir Hata Oluştu",
            color = DangerRed,
            fontWeight = FontWeight.Bold,
            fontSize = 16.sp
        )
        Spacer(modifier = Modifier.height(8.dp))
        Text(
            text = message,
            color = Color.LightGray,
            fontSize = 14.sp,
            textAlign = TextAlign.Center
        )
        Spacer(modifier = Modifier.height(16.dp))
        Button(
            onClick = onRetry,
            colors = ButtonDefaults.buttonColors(containerColor = AccentPrimary)
        ) {
            Text("Tekrar Dene", color = Color.White)
        }
    }
}
