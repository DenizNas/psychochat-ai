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
import androidx.compose.material.icons.automirrored.filled.*
import androidx.compose.material.icons.filled.*
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.compose.ui.platform.LocalLifecycleOwner
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
import com.psikochat.app.data.model.Resource
import com.psikochat.app.data.realtime.ConnectionState
import com.psikochat.app.data.realtime.RealtimeWebSocketManager
import com.psikochat.app.data.repository.ChatRepository
import com.psikochat.app.ui.theme.*
import androidx.compose.foundation.Image
import androidx.compose.ui.res.painterResource
import kotlinx.coroutines.launch
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import android.content.Intent
import android.net.Uri
import android.widget.Toast
import androidx.compose.ui.platform.LocalContext

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ChatScreen(navController: NavController, tokenManager: TokenManager, conversationId: String? = null) {
    val context = androidx.compose.ui.platform.LocalContext.current
    val db = com.psikochat.app.data.local.AppDatabase.getInstance(context)
    val syncManager = com.psikochat.app.data.sync.SyncManager.getInstance(context)
    val api = RetrofitClient.create(tokenManager)
    val repo = ChatRepository(api, db.chatDao())
    val privacyRepo = com.psikochat.app.data.repository.PrivacyRepository(api)
    val factory = object : ViewModelProvider.Factory {
        override fun <T : ViewModel> create(modelClass: Class<T>): T {
            val wsManager = RealtimeWebSocketManager(
                tokenManager = tokenManager,
                scope = kotlinx.coroutines.MainScope(),
            )
            @Suppress("UNCHECKED_CAST")
            return ChatViewModel(repo, wsManager, tokenManager, syncManager, privacyRepo) as T
        }
    }
    val viewModel: ChatViewModel = viewModel(factory = factory)

    // Observe Consent State
    val aiConsentGranted by viewModel.aiConsentGranted.collectAsState()
    val isConsentOffline by viewModel.isConsentOffline.collectAsState()

    // Screen Resume Lifecycle Observer for auto-refreshing consent status
    val lifecycleOwner = LocalLifecycleOwner.current
    DisposableEffect(lifecycleOwner) {
        val observer = androidx.lifecycle.LifecycleEventObserver { _, event ->
            if (event == androidx.lifecycle.Lifecycle.Event.ON_RESUME) {
                viewModel.checkConsentAndConnect()
            }
        }
        lifecycleOwner.lifecycle.addObserver(observer)
        onDispose {
            lifecycleOwner.lifecycle.removeObserver(observer)
        }
    }

    // Profile ViewModel Integration for Personalized Welcome Greeting
    val profileRepo = com.psikochat.app.data.repository.ProfileRepository(api)
    val profileFactory = object : ViewModelProvider.Factory {
        @Suppress("UNCHECKED_CAST")
        override fun <T : ViewModel> create(modelClass: Class<T>): T {
            return com.psikochat.app.ui.home.ProfileViewModel(profileRepo, tokenManager) as T
        }
    }
    val profileViewModel: com.psikochat.app.ui.home.ProfileViewModel = viewModel(factory = profileFactory)
    val profileState by profileViewModel.profileState.collectAsState()

    val welcomeName = when (val state = profileState) {
        is Resource.Success -> state.data?.displayName ?: state.data?.username ?: "Kullanıcı"
        else -> "Kullanıcı"
    }

    val messages by viewModel.messages.collectAsState()
    val isLoading by viewModel.isLoading.collectAsState()
    val error by viewModel.error.collectAsState()
    val lastFailedMessage by viewModel.lastFailedMessage.collectAsState()
    val isAssistantTyping by viewModel.isAssistantTyping.collectAsState()
    val connectionState by viewModel.connectionState.collectAsState()
    val crisisAlert by viewModel.crisisAlert.collectAsState()
    val activeEmergencySupport by viewModel.activeEmergencySupport.collectAsState()
    
    val currentToken by tokenManager.getToken().collectAsState(initial = "loading")

    val listState = rememberLazyListState()
    var previousMessagesSize by remember { mutableIntStateOf(0) }
    var showNewChatConfirm by remember { mutableStateOf(false) }

    LaunchedEffect(currentToken) {
        if (currentToken == null) {
            navController.navigate("auth_graph") {
                popUpTo("main_graph") { inclusive = true }
                launchSingleTop = true
            }
        }
    }

    LaunchedEffect(messages.size, isLoading, activeEmergencySupport) {
        val totalItems = listState.layoutInfo.totalItemsCount
        val isUserMessageAdded = messages.size > previousMessagesSize && messages.lastOrNull()?.role == "user"
        
        if (totalItems > 0) {
            val lastVisibleItemIndex = listState.layoutInfo.visibleItemsInfo.lastOrNull()?.index ?: 0
            val isAtBottom = lastVisibleItemIndex >= totalItems - 3

            if (isUserMessageAdded || isAtBottom || activeEmergencySupport != null) {
                listState.animateScrollToItem(totalItems - 1)
            }
        }
        previousMessagesSize = messages.size
    }

    LaunchedEffect(Unit) {
        viewModel.loadHistory(conversationId)
    }

    Scaffold(
        topBar = {
            Column {
                CenterAlignedTopAppBar(
                    title = {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Image(
                                painter = painterResource(id = com.psikochat.app.R.drawable.ic_logo),
                                contentDescription = "Logo",
                                modifier = Modifier.size(22.dp)
                            )
                            Spacer(modifier = Modifier.width(8.dp))
                            val titleText = remember(messages, conversationId) {
                                if (conversationId != null) {
                                    val firstMsg = messages.firstOrNull()
                                    if (firstMsg != null) {
                                        "Geçmiş Sohbet (${extractDateString(firstMsg.timestamp)})"
                                    } else {
                                        if (conversationId.length > 20) "Geçmiş Sohbet" else "Geçmiş Sohbet ($conversationId)"
                                    }
                                } else {
                                    "PsikoChat"
                                }
                            }
                            Text(titleText, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold, color = LoginTextColor)
                        }
                    },
                    navigationIcon = {
                        IconButton(onClick = { navController.popBackStack() }) {
                            Icon(Icons.AutoMirrored.Filled.KeyboardArrowLeft, contentDescription = "Geri", tint = LoginTextColor)
                        }
                    },
                    actions = {
                        IconButton(onClick = { showNewChatConfirm = true }) {
                            Icon(Icons.Default.Add, contentDescription = "Yeni Sohbet", tint = LoginTextColor)
                        }
                        IconButton(onClick = { navController.navigate("chat_history") }) {
                            Icon(Icons.AutoMirrored.Filled.List, contentDescription = "Sohbet Geçmişi", tint = LoginTextColor)
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
                },
                enabled = aiConsentGranted != false
            )
        },
        containerColor = LoginBackground
    ) { padding ->
        Column(modifier = Modifier.padding(padding).fillMaxSize()) {

            if (isConsentOffline) {
                Surface(
                    color = SoftMintAccent.copy(alpha = 0.3f),
                    shape = RoundedCornerShape(8.dp),
                    modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 4.dp)
                ) {
                    Row(
                        modifier = Modifier.padding(8.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Icon(
                            imageVector = Icons.Default.Info,
                            contentDescription = null,
                            tint = DarkTealPrimary,
                            modifier = Modifier.size(16.dp)
                        )
                        Spacer(modifier = Modifier.width(8.dp))
                        Text(
                            text = "Gizlilik izni çevrimdışı doğrulanamadı, mevcut ayarlarla devam ediliyor.",
                            fontSize = 11.sp,
                            color = LoginTextColor,
                            fontWeight = FontWeight.Medium
                        )
                    }
                }
            }

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

            val filteredMessages = messages
            val groupedMessages = remember(filteredMessages) {
                filteredMessages.groupBy { extractDateString(it.timestamp) }
            }

            LazyColumn(
                state = listState,
                modifier = Modifier.weight(1f).fillMaxWidth(),
                contentPadding = PaddingValues(16.dp),
                reverseLayout = false
            ) {
                if (filteredMessages.isEmpty() && !isLoading) {
                    item {
                        EmptyChatState(modifier = Modifier.fillParentMaxSize())
                    }
                } else {
                    item {
                        SystemNoteBubble("PsikoChat'e hoş geldiniz, $welcomeName! Lütfen bugün nasıl hissettiğinizi paylaşın.")
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

                activeEmergencySupport?.let { support ->
                    item {
                        EmergencySupportCard(
                            title = support.emergencyTitle ?: "Acil Destek",
                            message = support.emergencyMessage ?: "Güvende kalman öncelikli. Yalnız kalmamaya çalış ve mümkünse hemen destek al.",
                            emergencyPhone = support.emergencyPhone,
                            onDialEmergency = {
                                try {
                                    val intent = Intent(Intent.ACTION_DIAL).apply {
                                        data = Uri.parse("tel:${support.emergencyPhone ?: "112"}")
                                    }
                                    context.startActivity(intent)
                                } catch (e: Exception) {
                                    Toast.makeText(context, "Arama başlatılamadı", Toast.LENGTH_SHORT).show()
                                }
                            },
                            onDialTrusted = {
                                try {
                                    val intent = Intent(Intent.ACTION_DIAL).apply {
                                        data = Uri.parse("tel:")
                                    }
                                    context.startActivity(intent)
                                } catch (e: Exception) {
                                    Toast.makeText(context, "Arama başlatılamadı", Toast.LENGTH_SHORT).show()
                                }
                            },
                            onPsychologistSupport = {
                                navController.navigate("therapy")
                            },
                            onContinueChat = {
                                viewModel.clearEmergencySupport()
                            }
                        )
                        Spacer(modifier = Modifier.height(12.dp))
                    }
                }
            }

            if (aiConsentGranted == false) {
                Surface(
                    color = MildAlertBg,
                    border = androidx.compose.foundation.BorderStroke(1.dp, MildAlertText.copy(alpha = 0.3f)),
                    shape = RoundedCornerShape(16.dp),
                    modifier = Modifier.fillMaxWidth().padding(16.dp),
                    shadowElevation = 2.dp
                ) {
                    Column(
                        modifier = Modifier.padding(16.dp),
                        horizontalAlignment = Alignment.CenterHorizontally
                    ) {
                        Text(
                            text = "AI yanıtları için işleme izni gerekli.",
                            fontSize = 14.sp,
                            fontWeight = FontWeight.Bold,
                            color = MildAlertText,
                            textAlign = TextAlign.Center
                        )
                        Spacer(modifier = Modifier.height(12.dp))
                        Button(
                            onClick = { navController.navigate("privacy_data") },
                            colors = ButtonDefaults.buttonColors(containerColor = DarkTealPrimary),
                            shape = RoundedCornerShape(12.dp),
                            modifier = Modifier.fillMaxWidth()
                        ) {
                            Text("Gizlilik Ayarlarına Git", color = Color.White, fontWeight = FontWeight.Bold)
                        }
                    }
                }
            }
        }
    }

    if (showNewChatConfirm) {
        AlertDialog(
            onDismissRequest = { showNewChatConfirm = false },
            title = { Text("Yeni sohbet başlatılsın mı?", fontWeight = FontWeight.Bold, color = LoginTextColor) },
            text = { Text("Mevcut sohbet geçmişin silinmeyecek. Sadece ekrandaki aktif konuşma temizlenecek.", color = LoginTextColor) },
            confirmButton = {
                Button(
                    onClick = {
                        viewModel.startNewChat()
                        showNewChatConfirm = false
                    },
                    colors = ButtonDefaults.buttonColors(containerColor = DarkTealPrimary)
                ) {
                    Text("Başlat", color = Color.White)
                }
            },
            dismissButton = {
                TextButton(onClick = { showNewChatConfirm = false }) {
                    Text("Vazgeç")
                }
            }
        )
    }

    if (crisisAlert != null) {
        AlertDialog(
            onDismissRequest = { viewModel.clearCrisisAlert() },
            title = {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(Icons.Default.Warning, contentDescription = null, tint = DangerRed, modifier = Modifier.size(24.dp))
                    Spacer(modifier = Modifier.width(8.dp))
                    Text("Destek ve Güvenlik ❤️", fontWeight = FontWeight.Bold, color = LoginTextColor)
                }
            },
            text = {
                Column {
                    Text(
                        text = crisisAlert!!,
                        fontSize = 14.sp,
                        color = LoginTextColor
                    )
                    Spacer(modifier = Modifier.height(16.dp))
                    Surface(
                        color = MildAlertBg,
                        border = androidx.compose.foundation.BorderStroke(1.dp, MildAlertText.copy(alpha = 0.3f)),
                        shape = RoundedCornerShape(12.dp),
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        Text(
                            text = "Unutmayın, yalnız değilsiniz. Destek ekiplerimiz ve acil hatlar 7/24 yanınızda.",
                            fontSize = 11.sp,
                            fontWeight = FontWeight.SemiBold,
                            color = MildAlertText,
                            modifier = Modifier.padding(12.dp)
                        )
                    }
                    Spacer(modifier = Modifier.height(16.dp))
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        Button(
                            onClick = {
                                try {
                                    val intent = Intent(Intent.ACTION_DIAL).apply {
                                        data = Uri.parse("tel:112")
                                    }
                                    context.startActivity(intent)
                                } catch (e: Exception) {
                                    Toast.makeText(context, "Arama başlatılamadı: 112", Toast.LENGTH_SHORT).show()
                                }
                            },
                            colors = ButtonDefaults.buttonColors(containerColor = DangerRed),
                            modifier = Modifier.weight(1f),
                            shape = RoundedCornerShape(12.dp)
                        ) {
                            Text("112'yi Ara", color = Color.White, fontWeight = FontWeight.Bold, fontSize = 12.sp)
                        }

                        Button(
                            onClick = {
                                try {
                                    val intent = Intent(Intent.ACTION_DIAL).apply {
                                        data = Uri.parse("tel:114")
                                    }
                                    context.startActivity(intent)
                                } catch (e: Exception) {
                                    Toast.makeText(context, "Arama başlatılamadı: 114", Toast.LENGTH_SHORT).show()
                                }
                            },
                            colors = ButtonDefaults.buttonColors(containerColor = DarkTealPrimary),
                            modifier = Modifier.weight(1f),
                            shape = RoundedCornerShape(12.dp)
                        ) {
                            Text("114 Destek Hattı", color = Color.White, fontWeight = FontWeight.Bold, fontSize = 12.sp)
                        }
                    }
                }
            },
            confirmButton = {
                Button(
                    onClick = { viewModel.clearCrisisAlert() },
                    colors = ButtonDefaults.buttonColors(containerColor = DarkTealPrimary)
                ) {
                    Text("Anladım", color = Color.White)
                }
            }
        )
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
                shadowElevation = 1.dp,
                border = if (isUser) null else androidx.compose.foundation.BorderStroke(1.dp, SoftMintAccent.copy(alpha = 0.5f))
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
                    Row(
                        modifier = Modifier.align(Alignment.End),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.End
                    ) {
                        Text(
                            text = formatMessageTime(msg.timestamp),
                            color = timeColor,
                            fontSize = 10.sp
                        )
                        if (isUser) {
                            Spacer(modifier = Modifier.width(4.dp))
                            val (icon, color) = when (msg.state) {
                                "pending" -> Icons.Default.Refresh to timeColor
                                "failed" -> Icons.Default.Warning to Color(0xFFEF4444)
                                else -> Icons.Default.Check to timeColor
                            }
                            Icon(
                                imageVector = icon,
                                contentDescription = msg.state,
                                tint = color,
                                modifier = Modifier.size(10.dp)
                            )
                        }
                    }
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
fun ChatInputBar(
    isLoading: Boolean, 
    onSendMessage: (String) -> Unit, 
    onTextChanged: () -> Unit = {},
    enabled: Boolean = true
) {
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
                enabled = enabled && !isLoading,
                placeholder = { Text("Mesajınızı yazın...", fontSize = 14.sp) },
                shape = RoundedCornerShape(24.dp),
                colors = OutlinedTextFieldDefaults.colors(
                    focusedBorderColor = LoginButton,
                    unfocusedBorderColor = Color.LightGray
                ),
                keyboardOptions = KeyboardOptions(imeAction = ImeAction.Send),
                keyboardActions = KeyboardActions(
                    onSend = {
                        if (inputText.isNotBlank() && !isLoading && enabled) {
                            android.util.Log.d("ChatInput", "RAW_INPUT = $inputText")
                            android.util.Log.d("ChatInput", "UNICODE_CODEPOINTS = ${inputText.map { it.code }.joinToString(",")}")
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
                    if (inputText.isNotBlank() && !isLoading && enabled) {
                        android.util.Log.d("ChatInput", "RAW_INPUT = $inputText")
                        android.util.Log.d("ChatInput", "UNICODE_CODEPOINTS = ${inputText.map { it.code }.joinToString(",")}")
                        onSendMessage(inputText)
                        inputText = ""
                    }
                },
                enabled = enabled && !isLoading,
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
            "Sistem Notu",
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

fun parseDateSafely(timestamp: String?): Date? {
    if (timestamp.isNullOrBlank()) return null
    val formats = listOf(
        "yyyy-MM-dd'T'HH:mm:ss.SSS'Z'",
        "yyyy-MM-dd'T'HH:mm:ss.SSS",
        "yyyy-MM-dd'T'HH:mm:ss",
        "yyyy-MM-dd HH:mm:ss",
        "yyyy-MM-dd"
    )
    for (format in formats) {
        try {
            val sdf = SimpleDateFormat(format, Locale.getDefault())
            if (format.endsWith("'Z'")) {
                sdf.timeZone = java.util.TimeZone.getTimeZone("UTC")
            }
            val date = sdf.parse(timestamp)
            if (date != null) return date
        } catch (e: Exception) {
            // try next format
        }
    }
    return null
}

fun formatMessageTime(timestamp: String?): String {
    if (timestamp == null) return "Şimdi"
    val date = parseDateSafely(timestamp) ?: return ""
    return try {
        val formatter = SimpleDateFormat("HH:mm", Locale.getDefault())
        formatter.format(date)
    } catch (e: Exception) {
        ""
    }
}

fun extractDateString(timestamp: String?): String {
    if (timestamp == null) return "Bugün"
    val date = parseDateSafely(timestamp) ?: return "Bilinmeyen Tarih"
    return try {
        val formatter = SimpleDateFormat("dd MMMM yyyy", Locale("tr", "TR"))
        val dateString = formatter.format(date)
        
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

@Composable
fun EmergencySupportCard(
    title: String,
    message: String,
    emergencyPhone: String?,
    onDialEmergency: () -> Unit,
    onDialTrusted: () -> Unit,
    onPsychologistSupport: () -> Unit,
    onContinueChat: () -> Unit
) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 12.dp, horizontal = 4.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.errorContainer),
        elevation = CardDefaults.cardElevation(defaultElevation = 4.dp),
        shape = RoundedCornerShape(16.dp),
        border = androidx.compose.foundation.BorderStroke(1.dp, MaterialTheme.colorScheme.error.copy(alpha = 0.5f))
    ) {
        Column(
            modifier = Modifier.padding(16.dp)
        ) {
            Row(
                verticalAlignment = Alignment.CenterVertically
            ) {
                Icon(
                    imageVector = Icons.Default.Warning,
                    contentDescription = null,
                    tint = MaterialTheme.colorScheme.error,
                    modifier = Modifier.size(24.dp)
                )
                Spacer(modifier = Modifier.width(8.dp))
                Text(
                    text = title,
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold,
                    color = MaterialTheme.colorScheme.onErrorContainer
                )
            }
            
            Spacer(modifier = Modifier.height(8.dp))
            
            Text(
                text = message,
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onErrorContainer.copy(alpha = 0.8f)
            )
            
            Spacer(modifier = Modifier.height(16.dp))
            
            Column(
                modifier = Modifier.fillMaxWidth(),
                verticalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                if (!emergencyPhone.isNullOrBlank()) {
                    Button(
                        onClick = onDialEmergency,
                        colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.error),
                        modifier = Modifier.fillMaxWidth(),
                        shape = RoundedCornerShape(12.dp)
                    ) {
                        Text(text = "${emergencyPhone}'yi Ara", color = Color.White, fontWeight = FontWeight.Bold)
                    }
                }
                
                Button(
                    onClick = onDialTrusted,
                    colors = ButtonDefaults.buttonColors(containerColor = DarkTealPrimary),
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(12.dp)
                ) {
                    Text(text = "Güvendiğim Birini Ara", color = Color.White, fontWeight = FontWeight.Bold)
                }
                
                Button(
                    onClick = onPsychologistSupport,
                    colors = ButtonDefaults.buttonColors(containerColor = SoftMintAccent),
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(12.dp)
                ) {
                    Text(text = "Randevu / Psikolog Desteği", color = LoginTextColor, fontWeight = FontWeight.Bold)
                }
                
                TextButton(
                    onClick = onContinueChat,
                    modifier = Modifier.align(Alignment.CenterHorizontally)
                ) {
                    Text(text = "Sohbete Devam Et", color = MaterialTheme.colorScheme.error, fontWeight = FontWeight.SemiBold)
                }
            }
        }
    }
}