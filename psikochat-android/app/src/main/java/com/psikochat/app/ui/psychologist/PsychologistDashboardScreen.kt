package com.psikochat.app.ui.psychologist

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ExitToApp
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
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
import com.psikochat.app.data.repository.ProfileRepository
import com.psikochat.app.ui.home.ProfileViewModel
import com.psikochat.app.ui.theme.*
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun PsychologistDashboardScreen(navController: NavController, tokenManager: TokenManager) {
    val username by tokenManager.getUsername().collectAsState(initial = "Psikolog")
    val scope = rememberCoroutineScope()
    val scrollState = rememberScrollState()

    val api = RetrofitClient.create(tokenManager)
    val profileRepo = ProfileRepository(api)
    val profileFactory = object : ViewModelProvider.Factory {
        @Suppress("UNCHECKED_CAST")
        override fun <T : ViewModel> create(modelClass: Class<T>): T {
            return ProfileViewModel(profileRepo, tokenManager) as T
        }
    }
    val profileViewModel: ProfileViewModel = viewModel(factory = profileFactory)
    val profileState by profileViewModel.profileState.collectAsState()

    Scaffold(
        topBar = {
            CenterAlignedTopAppBar(
                title = {
                    Text(
                        "Psikolog Paneli",
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Bold,
                        color = LoginTextColor
                    )
                },
                colors = TopAppBarDefaults.centerAlignedTopAppBarColors(
                    containerColor = Color.Transparent
                )
            )
        },
        containerColor = LoginBackground
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .verticalScroll(scrollState)
                .padding(horizontal = 24.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Top
        ) {
            Spacer(modifier = Modifier.height(16.dp))

            // Professional Profile Avatar
            Box(
                contentAlignment = Alignment.Center,
                modifier = Modifier.size(100.dp)
            ) {
                Surface(
                    shape = CircleShape,
                    color = Color.White,
                    shadowElevation = 4.dp,
                    border = BorderStroke(3.dp, Color.White),
                    modifier = Modifier.size(100.dp)
                ) {
                    Box(
                        modifier = Modifier
                            .fillMaxSize()
                            .background(SoftMintAccent),
                        contentAlignment = Alignment.Center
                    ) {
                        Icon(
                            imageVector = Icons.Default.Person,
                            contentDescription = "Profil Resmi",
                            modifier = Modifier.size(54.dp),
                            tint = DarkTealPrimary
                        )
                    }
                }
            }

            Spacer(modifier = Modifier.height(16.dp))

            // Display Name / Username
            val displayName = when (val state = profileState) {
                is Resource.Success -> state.data?.fullName ?: state.data?.displayName ?: username
                else -> username
            }
            Text(
                text = displayName,
                style = MaterialTheme.typography.titleLarge.copy(
                    fontWeight = FontWeight.Bold,
                    fontSize = 22.sp
                ),
                color = LoginTextColor,
                textAlign = TextAlign.Center
            )

            Spacer(modifier = Modifier.height(24.dp))

            // 1. Card: Onay Durumu
            val status = when (val state = profileState) {
                is Resource.Success -> state.data?.status ?: "pending"
                else -> "pending"
            }
            val statusLabel = if (status == "approved") "Onaylandı" else "Onay Sürecinde (Beklemede)"
            val statusColor = if (status == "approved") DarkTealPrimary else MildAlertText
            val statusBg = if (status == "approved") SoftMintAccent.copy(alpha = 0.5f) else MildAlertBg

            Surface(
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(24.dp),
                color = PremiumWhiteCard,
                shadowElevation = 2.dp,
                border = BorderStroke(1.dp, SoftMintAccent.copy(alpha = 0.5f))
            ) {
                Column(
                    modifier = Modifier.padding(20.dp),
                    horizontalAlignment = Alignment.Start
                ) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(
                            imageVector = Icons.Default.CheckCircle,
                            contentDescription = null,
                            tint = statusColor,
                            modifier = Modifier.size(20.dp)
                        )
                        Spacer(modifier = Modifier.width(8.dp))
                        Text(
                            text = "Onay Durumu",
                            fontSize = 14.sp,
                            fontWeight = FontWeight.Bold,
                            color = LoginTextColor
                        )
                    }
                    Spacer(modifier = Modifier.height(12.dp))
                    Surface(
                        shape = RoundedCornerShape(12.dp),
                        color = statusBg,
                        border = BorderStroke(1.dp, statusColor.copy(alpha = 0.3f))
                    ) {
                        Text(
                            text = statusLabel,
                            color = statusColor,
                            fontWeight = FontWeight.Bold,
                            fontSize = 13.sp,
                            modifier = Modifier.padding(horizontal = 14.dp, vertical = 8.dp)
                        )
                    }
                    Spacer(modifier = Modifier.height(8.dp))
                    Text(
                        text = if (status == "approved") 
                            "Hesabınız onaylanmıştır. Aktif olarak randevu alabilir ve danışanlarınızla görüşebilirsiniz."
                            else "Profiliniz yöneticilerimiz tarafından incelenmektedir. Onaylandıktan sonra danışanlar sizi görebilecektir.",
                        fontSize = 12.sp,
                        color = LoginSecondaryText,
                        lineHeight = 18.sp
                    )
                }
            }

            Spacer(modifier = Modifier.height(16.dp))

            // 2. Card: Profil Bilgilerim
            val title = when (val state = profileState) {
                is Resource.Success -> state.data?.title ?: "Psikolog"
                else -> "Psikolog"
            }
            val specialty = when (val state = profileState) {
                is Resource.Success -> state.data?.specialty ?: "Genel Terapi"
                else -> "Genel Terapi"
            }
            val bio = when (val state = profileState) {
                is Resource.Success -> state.data?.bio ?: ""
                else -> ""
            }

            Surface(
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(24.dp),
                color = PremiumWhiteCard,
                shadowElevation = 2.dp,
                border = BorderStroke(1.dp, SoftMintAccent.copy(alpha = 0.5f))
            ) {
                Column(
                    modifier = Modifier.padding(20.dp),
                    horizontalAlignment = Alignment.Start
                ) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(
                            imageVector = Icons.Default.Info,
                            contentDescription = null,
                            tint = DarkTealPrimary,
                            modifier = Modifier.size(20.dp)
                        )
                        Spacer(modifier = Modifier.width(8.dp))
                        Text(
                            text = "Profil Bilgilerim",
                            fontSize = 14.sp,
                            fontWeight = FontWeight.Bold,
                            color = LoginTextColor
                        )
                    }
                    Spacer(modifier = Modifier.height(12.dp))
                    
                    Text(
                        text = "Unvan",
                        fontSize = 11.sp,
                        fontWeight = FontWeight.Bold,
                        color = LoginSecondaryText
                    )
                    Text(
                        text = title,
                        fontSize = 14.sp,
                        fontWeight = FontWeight.SemiBold,
                        color = LoginTextColor,
                        modifier = Modifier.padding(bottom = 8.dp)
                    )

                    Text(
                        text = "Uzmanlık Alanı",
                        fontSize = 11.sp,
                        fontWeight = FontWeight.Bold,
                        color = LoginSecondaryText
                    )
                    Text(
                        text = specialty,
                        fontSize = 14.sp,
                        fontWeight = FontWeight.SemiBold,
                        color = LoginTextColor,
                        modifier = Modifier.padding(bottom = 8.dp)
                    )

                    if (bio.isNotEmpty()) {
                        Text(
                            text = "Biyografi",
                            fontSize = 11.sp,
                            fontWeight = FontWeight.Bold,
                            color = LoginSecondaryText
                        )
                        Text(
                            text = bio,
                            fontSize = 13.sp,
                            color = LoginTextColor,
                            lineHeight = 18.sp
                        )
                    }
                }
            }

            Spacer(modifier = Modifier.height(16.dp))

            // 3. Card: Randevularım
            Surface(
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(24.dp),
                color = PremiumWhiteCard,
                shadowElevation = 2.dp,
                border = BorderStroke(1.dp, SoftMintAccent.copy(alpha = 0.5f))
            ) {
                Column(
                    modifier = Modifier.padding(20.dp),
                    horizontalAlignment = Alignment.Start
                ) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(
                            imageVector = Icons.Default.DateRange,
                            contentDescription = null,
                            tint = DarkTealPrimary,
                            modifier = Modifier.size(20.dp)
                        )
                        Spacer(modifier = Modifier.width(8.dp))
                        Text(
                            text = "Randevularım",
                            fontSize = 14.sp,
                            fontWeight = FontWeight.Bold,
                            color = LoginTextColor
                        )
                    }
                    Spacer(modifier = Modifier.height(16.dp))
                    Box(
                        modifier = Modifier.fillMaxWidth().padding(vertical = 12.dp),
                        contentAlignment = Alignment.Center
                    ) {
                        Column(horizontalAlignment = Alignment.CenterHorizontally) {
                            Icon(
                                imageVector = Icons.Default.DateRange,
                                contentDescription = null,
                                tint = LoginSecondaryText,
                                modifier = Modifier.size(36.dp)
                            )
                            Spacer(modifier = Modifier.height(8.dp))
                            Text(
                                text = "Yaklaşan randevunuz bulunmamaktadır.",
                                fontSize = 13.sp,
                                color = LoginSecondaryText,
                                textAlign = TextAlign.Center
                            )
                        }
                    }
                }
            }

            Spacer(modifier = Modifier.height(16.dp))

            // 4. Card: Müsaitlik Yönetimi
            Surface(
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(24.dp),
                color = PremiumWhiteCard,
                shadowElevation = 2.dp,
                border = BorderStroke(1.dp, SoftMintAccent.copy(alpha = 0.5f))
            ) {
                Column(
                    modifier = Modifier.padding(20.dp),
                    horizontalAlignment = Alignment.Start
                ) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(
                            imageVector = Icons.Default.Build,
                            contentDescription = null,
                            tint = DarkTealPrimary,
                            modifier = Modifier.size(20.dp)
                        )
                        Spacer(modifier = Modifier.width(8.dp))
                        Text(
                            text = "Müsaitlik Yönetimi",
                            fontSize = 14.sp,
                            fontWeight = FontWeight.Bold,
                            color = LoginTextColor
                        )
                    }
                    Spacer(modifier = Modifier.height(12.dp))
                    Text(
                        text = "Müsait saatlerinizi belirlemek ve düzenlemek için yakında bu alandan erişim sağlayabileceksiniz.",
                        fontSize = 13.sp,
                        color = LoginSecondaryText,
                        lineHeight = 18.sp
                    )
                }
            }

            Spacer(modifier = Modifier.height(28.dp))

            // Logout Button
            OutlinedButton(
                onClick = {
                    scope.launch {
                        tokenManager.clearAuthData()
                        ProfileViewModel.clearCache()
                        navController.navigate("auth_graph") {
                            popUpTo("psychologist_graph") { inclusive = true }
                            launchSingleTop = true
                        }
                    }
                },
                modifier = Modifier
                    .fillMaxWidth()
                    .height(56.dp),
                shape = RoundedCornerShape(16.dp),
                border = BorderStroke(1.5.dp, Color(0xFFDC2626)),
                colors = ButtonDefaults.outlinedButtonColors(
                    contentColor = Color(0xFFDC2626)
                )
            ) {
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.Center
                ) {
                    Icon(
                        imageVector = Icons.AutoMirrored.Filled.ExitToApp,
                        contentDescription = null,
                        tint = Color(0xFFDC2626),
                        modifier = Modifier.size(20.dp)
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    Text(
                        text = "Oturumu Kapat",
                        fontWeight = FontWeight.Bold,
                        fontSize = 16.sp
                    )
                }
            }

            Spacer(modifier = Modifier.height(28.dp))
        }
    }
}
