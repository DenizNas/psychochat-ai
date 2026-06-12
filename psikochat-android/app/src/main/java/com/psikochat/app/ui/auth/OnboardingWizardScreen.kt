package com.psikochat.app.ui.auth

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowLeft
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Favorite
import androidx.compose.material.icons.filled.Warning
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
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun OnboardingWizardScreen(navController: NavController, tokenManager: TokenManager) {
    val api = RetrofitClient.create(tokenManager)
    val repository = ProfileRepository(api)
    val factory = object : ViewModelProvider.Factory {
        override fun <T : ViewModel> create(modelClass: Class<T>): T {
            @Suppress("UNCHECKED_CAST")
            return ProfileViewModel(repository, tokenManager) as T
        }
    }
    val viewModel: ProfileViewModel = viewModel(factory = factory)
    val updateState by viewModel.updateState.collectAsState()
    val scope = rememberCoroutineScope()

    var currentStep by remember { mutableIntStateOf(1) }

    // Form inputs state
    var displayName by remember { mutableStateOf("") }
    var bio by remember { mutableStateOf("") }
    var responseStyle by remember { mutableStateOf("supportive") }
    var answerLength by remember { mutableStateOf("medium") }
    
    // Step 5: Wellness goals (kept in local state, no backend field model)
    var selectedGoals by remember { mutableStateOf(setOf<String>()) }

    // Validation checks
    val isDisplayNameValidi = displayName.trim().isNotEmpty() && displayName.length <= 50
    val isBioValidi = bio.length <= 250
    val isStep2Valid = isDisplayNameValidi && isBioValidi

    val scrollState = rememberScrollState()

    // Handlers
    val handleSkip = {
        scope.launch {
            tokenManager.setOnboardingCompleted(true)
            navController.navigate("main_graph") {
                popUpTo("onboarding_wizard") { inclusive = true }
            }
        }
    }

    val handleFinish = {
        viewModel.updateProfile(
            displayName = displayName.trim(),
            bio = bio.trim(),
            language = "tr",
            style = responseStyle,
            answerLength = answerLength
        )
    }

    LaunchedEffect(updateState) {
        if (updateState is Resource.Success) {
            tokenManager.setOnboardingCompleted(true)
            viewModel.clearUpdateState()
            navController.navigate("main_graph") {
                popUpTo("onboarding_wizard") { inclusive = true }
            }
        }
    }

    Scaffold(
        topBar = {
            CenterAlignedTopAppBar(
                title = {
                    Text(
                        text = "Kişiselleştirme",
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Bold,
                        color = LoginTextColor
                    )
                },
                actions = {
                    // Skip (Geç) Button is always safe and completes onboarding locally
                    TextButton(onClick = { handleSkip() }) {
                        Text(
                            text = "Geç",
                            color = DarkTealPrimary,
                            fontWeight = FontWeight.Bold,
                            fontSize = 15.sp
                        )
                    }
                },
                colors = TopAppBarDefaults.centerAlignedTopAppBarColors(
                    containerColor = Color.Transparent
                )
            )
        },
        containerColor = SoftMintBackground
    ) { padding ->
        Box(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
        ) {
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .verticalScroll(scrollState)
                    .padding(horizontal = 24.dp, vertical = 8.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.SpaceBetween
            ) {
                // Top Progress indicator
                Column(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalAlignment = Alignment.CenterHorizontally
                ) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text(
                            text = "Adım $currentStep / 5",
                            color = SecondaryTealText,
                            style = MaterialTheme.typography.bodyMedium,
                            fontWeight = FontWeight.Bold
                        )
                        Text(
                            text = "%${(currentStep * 20)} Tamamlandı",
                            color = DarkTealPrimary,
                            style = MaterialTheme.typography.bodySmall,
                            fontWeight = FontWeight.Bold
                        )
                    }
                    Spacer(modifier = Modifier.height(8.dp))
                    LinearProgressIndicator(
                        progress = { currentStep / 5f },
                        modifier = Modifier
                            .fillMaxWidth()
                            .height(6.dp)
                            .clip(RoundedCornerShape(3.dp)),
                        color = DarkTealPrimary,
                        trackColor = SoftMintAccent
                    )
                }

                Spacer(modifier = Modifier.height(24.dp))

                // Content block based on currentStep
                Box(
                    modifier = Modifier
                        .weight(1f)
                        .fillMaxWidth(),
                    contentAlignment = Alignment.TopCenter
                ) {
                    when (currentStep) {
                        1 -> WelcomeStep()
                        2 -> ProfileSetupStep(
                            displayName = displayName,
                            onDisplayNameChange = { displayName = it },
                            bio = bio,
                            onBioChange = { bio = it },
                            isNameValid = isDisplayNameValidi,
                            isBioValid = isBioValidi
                        )
                        3 -> ResponseStyleStep(
                            selectedStyle = responseStyle,
                            onStyleSelected = { responseStyle = it }
                        )
                        4 -> AnswerLengthStep(
                            selectedLength = answerLength,
                            onLengthSelected = { answerLength = it }
                        )
                        5 -> WellnessGoalsStep(
                            selectedGoals = selectedGoals,
                            onGoalToggled = { goal ->
                                selectedGoals = if (selectedGoals.contains(goal)) {
                                    selectedGoals - goal
                                } else {
                                    selectedGoals + goal
                                }
                            }
                        )
                    }
                }

                Spacer(modifier = Modifier.height(24.dp))

                // Error State Card (Sync fail helper)
                if (updateState is Resource.Error) {
                    Surface(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(bottom = 16.dp),
                        shape = RoundedCornerShape(16.dp),
                        color = MildAlertBg,
                        border = BorderStroke(1.dp, MildAlertText.copy(alpha = 0.3f))
                    ) {
                        Row(
                            modifier = Modifier.padding(16.dp),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Icon(
                                imageVector = Icons.Default.Warning,
                                contentDescription = "Hata",
                                tint = MildAlertText,
                                modifier = Modifier.size(24.dp)
                            )
                            Spacer(modifier = Modifier.width(12.dp))
                            Column(modifier = Modifier.weight(1f)) {
                                Text(
                                    text = "Kayıt Başarısız Oldu",
                                    color = MildAlertText,
                                    fontWeight = FontWeight.Bold,
                                    style = MaterialTheme.typography.bodyMedium
                                )
                                Text(
                                    text = (updateState as Resource.Error).message ?: "Profil bilgileri güncellenemedi. Lütfen tekrar deneyin.",
                                    color = MildAlertText,
                                    style = MaterialTheme.typography.bodySmall
                                )
                            }
                        }
                    }
                }

                // Bottom Action buttons row
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(bottom = 16.dp),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    if (currentStep > 1) {
                        OutlinedButton(
                            onClick = { currentStep -= 1 },
                            modifier = Modifier
                                .weight(1f)
                                .height(56.dp),
                            shape = RoundedCornerShape(16.dp),
                            border = BorderStroke(1.5.dp, SoftMintAccent),
                            colors = ButtonDefaults.outlinedButtonColors(
                                contentColor = LoginTextColor
                            ),
                            enabled = updateState !is Resource.Loading
                        ) {
                            Icon(
                                imageVector = Icons.AutoMirrored.Filled.KeyboardArrowLeft,
                                contentDescription = "Geri"
                            )
                            Spacer(modifier = Modifier.width(4.dp))
                            Text("Geri", fontWeight = FontWeight.Bold, fontSize = 16.sp)
                        }
                        Spacer(modifier = Modifier.width(12.dp))
                    }

                    Button(
                        onClick = {
                            if (currentStep < 5) {
                                currentStep += 1
                            } else {
                                handleFinish()
                            }
                        },
                        modifier = Modifier
                            .weight(if (currentStep > 1) 1.5f else 1f)
                            .height(56.dp),
                        shape = RoundedCornerShape(16.dp),
                        colors = ButtonDefaults.buttonColors(
                            containerColor = DarkTealPrimary,
                            contentColor = Color.White
                        ),
                        enabled = (currentStep != 2 || isStep2Valid) && updateState !is Resource.Loading
                    ) {
                        Text(
                            text = if (currentStep == 5) "Tamamla" else "İleri",
                            fontWeight = FontWeight.Bold,
                            color = Color.White,
                            fontSize = 16.sp
                        )
                    }
                }
            }

            // Spinner Loading Screen
            if (updateState is Resource.Loading) {
                Box(
                    modifier = Modifier
                        .fillMaxSize()
                        .background(Color.Black.copy(alpha = 0.4f))
                        .clickable(enabled = false) {},
                    contentAlignment = Alignment.Center
                ) {
                    Card(
                        shape = RoundedCornerShape(24.dp),
                        colors = CardDefaults.cardColors(containerColor = PremiumWhiteCard),
                        elevation = CardDefaults.cardElevation(8.dp)
                    ) {
                        Column(
                            modifier = Modifier.padding(32.dp),
                            horizontalAlignment = Alignment.CenterHorizontally
                        ) {
                            CircularProgressIndicator(color = DarkTealPrimary, strokeWidth = 3.dp)
                            Spacer(modifier = Modifier.height(16.dp))
                            Text(
                                text = "Bilgileriniz Kaydediliyor...",
                                color = LoginTextColor,
                                fontWeight = FontWeight.Bold,
                                style = MaterialTheme.typography.bodyMedium
                            )
                        }
                    }
                }
            }
        }
    }
}

