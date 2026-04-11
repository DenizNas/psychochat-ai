package com.psikochat.app.ui.chat

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Send
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavController
import com.psikochat.app.data.api.RetrofitClient
import com.psikochat.app.data.local.TokenManager
import com.psikochat.app.data.model.HistoryItem
import com.psikochat.app.data.repository.ChatRepository
import com.psikochat.app.ui.theme.*
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ChatScreen(navController: NavController, tokenManager: TokenManager) {
    val api = RetrofitClient.create(tokenManager)
    val repo = ChatRepository(api)
    val factory = object : ViewModelProvider.Factory {
        override fun <T : ViewModel> create(modelClass: Class<T>): T {
            return ChatViewModel(repo) as T
        }
    }
    val viewModel: ChatViewModel = viewModel(factory = factory)
    
    val messages by viewModel.messages.collectAsState()
    val isLoading by viewModel.isLoading.collectAsState()
    val error by viewModel.error.collectAsState()
    val crisisAlert by viewModel.crisisAlert.collectAsState()
    
    var inputText by remember { mutableStateOf("") }
    val scope = rememberCoroutineScope()
    
    LaunchedEffect(Unit) {
        viewModel.loadHistory()
    }
    
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Psikochat-AI") },
                actions = {
                    TextButton(onClick = {
                        scope.launch {
                            tokenManager.clearToken()
                            navController.navigate("login") { popUpTo("chat") { inclusive = true } }
                        }
                    }) {
                        Text("Çıkış", color = MaterialTheme.colorScheme.error)
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = DarkSurface)
            )
        },
        bottomBar = {
            Surface(color = DarkSurface, modifier = Modifier.fillMaxWidth()) {
                Row(
                    modifier = Modifier.padding(8.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    OutlinedTextField(
                        value = inputText,
                        onValueChange = { inputText = it },
                        modifier = Modifier.weight(1f),
                        placeholder = { Text("Mesajınızı yazın...") },
                        colors = OutlinedTextFieldDefaults.colors(
                            unfocusedContainerColor = DarkBackground,
                            focusedContainerColor = DarkBackground
                        )
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    IconButton(
                        onClick = {
                            viewModel.sendMessage(inputText)
                            inputText = ""
                        },
                        colors = IconButtonDefaults.iconButtonColors(containerColor = AccentPrimary)
                    ) {
                        Icon(Icons.Default.Send, contentDescription = "Gönder", tint = Color.White)
                    }
                }
            }
        }
    ) { padding ->
        Column(modifier = Modifier.padding(padding).fillMaxSize()) {
            if (crisisAlert != null) {
                Surface(color = DangerRed.copy(alpha = 0.2f), modifier = Modifier.fillMaxWidth()) {
                    Text(
                        text = "Acil Durum: $crisisAlert",
                        color = DangerRed,
                        modifier = Modifier.padding(16.dp)
                    )
                }
            }
            
            if (error != null) {
                Text(text = error!!, color = DangerRed, modifier = Modifier.padding(16.dp))
            }
            
            LazyColumn(
                modifier = Modifier.weight(1f).fillMaxWidth(),
                contentPadding = PaddingValues(16.dp),
                reverseLayout = false
            ) {
                items(messages) { msg ->
                    MessageBubble(msg)
                    Spacer(modifier = Modifier.height(8.dp))
                }
                if (isLoading) {
                    item {
                        Box(contentAlignment = Alignment.Center, modifier = Modifier.fillMaxWidth().padding(16.dp)) {
                            CircularProgressIndicator()
                        }
                    }
                }
            }
        }
    }
}

@Composable
fun MessageBubble(msg: HistoryItem) {
    val isUser = msg.role == "user"
    val bgColor = if (isUser) AccentPrimary.copy(alpha=0.85f) else SystemChatBubble.copy(alpha=0.85f)
    val align = if (isUser) Alignment.CenterEnd else Alignment.CenterStart
    val shape = if (isUser) RoundedCornerShape(16.dp, 16.dp, 0.dp, 16.dp) else RoundedCornerShape(16.dp, 16.dp, 16.dp, 0.dp)
    
    Box(contentAlignment = align, modifier = Modifier.fillMaxWidth()) {
        Surface(
            color = bgColor,
            shape = shape,
            modifier = Modifier.widthIn(max = 280.dp)
        ) {
            Text(
                text = msg.text,
                color = Color.White,
                modifier = Modifier.padding(12.dp)
            )
        }
    }
}
