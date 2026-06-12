package com.psikochat.app.ui.chat

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.*
import androidx.compose.material.icons.filled.Email
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavController
import com.psikochat.app.data.api.RetrofitClient
import com.psikochat.app.data.local.TokenManager
import com.psikochat.app.data.model.HistoryItem
import com.psikochat.app.data.repository.ChatRepository
import com.psikochat.app.ui.theme.*
import com.psikochat.app.ui.components.*
import java.net.URLEncoder
import java.nio.charset.StandardCharsets
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch
import com.psikochat.app.data.model.Resource

class ChatHistoryViewModel(
    private val repository: ChatRepository,
    private val tokenManager: TokenManager,
    private val syncManager: com.psikochat.app.data.sync.SyncManager
) : ViewModel() {

    private val _messages = MutableStateFlow<List<HistoryItem>>(emptyList())
    val messages: StateFlow<List<HistoryItem>> = _messages

    private val _isLoading = MutableStateFlow(false)
    val isLoading: StateFlow<Boolean> = _isLoading

    private val _error = MutableStateFlow<String?>(null)
    val error: StateFlow<String?> = _error

    fun loadHistory() {
        viewModelScope.launch {
            _isLoading.value = true
            val username = tokenManager.getUsername().first()
            
            // 1. Observe Room local database cache reactively (always responds instantly!)
            repository.getCachedHistory(username)
                .onEach { list ->
                    _messages.value = list
                }
                .launchIn(viewModelScope)
            
            // 2. Perform background network refresh to update local Room cache if online
            if (syncManager.isOnline.value) {
                when (val res = repository.refreshHistory(username)) {
                    is Resource.Error -> {
                        _error.value = res.message
                    }
                    else -> {}
                }
            }
            _isLoading.value = false
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ChatHistoryScreen(navController: NavController, tokenManager: TokenManager) {
    val context = androidx.compose.ui.platform.LocalContext.current
    val db = com.psikochat.app.data.local.AppDatabase.getInstance(context)
    val api = RetrofitClient.create(tokenManager)
    val repo = ChatRepository(api, db.chatDao())
    val factory = object : ViewModelProvider.Factory {
        @Suppress("UNCHECKED_CAST")
        override fun <T : ViewModel> create(modelClass: Class<T>): T {
            val syncManager = com.psikochat.app.data.sync.SyncManager.getInstance(context)
            return ChatHistoryViewModel(repo, tokenManager, syncManager) as T
        }
    }
    val viewModel: ChatHistoryViewModel = viewModel(factory = factory)
    val messages by viewModel.messages.collectAsState()
    val isLoading by viewModel.isLoading.collectAsState()

    LaunchedEffect(Unit) {
        viewModel.loadHistory()
    }

    Scaffold(
        topBar = {
            CenterAlignedTopAppBar(
                title = {
                    Text(
                        "Sohbet Geçmişim",
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Bold,
                        color = LoginTextColor
                    )
                },
                navigationIcon = {
                    IconButton(onClick = { navController.popBackStack() }) {
                        Icon(Icons.AutoMirrored.Filled.KeyboardArrowLeft, contentDescription = "Geri", tint = LoginTextColor)
                    }
                },
                colors = TopAppBarDefaults.centerAlignedTopAppBarColors(containerColor = Color.Transparent)
            )
        },
        containerColor = LoginBackground
    ) { padding ->
        Box(modifier = Modifier.fillMaxSize().padding(padding)) {
            if (isLoading && messages.isEmpty()) {
                CircularProgressIndicator(modifier = Modifier.align(Alignment.Center), color = DarkTealPrimary)
            } else if (messages.isEmpty()) {
                // Empty History state
                Column(
                    modifier = Modifier.align(Alignment.Center).padding(32.dp),
                    horizontalAlignment = Alignment.CenterHorizontally,
                    verticalArrangement = Arrangement.Center
                ) {
                    Surface(
                        modifier = Modifier.size(80.dp),
                        shape = CircleShape,
                        color = Color.White.copy(alpha = 0.5f)
                    ) {
                        Box(contentAlignment = Alignment.Center) {
                            Icon(Icons.Default.Email, contentDescription = null, tint = DarkTealPrimary, modifier = Modifier.size(40.dp))
                        }
                    }
                    Spacer(modifier = Modifier.height(24.dp))
                    Text(
                        "Henüz kayıtlı bir sohbet geçmişiniz bulunmuyor.",
                        textAlign = TextAlign.Center,
                        fontSize = 15.sp,
                        fontWeight = FontWeight.Medium,
                        color = LoginSecondaryText
                    )
                    Spacer(modifier = Modifier.height(8.dp))
                    Text(
                        "Duygusal durumunuzu paylaşmak ve dilediğiniz zaman sohbet etmek için yeni bir konuşma başlatabilirsiniz.",
                        textAlign = TextAlign.Center,
                        fontSize = 12.sp,
                        color = LoginSecondaryText.copy(alpha = 0.8f)
                    )
                    Spacer(modifier = Modifier.height(24.dp))
                    PremiumButton(
                        onClick = { navController.navigate("chat") },
                        cornerRadius = 16.dp,
                        height = 48.dp,
                        modifier = Modifier.fillMaxWidth(0.7f)
                    ) {
                        Text("Sohbet Başlat", color = Color.White)
                    }
                }
            } else {
                // Group by date
                val grouped = remember(messages) {
                    messages.groupBy { extractDateString(it.timestamp) }
                }
                LazyColumn(
                    modifier = Modifier.fillMaxSize().padding(horizontal = 24.dp),
                    verticalArrangement = Arrangement.spacedBy(16.dp),
                    contentPadding = PaddingValues(top = 16.dp, bottom = 24.dp)
                ) {
                    items(grouped.keys.toList()) { dateKey ->
                        val listForDate = grouped[dateKey] ?: emptyList()
                        val lastMsg = listForDate.lastOrNull()?.text ?: ""
                        val msgCount = listForDate.size

                        Surface(
                            modifier = Modifier
                                .fillMaxWidth()
                                .clickable {
                                    val encodedDate = URLEncoder.encode(dateKey, StandardCharsets.UTF_8.toString())
                                    navController.navigate("chat/$encodedDate")
                                },
                            shape = RoundedCornerShape(20.dp),
                            color = PremiumWhiteCard,
                            border = BorderStroke(1.dp, SoftMintAccent.copy(alpha = 0.5f)),
                            shadowElevation = 1.dp
                        ) {
                            Row(
                                modifier = Modifier.padding(16.dp),
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Box(
                                    modifier = Modifier
                                        .size(40.dp)
                                        .clip(CircleShape)
                                        .background(SoftMintAccent.copy(alpha = 0.4f)),
                                    contentAlignment = Alignment.Center
                                ) {
                                    Icon(
                                        imageVector = Icons.Default.Email,
                                        contentDescription = null,
                                        tint = DarkTealPrimary,
                                        modifier = Modifier.size(20.dp)
                                    )
                                }
                                Spacer(modifier = Modifier.width(16.dp))
                                Column(modifier = Modifier.weight(1f)) {
                                    Row(
                                        modifier = Modifier.fillMaxWidth(),
                                        horizontalArrangement = Arrangement.SpaceBetween,
                                        verticalAlignment = Alignment.CenterVertically
                                    ) {
                                        Text(
                                            text = dateKey,
                                            fontWeight = FontWeight.Bold,
                                            fontSize = 15.sp,
                                            color = LoginTextColor
                                        )
                                        Surface(
                                            shape = RoundedCornerShape(8.dp),
                                            color = SoftMintAccent
                                        ) {
                                            Text(
                                                text = "$msgCount Mesaj",
                                                fontSize = 10.sp,
                                                fontWeight = FontWeight.Bold,
                                                color = DarkTealPrimary,
                                                modifier = Modifier.padding(horizontal = 8.dp, vertical = 2.dp)
                                            )
                                        }
                                    }
                                    Spacer(modifier = Modifier.height(4.dp))
                                    Text(
                                        text = lastMsg,
                                        fontSize = 12.sp,
                                        color = LoginSecondaryText,
                                        maxLines = 1,
                                        overflow = TextOverflow.Ellipsis
                                    )
                                }
                                Spacer(modifier = Modifier.width(12.dp))
                                Icon(
                                    imageVector = Icons.AutoMirrored.Filled.KeyboardArrowRight,
                                    tint = SecondaryTealText,
                                    contentDescription = null,
                                    modifier = Modifier.size(20.dp)
                                )
                            }
                        }
                    }
                }
            }
        }
    }
}
