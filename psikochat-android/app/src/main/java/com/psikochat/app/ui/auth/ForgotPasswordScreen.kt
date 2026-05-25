package com.psikochat.app.ui.auth

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
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
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.navigation.NavController
import com.psikochat.app.ui.theme.*

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ForgotPasswordScreen(navController: NavController) {
    var emailOrPhone by remember { mutableStateOf("") }

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
                        text = "Merhaba, Elif!",
                        style = MaterialTheme.typography.titleLarge.copy(fontWeight = FontWeight.Bold),
                        color = LoginTextColor
                    )
                    Text(
                        text = "Şifreni mi unuttun?",
                        style = MaterialTheme.typography.bodyLarge,
                        color = LoginTextColor
                    )
                }
            }

            Spacer(modifier = Modifier.height(24.dp))

            // Forgot Password Card
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
                            imageVector = Icons.Default.Info,
                            contentDescription = null,
                            modifier = Modifier.size(40.dp).align(Alignment.BottomEnd),
                            tint = LoginButton
                        )
                    }
                    
                    Spacer(modifier = Modifier.height(16.dp))
                    
                    Text(
                        text = "Hemen şifreni yenilemek için kayıtlı e-posta adresini veya telefon numaranı gir. Sana bir doğrulama kodu göndereceğiz.",
                        textAlign = TextAlign.Center,
                        fontSize = 14.sp,
                        color = LoginTextColor,
                        lineHeight = 20.sp
                    )

                    Spacer(modifier = Modifier.height(24.dp))

                    OutlinedTextField(
                        value = emailOrPhone,
                        onValueChange = { emailOrPhone = it },
                        placeholder = { Text("E-posta veya Telefon Numarası", color = Color.Gray, fontSize = 14.sp) },
                        textStyle = TextStyle(color = LoginTextColor),
                        modifier = Modifier.fillMaxWidth(),
                        shape = RoundedCornerShape(12.dp),
                        leadingIcon = { Icon(Icons.Default.Email, contentDescription = null, tint = Color.Gray) },
                        trailingIcon = { Icon(Icons.Default.Call, contentDescription = null, tint = Color.Gray) },
                        colors = OutlinedTextFieldDefaults.colors(
                            unfocusedBorderColor = LoginButton.copy(alpha = 0.5f),
                            focusedBorderColor = LoginButton
                        ),
                        singleLine = true
                    )

                    Spacer(modifier = Modifier.height(24.dp))

                    Button(
                        onClick = { /* Handle send code */ },
                        modifier = Modifier
                            .fillMaxWidth()
                            .height(56.dp),
                        shape = RoundedCornerShape(28.dp),
                        colors = ButtonDefaults.buttonColors(containerColor = LoginButton)
                    ) {
                        Text("Doğrulama Kodu Gönder", color = Color.White, fontWeight = FontWeight.Bold)
                    }

                    Spacer(modifier = Modifier.height(24.dp))

                    Row {
                        Text(text = "Yardım mı lazım? ", color = LoginTextColor, fontSize = 14.sp)
                        Text(
                            text = "Bize ulaşın.",
                            color = LoginTextColor,
                            fontWeight = FontWeight.Bold,
                            fontSize = 14.sp,
                            modifier = Modifier.clickable { /* Handle contact */ }
                        )
                    }
                }
            }
        }
    }
}
