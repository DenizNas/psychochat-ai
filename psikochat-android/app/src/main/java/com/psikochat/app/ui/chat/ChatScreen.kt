package com.psikochat.app.ui.chat

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.core.*
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalSoftwareKeyboardController
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavController
import com.psikochat.app.data.api.RetrofitClient
import com.psikochat.app.data.local.TokenManager
import com.psikochat.app.data.model.HistoryItem
import com.psikochat.app.data.realtime.ConnectionState
import com.psikochat.app.data.realtime.RealtimeWebSocketManager
import com.psikochat.app.data.repository.ChatRepository
import com.psikochat.app.ui.theme.*
import kotlinx.coroutines.launch
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ChatScreen(navController: NavController, tokenManager: TokenManager) {
    val context = androidx.compose.ui.platform.LocalContext.current
    val db = com.psikochat.app.data.local.AppDatabase.getInstance(context)
    val syncManager = com.psikochat.app.data.sync.SyncManager.getInstance(context)
    val api = RetrofitClient.create(tokenManager)
    val repo = ChatRepository(api, db.chatDao())
    val factory = object : ViewModelProvider.Factory {
        override fun <T : ViewModel> create(modelClass: Class<T>): T {
            val wsManager = RealtimeWebSocketManager(
                tokenManager = tokenManager,
                scope = androidx.lifecycle.ViewModelProvider
                    .NewInstanceFactory()
                    .create(androidx.lifecycle.ViewModel::class.java)
                    .let { kotlinx.coroutines.MainScope() },
            )
            @Suppress("UNCHECKED_CAST")
            return ChatViewModel(repo, wsManager, tokenManager, syncManager) as T
        }
    }
    val viewModel: ChatViewModel = viewModel(factory = factory)

    val messages by viewModel.messages.collectAsState()
    val isLoading by viewModel.isLoading.collectAsState()
    val error by viewModel.error.collectAsState()
    val lastFailedMessage by viewModel.lastFailedMessage.collectAsState()
    val isAssistantTyping by viewModel.isAssistantTyping.collectAsState()
    val connectionState by viewModel.connectionState.collectAsState()
    
    val currentToken by tokenManager.getToken().collectAsState(initial = "loading")

    val listState = rememberLazyListState()
    var previousMessagesSize by remember { mutableIntStateOf(0) }

    LaunchedEffect(currentToken) {
        if (currentToken == null) {
            navController.navigate("auth_graph") {
                popUpTo("main_graph") { inclusive = true }
                launchSingleTop = true
            }
        }
    }

    LaunchedEffect(messages.size, isLoading) {
        val totalItems = listState.layoutInfo.totalItemsCount
        val isUserMessageAdded = messages.size > previousMessagesSize && messages.lastOrNull()?.role == "user"
        
        if (totalItems > 0) {
            val lastVisibleItemIndex = listState.layoutInfo.visibleItemsInfo.lastOrNull()?.index ?: 0
            val isAtBottom = lastVisibleItemIndex >= totalItems - 3

            if (isUserMessageAdded || isAtBottom) {
                listState.animateScrollToItem(totalItems - 1)
            }
        }
        previousMessagesSize = messages.size
    }

    LaunchedEffect(Unit) {
        viewModel.loadHistory()
    }

    Scaffold(
        topBar = {
            Column {
                CenterAlignedTopAppBar(
                    title = {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Icon(
                                imageVector = Icons.Default.Settings,
                                contentDescription = null,
                                modifier = Modifier.size(24.dp),
                                tint = LoginTextColor
                            )
                            Spacer(modifier = Modifier.width(8.dp))
                            Text("PsikoChat", style = MaterialTheme.typography.titleMedium, color = LoginTextColor)
                        }
                    },
                    navigationIcon = {
                        IconButton(onClick = { navController.popBackStack() }) {
                            Icon(Icons.Default.KeyboardArrowLeft, contentDescription = "Geri", tint = LoginTextColor)
                        }
                    },
                    actions = {
                        IconButton(onClick = { }) {
                            Icon(Icons.Default.Menu, contentDescription = "Menü", tint = LoginTextColor)
                        }
                    },
                    colors = TopAppBarDefaults.centerAlignedTopAppBarColors(containerColor = Color.Transparent)
                )
                // ─── Connection Status Banner ───────────────────────────────────
                ConnectionBanner(state = connectionState)
            }
        },
        bottomBar = {
            ChatInputBar(
                isLoading = isLoading,
                onSendMessage = { text ->
                    viewModel.sendMessage(text)
                },
                onTextChanged = {
                    viewModel.onUserTyping()
                }
            )
        },
        containerColor = LoginBackground
    ) { padding ->
        Column(modifier = Modifier.padding(padding).fillMaxSize()) {
            Text(
                text = "PsikoChat Sohbet",
                style = MaterialTheme.typography.headlineSmall.copy(fontWeight = FontWeight.Bold),
                color = LoginTextColor,
                modifier = Modifier.padding(horizontal = 24.dp, vertical = 16.dp)
            )

            if (error != null) {
                Surface(
                    color = Color(0xFFFFEBEE),
                    shape = RoundedCornerShape(8.dp),
                    modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 8.dp)
                ) {
                    Row(
                        modifier = Modifier.padding(12.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text(
                            text = error!!, 
                            color = Color(0xFFC62828), 
                            modifier = Modifier.weight(1f),
                            style = MaterialTheme.typography.bodyMedium
                        )
                        if (lastFailedMessage != null) {
                            IconButton(onClick = { viewModel.retryLastMessage() }, modifier = Modifier.size(24.dp)) {
                                Icon(Icons.Default.Refresh, contentDescription = "Tekrar Dene", tint = Color(0xFFC62828))
                            }
                            Spacer(modifier = Modifier.width(8.dp))
                        }
                        IconButton(onClick = { viewModel.clearError() }, modifier = Modifier.size(24.dp)) {
                            Icon(Icons.Default.Close, contentDescription = "Kapat", tint = Color(0xFFC62828))
                        }
                    }
                }
            }

            val groupedMessages = messages.groupBy { extractDateString(it.timestamp) }

            LazyColumn(
                state = listState,
                modifier = Modifier.weight(1f).fillMaxWidth(),
                contentPadding = PaddingValues(16.dp),
                reverseLayout = false
            ) {
                if (messages.isEmpty() && !isLoading) {
                    item {
                        EmptyChatState(modifier = Modifier.fillParentMaxSize())
                    }
                } else {
                    item {
                        SystemNoteBubble("PsikoChat'e hoş geldiniz! Lütfen nasıl hissettiğinizi paylaşın.")
                        Spacer(modifier = Modifier.height(16.dp))
                    }

                    groupedMessages.forEach { (date, msgs) ->
                        item {
                            Box(modifier = Modifier.fillMaxWidth(), contentAlignment = Alignment.Center) {
                                Surface(
                                    color = Color(0xFFE0E0E0),
                                    shape = RoundedCornerShape(12.dp),
                                    modifier = Modifier.padding(vertical = 8.dp)
                                ) {
                                    Text(
                                        text = date,
                                        fontSize = 12.sp,
                                        color = Color.DarkGray,
                                        modifier = Modifier.padding(horizontal = 12.dp, vertical = 4.dp),
                                        fontWeight = FontWeight.SemiBold
                                    )
                                }
                            }
                        }

                        items(msgs, key = { it.id ?: (it.role + "_" + it.text.hashCode() + "_" + it.timestamp.hashCode()) }) { msg ->
                            MessageBubble(msg)
                            Spacer(modifier = Modifier.height(12.dp))
                        }
                    }
                }

                if (isLoading) {
                    item {
                        TypingIndicator()
                        Spacer(modifier = Modifier.height(12.dp))
                    }
                } else if (isAssistantTyping) {
                    item {
                        TypingIndicator()
                        Spacer(modifier = Modifier.height(12.dp))
                    }
                }
            }
        }
    }
}

