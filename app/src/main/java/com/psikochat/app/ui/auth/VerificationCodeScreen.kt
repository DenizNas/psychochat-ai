package com.psikochat.app.ui.auth

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
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
import com.psikochat.app.data.repository.AuthRepository
import com.psikochat.app.ui.theme.*
import kotlinx.coroutines.delay

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun VerificationCodeScreen(navController: NavController, email: String, tokenManager: TokenManager) {
    val api = RetrofitClient.create(tokenManager)
    val repo = AuthRepository(api)
    val factory = object : ViewModelProvider.Factory {
        override fun <T : ViewModel> create(modelClass: Class<T>): T {
            return AuthViewModel(repo, tokenManager) as T
        }
    }
    val viewModel: AuthViewModel = viewModel(factory = factory)

    var code by remember { mutableStateOf("") }
    var validationError by remember { mutableStateOf<String?>(null) }
    var cooldownSeconds by remember { mutableStateOf(60) }
    
    val verifyState by viewModel.verifyCodeState.collectAsState()
    val requestState by viewModel.resetRequestState.collectAsState()

    // Resend countdown timer
    LaunchedEffect(cooldownSeconds) {
        if (cooldownSeconds > 0) {
            delay(1000)
            cooldownSeconds -= 1
        }
    }

    LaunchedEffect(verifyState) {
        if (verifyState is Resource.Success && (verifyState.data != null)) {
            val token = verifyState.data!!
            val encodedToken = java.net.URLEncoder.encode(token, "UTF-8")
            navController.navigate("reset_password/$encodedToken")
        }
    }

    DisposableEffect(Unit) {
        onDispose {
            viewModel.resetResetStates()
        }
    }

    Scaffold(
        topBar = {
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
                        Text(
                            "PsikoChat",
                            style = MaterialTheme.typography.titleMedium,
                            color = LoginTextColor
                        )
                    }
                },
                navigationIcon = {
                    IconButton(onClick = { navController.popBackStack() }) {
                        Icon(imageVector = Icons.Default.KeyboardArrowLeft, contentDescription = "Back", tint = LoginTextColor)
                    }
                },
                actions = {
                    IconButton(onClick = { }) {
                        Icon(imageVector = Icons.Default.Menu, contentDescription = "Menu", tint = LoginTextColor)
                    }
                },
                colors = TopAppBarDefaults.centerAlignedTopAppBarColors(
                    containerColor = Color.Transparent
                )
            )
        },
        bottomBar = {
            NavigationBar(containerColor = Color.White) {
                NavigationBarItem(
                    icon = { Icon(Icons.Default.Home, contentDescription = null) },
                    label = { Text("Ana Sayfa", fontSize = 10.sp) },
                    selected = false,
                    onClick = { }
                )
                NavigationBarItem(
                    icon = { Icon(Icons.Default.Share, contentDescription = null) },
                    label = { Text("Terapi", fontSize = 10.sp) },
                    selected = false,
                    onClick = { }
                )
                NavigationBarItem(
                    icon = { Icon(Icons.Default.Person, contentDescription = null) },
                    label = { Text("Gelişim", fontSize = 10.sp) },
                    selected = false,
                    onClick = { }
                )
                NavigationBarItem(
                    icon = { Icon(Icons.Default.Settings, contentDescription = null) },
                    label = { Text("Ayarlar", fontSize = 10.sp) },
                    selected = true,
                    onClick = { }
                )
            }
        },
        containerColor = LoginBackground
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(horizontal = 24.dp),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            Spacer(modifier = Modifier.height(16.dp))
            
            // Header
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Box(
                    modifier = Modifier
                        .size(56.dp)
                        .clip(CircleShape)
                        .background(Color.LightGray)
                ) {
                    Icon(Icons.Default.Person, contentDescription = null, modifier = Modifier.fillMaxSize().padding(10.dp), tint = Color.White)
                }
                Spacer(modifier = Modifier.width(16.dp))
                Column {
                    Text(
                        text = "Doğrulama Kodu",
                        style = MaterialTheme.typography.titleLarge.copy(fontWeight = FontWeight.Bold),
                        color = LoginTextColor
                    )
                    Text(
                        text = "E-postanı kontrol et.",
                        style = MaterialTheme.typography.bodyLarge,
                        color = LoginTextColor
                    )
                }
            }

            Spacer(modifier = Modifier.height(24.dp))

            // Card
            Surface(
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(32.dp),
                color = Color.White.copy(alpha = 0.9f)
            ) {
                Column(
                    modifier = Modifier.padding(24.dp),
                    horizontalAlignment = Alignment.CenterHorizontally
                ) {
                    // Lock Icon Illustration
                    Box(
                        modifier = Modifier.size(120.dp),
                        contentAlignment = Alignment.Center
                    ) {
                        Icon(
                            imageVector = Icons.Default.Lock,
                            contentDescription = null,
                            modifier = Modifier.size(80.dp),
                            tint = LoginButton.copy(alpha = 0.5f)
                        )
                        Icon(
                            imageVector = Icons.Default.CheckCircle,
                            contentDescription = null,
                            modifier = Modifier.size(40.dp).align(Alignment.BottomEnd),
                            tint = LoginButton
                        )
                    }
                    
                    Spacer(modifier = Modifier.height(16.dp))
                    
                    Text(
                        text = "$email adresine 6 haneli bir doğrulama kodu gönderdik. Lütfen kodu giriniz.",
                        textAlign = TextAlign.Center,
                        fontSize = 14.sp,
                        color = LoginTextColor,
                        lineHeight = 20.sp
                    )

                    Spacer(modifier = Modifier.height(24.dp))

                    OutlinedTextField(
                        value = code,
                        onValueChange = { 
                            if (it.length <= 6) {
                                code = it.filter { char -> char.isDigit() }
                            }
                        },
                        placeholder = { Text("6 Haneli Kod", color = Color.Gray, fontSize = 14.sp, textAlign = TextAlign.Center) },
                        textStyle = TextStyle(color = LoginTextColor, textAlign = TextAlign.Center, fontSize = 18.sp, fontWeight = FontWeight.Bold),
                        modifier = Modifier.fillMaxWidth(0.7f),
                        shape = RoundedCornerShape(12.dp),
                        colors = OutlinedTextFieldDefaults.colors(
                            unfocusedBorderColor = LoginButton.copy(alpha = 0.5f),
                            focusedBorderColor = LoginButton
                        ),
                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                        singleLine = true
                    )

                    Spacer(modifier = Modifier.height(16.dp))

                    val displayError = validationError ?: (if (verifyState is Resource.Error) (verifyState as Resource.Error).message else null)
                    if (displayError != null) {
                        Text(
                            text = displayError,
                            color = Color.Red,
                            style = MaterialTheme.typography.bodyMedium.copy(fontWeight = FontWeight.Medium),
                            textAlign = TextAlign.Center,
                            modifier = Modifier.fillMaxWidth()
                        )
                        Spacer(modifier = Modifier.height(16.dp))
                    }

                    Button(
                        onClick = {
                            validationError = null
                            if (code.length != 6) {
                                validationError = "Lütfen 6 haneli doğrulama kodunu eksiksiz giriniz."
                            } else {
                                viewModel.verifyPasswordResetCode(email, code)
                            }
                        },
                        modifier = Modifier
                            .fillMaxWidth()
                            .height(56.dp),
                        shape = RoundedCornerShape(28.dp),
                        colors = ButtonDefaults.buttonColors(
                            containerColor = LoginButton,
                            disabledContainerColor = LoginButton.copy(alpha = 0.6f)
                        ),
                        enabled = verifyState !is Resource.Loading
                    ) {
                        if (verifyState is Resource.Loading) {
                            CircularProgressIndicator(color = Color.White, modifier = Modifier.size(24.dp), strokeWidth = 2.dp)
                        } else {
                            Text("Kodu Doğrula", color = Color.White, fontWeight = FontWeight.Bold)
                        }
                    }

                    Spacer(modifier = Modifier.height(24.dp))

                    if (cooldownSeconds > 0) {
                        Text(
                            text = "Tekrar Kod Gönder ($cooldownSeconds)",
                            color = Color.Gray,
                            fontWeight = FontWeight.Medium,
                            fontSize = 14.sp
                        )
                    } else {
                        Text(
                            text = "Tekrar Kod Gönder",
                            color = LoginButton,
                            fontWeight = FontWeight.Bold,
                            fontSize = 14.sp,
                            modifier = Modifier.clickable {
                                validationError = null
                                cooldownSeconds = 60
                                viewModel.requestPasswordReset(email)
                            }
                        )
                    }
                }
            }
        }
    }
}
