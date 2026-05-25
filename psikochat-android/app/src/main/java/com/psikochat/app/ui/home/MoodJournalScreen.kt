package com.psikochat.app.ui.home

import android.widget.Toast
import androidx.compose.animation.*
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Info
import androidx.compose.material.icons.filled.KeyboardArrowLeft
import androidx.compose.material.icons.filled.Warning
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
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavController
import com.psikochat.app.data.api.RetrofitClient
import com.psikochat.app.data.local.TokenManager
import com.psikochat.app.data.model.Resource
import com.psikochat.app.data.model.MoodJournalEntry
import com.psikochat.app.data.repository.MoodJournalRepository
import com.psikochat.app.ui.theme.*

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MoodJournalScreen(navController: NavController, tokenManager: TokenManager) {
    val context = LocalContext.current
    val api = RetrofitClient.create(tokenManager)
    val db = com.psikochat.app.data.local.AppDatabase.getInstance(context)
    val syncManager = com.psikochat.app.data.sync.SyncManager.getInstance(context)
    val repository = MoodJournalRepository(api, db.moodJournalDao())
    val factory = object : ViewModelProvider.Factory {
        override fun <T : ViewModel> create(modelClass: Class<T>): T {
            return MoodJournalViewModel(repository, tokenManager, syncManager) as T
        }
    }
    val viewModel: MoodJournalViewModel = viewModel(factory = factory)

    val journalListState by viewModel.journalListState.collectAsState()
    val creationState by viewModel.creationState.collectAsState()

    var selectedMood by remember { mutableStateOf("neutral") }
    var intensity by remember { mutableStateOf(3f) }
    var note by remember { mutableStateOf("") }

    val moodMap = listOf(
        Pair("happy", "😊 Mutlu"),
        Pair("calm", "😌 Sakin"),
        Pair("neutral", "😐 Nötr"),
        Pair("anxious", "😰 Kaygılı"),
        Pair("sad", "😢 Üzüntü"),
        Pair("angry", "😠 Öfkeli"),
        Pair("tired", "😴 Yorgun")
    )

    // Handle creation success
    LaunchedEffect(creationState) {
        when (val state = creationState) {
            is Resource.Success -> {
                Toast.makeText(context, "Mood günlüğünüz başarıyla kaydedildi.", Toast.LENGTH_SHORT).show()
                note = ""
                intensity = 3f
                selectedMood = "neutral"
                viewModel.clearCreationState()
            }
            is Resource.Error -> {
                // If warning mask is detected inside note, the backend will return successfully but masked
                // If there's a network/HTTP error, show it
                Toast.makeText(context, state.message ?: "Kayıt sırasında hata oluştu", Toast.LENGTH_LONG).show()
                viewModel.clearCreationState()
            }
            else -> {}
        }
    }

    Scaffold(
        topBar = {
            CenterAlignedTopAppBar(
                title = {
                    Text(
                        "Duygu Günlüğüm",
                        style = MaterialTheme.typography.titleMedium,
                        color = LoginTextColor,
                        fontWeight = FontWeight.Bold
                    )
                },
                navigationIcon = {
                    IconButton(onClick = { navController.popBackStack() }) {
                        Icon(Icons.Default.KeyboardArrowLeft, contentDescription = "Geri", tint = LoginTextColor)
                    }
                },
                colors = TopAppBarDefaults.centerAlignedTopAppBarColors(containerColor = Color.Transparent)
            )
        },
        containerColor = LoginBackground
    ) { padding ->
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(horizontal = 24.dp),
            verticalArrangement = Arrangement.spacedBy(20.dp),
            contentPadding = PaddingValues(bottom = 32.dp)
        ) {
            // 1. Logger Form Card
            item {
                Surface(
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(28.dp),
                    color = Color.White.copy(alpha = 0.9f),
                    shadowElevation = 1.dp
                ) {
                    Column(modifier = Modifier.padding(24.dp)) {
                        Text(
                            "Şu an nasıl hissediyorsun?",
                            fontSize = 15.sp,
                            fontWeight = FontWeight.Bold,
                            color = LoginTextColor
                        )
                        Spacer(modifier = Modifier.height(16.dp))

                        // Mood Badges Flow/Scroll
                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(vertical = 4.dp),
                            horizontalArrangement = Arrangement.spacedBy(8.dp)
                        ) {
                            // Split into two rows or show horizontally scrollable.
                            // We can use a simple flow style row by mapping first 4 and last 3.
                        }
                        
                        // First line of moods
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween
                        ) {
                            moodMap.take(4).forEach { (key, display) ->
                                MoodBadge(
                                    display = display,
                                    selected = selectedMood == key,
                                    onClick = { selectedMood = key }
                                )
                            }
                        }
                        Spacer(modifier = Modifier.height(10.dp))
                        // Second line of moods
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.spacedBy(8.dp)
                        ) {
                            moodMap.drop(4).forEach { (key, display) ->
                                MoodBadge(
                                    display = display,
                                    selected = selectedMood == key,
                                    onClick = { selectedMood = key }
                                )
                            }
                        }

                        Spacer(modifier = Modifier.height(24.dp))

                        // Intensity Selector
                        Text(
                            "Bu duygunun yoğunluğu: ${intensity.toInt()}/5",
                            fontSize = 13.sp,
                            fontWeight = FontWeight.Bold,
                            color = LoginTextColor
                        )
                        Spacer(modifier = Modifier.height(8.dp))
                        Slider(
                            value = intensity,
                            onValueChange = { intensity = it },
                            valueRange = 1f..5f,
                            steps = 3,
                            colors = SliderDefaults.colors(
                                thumbColor = LoginButton,
                                activeTrackColor = LoginButton,
                                inactiveTrackColor = Color.LightGray.copy(alpha = 0.5f)
                            )
                        )

                        Spacer(modifier = Modifier.height(20.dp))

                        // Optional Note Input
                        OutlinedTextField(
                            value = note,
                            onValueChange = { if (it.length <= 500) note = it },
                            label = { Text("Kısa Düşünce veya Notlar (Opsiyonel)", fontSize = 12.sp) },
                            modifier = Modifier.fillMaxWidth().height(100.dp),
                            shape = RoundedCornerShape(16.dp),
                            colors = OutlinedTextFieldDefaults.colors(
                                focusedBorderColor = LoginButton,
                                unfocusedBorderColor = Color.LightGray.copy(alpha = 0.5f)
                            )
                        )
                        Spacer(modifier = Modifier.height(4.dp))
                        Text(
                            text = "${note.length}/500 karakter",
                            fontSize = 10.sp,
                            color = LoginSecondaryText,
                            modifier = Modifier.align(Alignment.End)
                        )

                        Spacer(modifier = Modifier.height(20.dp))

                        // Submit Button
                        Button(
                            onClick = {
                                viewModel.createJournal(
                                    mood = selectedMood,
                                    intensity = intensity.toInt(),
                                    note = if (note.isBlank()) null else note
                                )
                            },
                            modifier = Modifier
                                .fillMaxWidth()
                                .height(48.dp),
                            shape = RoundedCornerShape(24.dp),
                            colors = ButtonDefaults.buttonColors(containerColor = LoginButton),
                            enabled = creationState !is Resource.Loading
                        ) {
                            if (creationState is Resource.Loading) {
                                CircularProgressIndicator(color = Color.White, modifier = Modifier.size(20.dp))
                            } else {
                                Text("Günlüğü Kaydet", fontWeight = FontWeight.Bold, color = Color.White)
                            }
                        }
                    }
                }
            }

            // 2. History Header
            item {
                Text(
                    "Geçmiş Kayıtlarım",
                    fontSize = 15.sp,
                    fontWeight = FontWeight.Bold,
                    color = LoginTextColor,
                    modifier = Modifier.padding(start = 8.dp, top = 8.dp)
                )
            }

            // 3. History Logs List
            when (val state = journalListState) {
                is Resource.Loading -> {
                    item {
                        Box(
                            modifier = Modifier.fillMaxWidth().height(200.dp),
                            contentAlignment = Alignment.Center
                        ) {
                            CircularProgressIndicator(color = LoginButton)
                        }
                    }
                }
                is Resource.Error -> {
                    item {
                        Column(
                            modifier = Modifier.fillMaxWidth().padding(24.dp),
                            horizontalAlignment = Alignment.CenterHorizontally
                        ) {
                            Icon(Icons.Default.Warning, contentDescription = null, tint = DangerRed, modifier = Modifier.size(32.dp))
                            Spacer(modifier = Modifier.height(12.dp))
                            Text(state.message ?: "Kayıtlar yüklenemedi.", color = LoginTextColor)
                        }
                    }
                }
                is Resource.Success -> {
                    val entries = state.data ?: emptyList()
                    if (entries.isEmpty()) {
                        item {
                            Surface(
                                modifier = Modifier.fillMaxWidth(),
                                shape = RoundedCornerShape(20.dp),
                                color = Color.White.copy(alpha = 0.5f)
                            ) {
                                Text(
                                    "Henüz hiç duygu günlüğü kaydı oluşturmadınız.",
                                    textAlign = TextAlign.Center,
                                    fontSize = 13.sp,
                                    color = LoginSecondaryText,
                                    modifier = Modifier.padding(24.dp)
                                )
                            }
                        }
                    } else {
                        items(entries, key = { it.id }) { entry ->
                            JournalEntryItem(entry = entry, onDelete = { viewModel.deleteJournal(entry.id) })
                        }
                    }
                }
            }
        }
    }
}