// ... (Import kısımları aynı kalabilir, FontWeight zaten ekli)

@Composable
fun MessageBubble(msg: HistoryItem) {
    val isUser = msg.role == "user"
    val align = if (isUser) Alignment.CenterEnd else Alignment.CenterStart
    val bgColor = if (isUser) LoginButton else Color.White
    val textColor = if (isUser) Color.White else LoginTextColor
    val timeColor = if (isUser) Color.White.copy(alpha = 0.8f) else Color.Gray

    val shape = if (isUser)
        RoundedCornerShape(topStart = 16.dp, topEnd = 16.dp, bottomStart = 16.dp, bottomEnd = 4.dp)
    else
        RoundedCornerShape(topStart = 16.dp, topEnd = 16.dp, bottomStart = 4.dp, bottomEnd = 16.dp)

    Box(contentAlignment = align, modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp)) {
        Row(
            verticalAlignment = Alignment.Bottom,
            horizontalArrangement = if (isUser) Arrangement.End else Arrangement.Start,
            modifier = Modifier.fillMaxWidth()
        ) {
            Surface(
                color = bgColor,
                shape = shape,
                modifier = Modifier.widthIn(max = 280.dp),
                shadowElevation = 2.dp
            ) {
                Column(modifier = Modifier.padding(horizontal = 14.dp, vertical = 10.dp)) {
                    Text(
                        text = msg.text,
                        color = textColor,
                        fontSize = 15.sp,
                        fontWeight = FontWeight.Normal,
                        lineHeight = 22.sp
                    )
                    Spacer(modifier = Modifier.height(4.dp))
                    Text(
                        text = formatMessageTime(msg.timestamp),
                        color = timeColor,
                        fontSize = 10.sp,
                        modifier = Modifier.align(Alignment.End)
                    )
                }
            }
        }
    }
}