@Composable
fun WelcomeStep() {
    Column(
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
        modifier = Modifier.padding(vertical = 16.dp)
    ) {
        Spacer(modifier = Modifier.height(24.dp))
        // Brand Emblem
        Box(
            modifier = Modifier
                .size(108.dp)
                .clip(CircleShape)
                .background(SoftMintAccent),
            contentAlignment = Alignment.Center
        ) {
            Icon(
                imageVector = Icons.Default.Favorite,
                contentDescription = null,
                modifier = Modifier.size(56.dp),
                tint = DarkTealPrimary
            )
        }

        Spacer(modifier = Modifier.height(28.dp))

        Text(
            text = "PsikoChat'e hoş geldin",
            style = MaterialTheme.typography.headlineMedium.copy(
                fontWeight = FontWeight.ExtraBold,
                fontSize = 28.sp
            ),
            color = LoginTextColor,
            textAlign = TextAlign.Center
        )

        Spacer(modifier = Modifier.height(16.dp))

        Text(
            text = "Bireysel zihinsel sağlık yolculuğunuzda size eşlik edecek yapay zeka asistanınızı kişiselleştirelim.",
            style = MaterialTheme.typography.bodyLarge.copy(
                fontWeight = FontWeight.Medium,
                lineHeight = 24.sp
            ),
            color = SecondaryTealText,
            textAlign = TextAlign.Center,
            modifier = Modifier.padding(horizontal = 8.dp)
        )

        Spacer(modifier = Modifier.height(28.dp))

        Surface(
            shape = RoundedCornerShape(20.dp),
            color = PremiumWhiteCard,
            border = BorderStroke(1.dp, SoftMintAccent.copy(alpha = 0.5f))
        ) {
            Row(
                modifier = Modifier.padding(20.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Icon(
                    imageVector = Icons.Default.Favorite,
                    contentDescription = null,
                    tint = DarkTealPrimary,
                    modifier = Modifier.size(28.dp)
                )
                Spacer(modifier = Modifier.width(16.dp))
                Text(
                    text = "Bu kısa kurulum, PsikoChat AI'ın size en uygun dilde, üslupta ve tonda yanıt vermesini sağlayacaktır.",
                    style = MaterialTheme.typography.bodyMedium,
                    color = LoginTextColor,
                    lineHeight = 20.sp,
                    modifier = Modifier.weight(1f)
                )
            }
        }
    }
}

@Composable
fun ProfileSetupStep(
    displayName: String,
    onDisplayNameChange: (String) -> Unit,
    bio: String,
    onBioChange: (String) -> Unit,
    isNameValid: Boolean,
    isBioValid: Boolean
) {
    Column(
        horizontalAlignment = Alignment.Start,
        modifier = Modifier.fillMaxWidth()
    ) {
        Text(
            text = "Profilini Ayarla",
            style = MaterialTheme.typography.titleLarge.copy(
                fontWeight = FontWeight.Bold,
                fontSize = 22.sp
            ),
            color = LoginTextColor
        )
        Text(
            text = "Asistanınızın size nasıl hitap etmesini istersiniz? Kendiniz hakkında kısa bir bilgi ekleyebilirsiniz.",
            style = MaterialTheme.typography.bodyMedium,
            color = SecondaryTealText,
            modifier = Modifier.padding(top = 4.dp, bottom = 24.dp)
        )

        Surface(
            shape = RoundedCornerShape(24.dp),
            color = PremiumWhiteCard,
            border = BorderStroke(1.dp, SoftMintAccent.copy(alpha = 0.5f)),
            modifier = Modifier.fillMaxWidth()
        ) {
            Column(
                modifier = Modifier.padding(24.dp)
            ) {
                // Display Name Input
                Text(
                    text = "Görünür Ad *",
                    style = MaterialTheme.typography.labelMedium,
                    fontWeight = FontWeight.Bold,
                    color = LoginTextColor
                )
                Spacer(modifier = Modifier.height(8.dp))
                OutlinedTextField(
                    value = displayName,
                    onValueChange = onDisplayNameChange,
                    placeholder = { Text("Örn. Ahmet", color = SecondaryTealText) },
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(14.dp),
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedContainerColor = SoftMintLight,
                        unfocusedContainerColor = SoftMintLight,
                        focusedBorderColor = DarkTealPrimary,
                        unfocusedBorderColor = SoftMintAccent,
                        cursorColor = DarkTealPrimary
                    ),
                    singleLine = true
                )
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(top = 4.dp),
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {
                    Text(
                        text = if (!isNameValid && displayName.trim().isEmpty()) "Ad alanı boş bırakılamaz" else "",
                        color = MildAlertText,
                        style = MaterialTheme.typography.labelSmall
                    )
                    Text(
                        text = "${displayName.length}/50",
                        color = if (displayName.length > 50) MildAlertText else SecondaryTealText,
                        style = MaterialTheme.typography.labelSmall
                    )
                }

                Spacer(modifier = Modifier.height(20.dp))

                // Bio Input
                Text(
                    text = "Hakkımda (Biyografi)",
                    style = MaterialTheme.typography.labelMedium,
                    fontWeight = FontWeight.Bold,
                    color = LoginTextColor
                )
                Spacer(modifier = Modifier.height(8.dp))
                OutlinedTextField(
                    value = bio,
                    onValueChange = onBioChange,
                    placeholder = { Text("Kendinizden kısaca bahsedin...", color = SecondaryTealText) },
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(112.dp),
                    shape = RoundedCornerShape(14.dp),
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedContainerColor = SoftMintLight,
                        unfocusedContainerColor = SoftMintLight,
                        focusedBorderColor = DarkTealPrimary,
                        unfocusedBorderColor = SoftMintAccent,
                        cursorColor = DarkTealPrimary
                    ),
                    maxLines = 4
                )
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(top = 4.dp),
                    horizontalArrangement = Arrangement.End
                ) {
                    Text(
                        text = "${bio.length}/250",
                        color = if (!isBioValid) MildAlertText else SecondaryTealText,
                        style = MaterialTheme.typography.labelSmall
                    )
                }
            }
        }
    }
}