@Composable
fun MoodBadge(display: String, selected: Boolean, onClick: () -> Unit) {
    Surface(
        modifier = Modifier
            .clip(RoundedCornerShape(16.dp))
            .clickable { onClick() },
        color = if (selected) LoginButton else Color.White,
        shape = RoundedCornerShape(16.dp)
    ) {
        Text(
            text = display,
            fontSize = 12.sp,
            fontWeight = FontWeight.Bold,
            color = if (selected) Color.White else LoginTextColor,
            modifier = Modifier.padding(horizontal = 12.dp, vertical = 8.dp)
        )
    }
}

@Composable
fun JournalEntryItem(entry: MoodJournalEntry, onDelete: () -> Unit) {
    val cardColor = when (entry.mood) {
        "happy" -> Color(0xFFF0FDF4) // Soft mint green
        "calm" -> Color(0xFFEFF6FF) // Soft serene blue
        "anxious" -> Color(0xFFEEF2FF) // Lavender
        "sad" -> Color(0xFFF9FAFB) // Grey
        "angry" -> Color(0xFFFEF2F2) // Soft pink
        "tired" -> Color(0xFFFFFBEB) // Sand
        else -> Color.White
    }
    
    val badgeText = when (entry.mood) {
        "happy" -> "😊 Mutlu"
        "calm" -> "😌 Sakin"
        "neutral" -> "😐 Nötr"
        "anxious" -> "😰 Kaygılı"
        "sad" -> "😢 Üzüntü"
        "angry" -> "😠 Öfkeli"
        "tired" -> "😴 Yorgun"
        else -> "😐 Nötr"
    }

    Surface(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(20.dp),
        color = cardColor,
        shadowElevation = 0.5.dp
    ) {
        Row(
            modifier = Modifier.padding(16.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Row(
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text(
                        badgeText,
                        fontSize = 13.sp,
                        fontWeight = FontWeight.Bold,
                        color = LoginTextColor
                    )
                    Spacer(modifier = Modifier.width(12.dp))
                    Surface(
                        color = Color.White.copy(alpha = 0.8f),
                        shape = RoundedCornerShape(8.dp)
                    ) {
                        Text(
                            "Yoğunluk: ${entry.intensity}/5",
                            fontSize = 10.sp,
                            fontWeight = FontWeight.Bold,
                            color = LoginSecondaryText,
                            modifier = Modifier.padding(horizontal = 8.dp, vertical = 2.dp)
                        )
                    }
                }
                
                if (!entry.note.isNullOrBlank()) {
                    Spacer(modifier = Modifier.height(8.dp))
                    Text(
                        entry.note,
                        fontSize = 12.sp,
                        lineHeight = 18.sp,
                        color = LoginTextColor.copy(alpha = 0.8f)
                    )
                }
                
                Spacer(modifier = Modifier.height(8.dp))
                val dateStr = try {
                    entry.createdAt.substring(0, 10) + " " + entry.createdAt.substring(11, 16)
                } catch (e: Exception) {
                    entry.createdAt
                }
                Text(
                    dateStr,
                    fontSize = 9.sp,
                    color = LoginSecondaryText.copy(alpha = 0.7f)
                )
            }
            
            IconButton(onClick = onDelete) {
                Icon(
                    Icons.Default.Delete,
                    contentDescription = "Sil",
                    tint = DangerRed.copy(alpha = 0.8f),
                    modifier = Modifier.size(20.dp)
                )
            }
        }
    }
}