@Composable
fun TypingIndicator() {
    val infiniteTransition = rememberInfiniteTransition(label = "typing")
    val dot1 = infiniteTransition.animateFloat(
        initialValue = 0f, targetValue = 1f,
        animationSpec = infiniteRepeatable(
            animation = tween(600, easing = LinearEasing),
            repeatMode = RepeatMode.Reverse
        ), label = "dot1"
    )
    val dot2 = infiniteTransition.animateFloat(
        initialValue = 0f, targetValue = 1f,
        animationSpec = infiniteRepeatable(
            animation = tween(600, delayMillis = 200, easing = LinearEasing),
            repeatMode = RepeatMode.Reverse
        ), label = "dot2"
    )
    val dot3 = infiniteTransition.animateFloat(
        initialValue = 0f, targetValue = 1f,
        animationSpec = infiniteRepeatable(
            animation = tween(600, delayMillis = 400, easing = LinearEasing),
            repeatMode = RepeatMode.Reverse
        ), label = "dot3"
    )

    Box(contentAlignment = Alignment.CenterStart, modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp)) {
        Surface(
            color = Color.White,
            shape = RoundedCornerShape(topStart = 16.dp, topEnd = 16.dp, bottomStart = 4.dp, bottomEnd = 16.dp),
            modifier = Modifier.widthIn(min = 60.dp),
            shadowElevation = 2.dp
        ) {
            Row(
                modifier = Modifier.padding(horizontal = 16.dp, vertical = 14.dp),
                horizontalArrangement = Arrangement.spacedBy(4.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Dot(alpha = dot1.value)
                Dot(alpha = dot2.value)
                Dot(alpha = dot3.value)
            }
        }
    }
}

@Composable
private fun Dot(alpha: Float) {
    Box(
        modifier = Modifier
            .size(6.dp)
            .clip(CircleShape)
            .background(Color.Gray.copy(alpha = 0.3f + (alpha * 0.7f)))
    )
}

@Composable
fun ChatInputBar(isLoading: Boolean, onSendMessage: (String) -> Unit, onTextChanged: () -> Unit = {}) {
    var inputText by remember { mutableStateOf("") }
    val focusRequester = remember { FocusRequester() }

    Surface(
        color = Color.White,
        modifier = Modifier.fillMaxWidth(),
        shadowElevation = 8.dp
    ) {
        Row(
            modifier = Modifier.padding(12.dp).navigationBarsPadding().imePadding(),
            verticalAlignment = Alignment.CenterVertically
        ) {
            OutlinedTextField(
                value = inputText,
                onValueChange = { 
                    if (it.length <= 1000) {
                        inputText = it
                        onTextChanged() // typing indicator
                    }
                },
                modifier = Modifier
                    .weight(1f)
                    .focusRequester(focusRequester)
                    .background(Color(0xFFF5F5F5), RoundedCornerShape(24.dp)),
                enabled = !isLoading,
                placeholder = { Text("Mesajınızı yazın...", fontSize = 14.sp) },
                shape = RoundedCornerShape(24.dp),
                colors = OutlinedTextFieldDefaults.colors(
                    focusedBorderColor = LoginButton,
                    unfocusedBorderColor = Color.LightGray
                ),
                keyboardOptions = KeyboardOptions(imeAction = ImeAction.Send),
                keyboardActions = KeyboardActions(
                    onSend = {
                        if (inputText.isNotBlank() && !isLoading) {
                            onSendMessage(inputText)
                            inputText = ""
                        }
                    }
                ),
                trailingIcon = {
                    Icon(Icons.Default.Add, contentDescription = null, tint = Color.Gray)
                }
            )
            Spacer(modifier = Modifier.width(8.dp))
            IconButton(
                onClick = {
                    if (inputText.isNotBlank() && !isLoading) {
                        onSendMessage(inputText)
                        inputText = ""
                    }
                },
                enabled = !isLoading,
                colors = IconButtonDefaults.iconButtonColors(
                    containerColor = LoginButton,
                    disabledContainerColor = Color.Gray
                )
            ) {
                Icon(Icons.AutoMirrored.Filled.Send, contentDescription = "Gönder", tint = Color.White)
            }
        }
    }
}

