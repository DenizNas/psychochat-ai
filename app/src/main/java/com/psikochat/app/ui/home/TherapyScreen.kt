package com.psikochat.app.ui.home

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
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
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.navigation.NavController
import com.psikochat.app.data.local.TokenManager
import com.psikochat.app.ui.theme.*
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

@Immutable
data class Psychologist(
    val name: String,
    val specialty: String
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun TherapyScreen(navController: NavController, tokenManager: TokenManager) {
    val psychologists = remember {
        listOf(
            Psychologist("Uzm. Psk. Elif Kaya", "Bilişsel Terapi, Anksiyete"),
            Psychologist("Dr. Psk. Ahmet Yılmaz", "Depresyon, Aile Danışmanlığı"),
            Psychologist("Uzm. Psk. Ayşe Demir", "Çocuk ve Ergen Psikolojisi")
        )
    }

    var showSuccessMessage by remember { mutableStateOf(false) }
    val snackbarHostState = remember { SnackbarHostState() }
    val scope = rememberCoroutineScope()

    Scaffold(
        snackbarHost = { SnackbarHost(snackbarHostState) },
        topBar = {
            CenterAlignedTopAppBar(
                title = {
                    Text(
                        "Psikolog Yönlendirme ve Randevu",
                        style = MaterialTheme.typography.titleMedium,
                        color = LoginTextColor,
                        fontSize = 16.sp
                    )
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
        },
        bottomBar = {
            NavigationBar(
                containerColor = Color.White,
                tonalElevation = 8.dp,
                modifier = Modifier.height(80.dp)
            ) {
                NavigationBarItem(
                    icon = { Icon(Icons.Default.Home, contentDescription = null) },
                    label = { Text("Ana Sayfa", fontSize = 10.sp) },
                    selected = false,
                    onClick = { navController.navigate("home") { popUpTo("home") { inclusive = true } } }
                )
                NavigationBarItem(
                    icon = { Icon(Icons.Default.Share, contentDescription = null) },
                    label = { Text("Terapi", fontSize = 10.sp) },
                    selected = true,
                    onClick = { }
                )
                
                Box(
                    modifier = Modifier
                        .weight(1f)
                        .fillMaxHeight()
                        .clickable { navController.navigate("chat") },
                    contentAlignment = Alignment.Center
                ) {
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        Surface(
                            shape = CircleShape,
                            color = LoginButton,
                            modifier = Modifier.size(44.dp),
                            shadowElevation = 2.dp
                        ) {
                            Icon(Icons.Default.Face, contentDescription = "PsikoChat", tint = Color.White, modifier = Modifier.padding(10.dp))
                        }
                        Text("PsikoChat", fontSize = 10.sp, fontWeight = FontWeight.Bold, color = LoginButton)
                    }
                }

                NavigationBarItem(
                    icon = { Icon(Icons.Default.Person, contentDescription = null) },
                    label = { Text("Gelişim", fontSize = 10.sp) },
                    selected = false,
                    onClick = { navController.navigate("profile") }
                )
                NavigationBarItem(
                    icon = { Icon(Icons.Default.Settings, contentDescription = null) },
                    label = { Text("Ayarlar", fontSize = 10.sp) },
                    selected = false,
                    onClick = { navController.navigate("settings") }
                )
            }
        },
        containerColor = LoginBackground
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(horizontal = 24.dp)
        ) {
            Spacer(modifier = Modifier.height(16.dp))

            // Red Alert Box
            Surface(
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(12.dp),
                color = Color(0xFFFEE2E2) // Light red
            ) {
                Row(
                    modifier = Modifier.padding(16.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Icon(Icons.Default.Warning, contentDescription = null, tint = Color.Red)
                    Spacer(modifier = Modifier.width(12.dp))
                    Text(
                        text = "Riskli destek için bir uzman yönlendiriliyorsunuz.",
                        color = Color.Red,
                        fontSize = 14.sp,
                        fontWeight = FontWeight.Medium
                    )
                }
            }

            Spacer(modifier = Modifier.height(24.dp))

            Text(
                text = "Psikolog Listesi",
                style = MaterialTheme.typography.titleLarge.copy(fontWeight = FontWeight.Bold),
                color = LoginTextColor
            )

            Spacer(modifier = Modifier.height(16.dp))

            LazyColumn(
                verticalArrangement = Arrangement.spacedBy(16.dp),
                contentPadding = PaddingValues(bottom = 16.dp)
            ) {
                items(psychologists) { psychologist ->
                    PsychologistCard(psychologist) {
                        scope.launch {
                            snackbarHostState.showSnackbar(
                                message = "Randevunuz Başarıyla oluşturulmuştur.",
                                duration = SnackbarDuration.Short
                            )
                        }
                    }
                }
            }
        }
    }
}

@Composable
fun PsychologistCard(psychologist: Psychologist, onAppointmentCreated: () -> Unit) {
    Surface(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(24.dp),
        color = Color.White.copy(alpha = 0.9f),
        shadowElevation = 2.dp
    ) {
        Box(modifier = Modifier.padding(16.dp)) {
            Icon(
                Icons.Default.Info,
                contentDescription = null,
                tint = LoginButton,
                modifier = Modifier.align(Alignment.TopEnd).size(20.dp)
            )
            
            Row(verticalAlignment = Alignment.CenterVertically) {
                Box(
                    modifier = Modifier
                        .size(64.dp)
                        .clip(CircleShape)
                        .background(Color.LightGray),
                    contentAlignment = Alignment.Center
                ) {
                    Icon(Icons.Default.Person, contentDescription = null, modifier = Modifier.size(40.dp), tint = Color.White)
                }
                
                Spacer(modifier = Modifier.width(16.dp))
                
                Column(modifier = Modifier.weight(1f)) {
                    Text(
                        text = psychologist.name,
                        fontWeight = FontWeight.Bold,
                        fontSize = 16.sp,
                        color = LoginTextColor
                    )
                    Text(
                        text = "Uzmanlık Alanı: ${psychologist.specialty}",
                        fontSize = 12.sp,
                        color = LoginSecondaryText
                    )
                    Spacer(modifier = Modifier.height(8.dp))
                    Button(
                        onClick = onAppointmentCreated,
                        colors = ButtonDefaults.buttonColors(containerColor = LoginButton),
                        shape = RoundedCornerShape(12.dp),
                        modifier = Modifier.height(36.dp),
                        contentPadding = PaddingValues(horizontal = 16.dp, vertical = 0.dp)
                    ) {
                        Text("Randevu Oluştur", fontSize = 12.sp, color = Color.White)
                    }
                }
            }
        }
    }
}