@Composable
fun ResponseStyleStep(
    selectedStyle: String,
    onStyleSelected: (String) -> Unit
) {
    Column(
        horizontalAlignment = Alignment.Start,
        modifier = Modifier.fillMaxWidth()
    ) {
        Text(
            text = "Yapay Zeka Cevap Stili",
            style = MaterialTheme.typography.titleLarge.copy(
                fontWeight = FontWeight.Bold,
                fontSize = 22.sp
            ),
            color = LoginTextColor
        )
        Text(
            text = "Yapay zekanın sizinle konuşurken takınacağı ses tonunu belirleyin.",
            style = MaterialTheme.typography.bodyMedium,
            color = SecondaryTealText,
            modifier = Modifier.padding(top = 4.dp, bottom = 24.dp)
        )

        Column(
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            listOf(
                Triple("supportive", "Destekleyici", "Daha motive edici ve güven veren sakin yanıtlar."),
                Triple("empathetic", "Empatik", "Duygularınızı derinlemesine anlayan ve yansıtan yanıtlar."),
                Triple("direct", "Direkt", "Daha kısa, net, doğrudan ve çözüm odaklı yanıtlar.")
            ).forEach { (code, title, desc) ->
                val isSelected = selectedStyle == code
                Surface(
                    shape = RoundedCornerShape(20.dp),
                    color = if (isSelected) SoftMintLight else PremiumWhiteCard,
                    border = BorderStroke(
                        width = if (isSelected) 2.dp else 1.dp,
                        color = if (isSelected) DarkTealPrimary else SoftMintAccent.copy(alpha = 0.5f)
                    ),
                    modifier = Modifier
                        .fillMaxWidth()
                        .clickable { onStyleSelected(code) }
                ) {
                    Row(
                        modifier = Modifier.padding(20.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        RadioButton(
                            selected = isSelected,
                            onClick = { onStyleSelected(code) }
                        )
                        Spacer(modifier = Modifier.width(16.dp))
                        Column {
                            Text(
                                text = title,
                                style = MaterialTheme.typography.bodyLarge,
                                fontWeight = FontWeight.Bold,
                                color = LoginTextColor
                            )
                            Text(
                                text = desc,
                                style = MaterialTheme.typography.bodySmall,
                                color = SecondaryTealText,
                                lineHeight = 16.sp
                            )
                        }
                    }
                }
            }
        }
    }
}

@Composable
fun AnswerLengthStep(
    selectedLength: String,
    onLengthSelected: (String) -> Unit
) {
    Column(
        horizontalAlignment = Alignment.Start,
        modifier = Modifier.fillMaxWidth()
    ) {
        Text(
            text = "Yanıt Uzunluğu",
            style = MaterialTheme.typography.titleLarge.copy(
                fontWeight = FontWeight.Bold,
                fontSize = 22.sp
            ),
            color = LoginTextColor
        )
        Text(
            text = "PsikoChat AI asistanınızın cevaplarının uzunluğunu seçin.",
            style = MaterialTheme.typography.bodyMedium,
            color = SecondaryTealText,
            modifier = Modifier.padding(top = 4.dp, bottom = 24.dp)
        )

        Column(
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            listOf(
                Triple("short", "Kısa", "1-2 cümlelik kısa ve öz yanıtlar."),
                Triple("medium", "Orta", "3-5 cümlelik dengeli ve açıklayıcı yanıtlar."),
                Triple("detailed", "Detaylı", "Kapsamlı, derinlemesine ve analitik yanıtlar.")
            ).forEach { (code, title, desc) ->
                val isSelected = selectedLength == code
                Surface(
                    shape = RoundedCornerShape(20.dp),
                    color = if (isSelected) SoftMintLight else PremiumWhiteCard,
                    border = BorderStroke(
                        width = if (isSelected) 2.dp else 1.dp,
                        color = if (isSelected) DarkTealPrimary else SoftMintAccent.copy(alpha = 0.5f)
                    ),
                    modifier = Modifier
                        .fillMaxWidth()
                        .clickable { onLengthSelected(code) }
                ) {
                    Row(
                        modifier = Modifier.padding(20.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        RadioButton(
                            selected = isSelected,
                            onClick = { onLengthSelected(code) }
                        )
                        Spacer(modifier = Modifier.width(16.dp))
                        Column {
                            Text(
                                text = title,
                                style = MaterialTheme.typography.bodyLarge,
                                fontWeight = FontWeight.Bold,
                                color = LoginTextColor
                            )
                            Text(
                                text = desc,
                                style = MaterialTheme.typography.bodySmall,
                                color = SecondaryTealText,
                                lineHeight = 16.sp
                            )
                        }
                    }
                }
            }
        }
    }
}

@Composable
fun WellnessGoalsStep(
    selectedGoals: Set<String>,
    onGoalToggled: (String) -> Unit
) {
    Column(
        horizontalAlignment = Alignment.Start,
        modifier = Modifier.fillMaxWidth()
    ) {
        Text(
            text = "İyi Oluş (Wellness) Hedeflerin",
            style = MaterialTheme.typography.titleLarge.copy(
                fontWeight = FontWeight.Bold,
                fontSize = 22.sp
            ),
            color = LoginTextColor
        )
        Text(
            text = "Zihinsel sağlık yolculuğunuzda odaklanmak istediğiniz wellness alanlarını seçin (Birden fazla seçebilirsiniz).",
            style = MaterialTheme.typography.bodyMedium,
            color = SecondaryTealText,
            modifier = Modifier.padding(top = 4.dp, bottom = 24.dp)
        )

        // TODO: Save to backend database once wellness goals API models and tables are introduced. Currently persisted in local UI memory context only.
        Column(
            verticalArrangement = Arrangement.spacedBy(10.dp)
        ) {
            listOf(
                "Kaygımı yönetmek",
                "Daha iyi uyumak",
                "Duygularımı takip etmek",
                "Stresimi azaltmak",
                "Düzenli günlük tutmak"
            ).forEach { goal ->
                val isSelected = selectedGoals.contains(goal)
                Surface(
                    shape = RoundedCornerShape(16.dp),
                    color = if (isSelected) SoftMintLight else PremiumWhiteCard,
                    border = BorderStroke(
                        width = if (isSelected) 1.5.dp else 1.dp,
                        color = if (isSelected) DarkTealAccent else SoftMintAccent.copy(alpha = 0.5f)
                    ),
                    modifier = Modifier
                        .fillMaxWidth()
                        .clickable { onGoalToggled(goal) }
                ) {
                    Row(
                        modifier = Modifier.padding(16.dp),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.SpaceBetween
                    ) {
                        Text(
                            text = goal,
                            style = MaterialTheme.typography.bodyMedium,
                            fontWeight = FontWeight.Bold,
                            color = LoginTextColor,
                            modifier = Modifier.weight(1f)
                        )
                        Checkbox(
                            checked = isSelected,
                            onCheckedChange = { onGoalToggled(goal) },
                            colors = CheckboxDefaults.colors(
                                checkedColor = DarkTealPrimary,
                                uncheckedColor = SecondaryTealText,
                                checkmarkColor = Color.White
                            )
                        )
                    }
                }
            }
        }
    }
}