@Composable
fun EmptyChatState(modifier: Modifier = Modifier) {
    Box(
        modifier = modifier,
        contentAlignment = Alignment.Center
    ) {
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Icon(
                imageVector = Icons.Default.Email,
                contentDescription = null,
                modifier = Modifier.size(64.dp),
                tint = LoginButton.copy(alpha = 0.5f)
            )
            Spacer(modifier = Modifier.height(16.dp))
            Text(
                text = "Henüz bir sohbet başlatmadınız.",
                color = Color.Gray,
                fontSize = 16.sp,
                fontWeight = FontWeight.Medium,
                textAlign = TextAlign.Center
            )
            Spacer(modifier = Modifier.height(8.dp))
            Text(
                text = "Nasıl hissettiğinizi paylaşarak başlayabilirsiniz.",
                color = Color.Gray.copy(alpha = 0.8f),
                fontSize = 14.sp,
                textAlign = TextAlign.Center
            )
        }
    }
}
@Composable
fun SystemNoteBubble(text: String) {
    Column(modifier = Modifier.fillMaxWidth().padding(horizontal = 8.dp)) {
        Text(
            "System Note",
            fontSize = 11.sp,
            color = Color(0xFF001F3F), // Başlık Lacivert
            fontWeight = FontWeight.ExtraBold,
            modifier = Modifier.padding(start = 4.dp)
        )
        Spacer(modifier = Modifier.height(4.dp))
        Surface(
            color = Color.White,
            shape = RoundedCornerShape(0.dp, 16.dp, 16.dp, 16.dp),
            modifier = Modifier.widthIn(max = 300.dp),
            shadowElevation = 1.dp
        ) {
            Text(
                text = text,
                // DEĞİŞİKLİK: İçerik metni Lacivert yapıldı
                color = Color(0xFF001F3F),
                modifier = Modifier.padding(12.dp),
                fontSize = 14.sp,
                fontWeight = FontWeight.Bold
            )
        }
    }
}

fun formatMessageTime(timestamp: String?): String {
    if (timestamp == null) return "Şimdi"
    return try {
        val parser = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss", Locale.getDefault())
        val date = parser.parse(timestamp)
        val formatter = SimpleDateFormat("HH:mm", Locale.getDefault())
        date?.let { formatter.format(it) } ?: ""
    } catch (e: Exception) {
        ""
    }
}

fun extractDateString(timestamp: String?): String {
    if (timestamp == null) return "Bugün"
    return try {
        val parser = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss", Locale.getDefault())
        val date = parser.parse(timestamp)
        val formatter = SimpleDateFormat("dd MMMM yyyy", Locale("tr", "TR"))
        val dateString = date?.let { formatter.format(it) } ?: "Bilinmeyen Tarih"
        
        val todayString = formatter.format(Date())
        if (dateString == todayString) "Bugün" else dateString
    } catch (e: Exception) {
        "Bilinmeyen Tarih"
    }
}

/**
 * WebSocket bağlantı durumu banner'ı.
 * - Connected / Connecting → görünmez
 * - Reconnecting → amber uyarı
 * - Failed → kırmızı, "REST ile devam ediliyor"
 * - Disconnected → görünmez (çıkış yapıldı)
 */
@Composable
fun ConnectionBanner(state: ConnectionState) {
    AnimatedVisibility(
        visible = state is ConnectionState.Reconnecting || state is ConnectionState.Failed
    ) {
        val (bgColor, icon, text) = when (state) {
            is ConnectionState.Reconnecting -> Triple(
                Color(0xFFFFF3E0),
                Icons.Default.Refresh,
                "Bağlantı yenileniyor... (${state.attempt}. deneme)"
            )
            is ConnectionState.Failed -> Triple(
                Color(0xFFFFEBEE),
                Icons.Default.Warning,
                "Çevrimdışı — Mesajlar REST üzerinden iletilecek"
            )
            else -> Triple(Color.Transparent, Icons.Default.CheckCircle, "")
        }

        Surface(
            color = bgColor,
            modifier = Modifier.fillMaxWidth()
        ) {
            Row(
                modifier = Modifier.padding(horizontal = 16.dp, vertical = 6.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.Center
            ) {
                Icon(
                    imageVector = icon,
                    contentDescription = null,
                    modifier = Modifier.size(14.dp),
                    tint = if (state is ConnectionState.Failed) Color(0xFFC62828) else Color(0xFFE65100)
                )
                Spacer(modifier = Modifier.width(6.dp))
                Text(
                    text = text,
                    fontSize = 11.sp,
                    color = if (state is ConnectionState.Failed) Color(0xFFC62828) else Color(0xFFE65100),
                    fontWeight = FontWeight.Medium
                )
            }
        }
    }
}