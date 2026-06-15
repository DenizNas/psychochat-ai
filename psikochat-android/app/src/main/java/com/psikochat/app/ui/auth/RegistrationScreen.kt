package com.psikochat.app.ui.auth

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowLeft
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.graphics.vector.path
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
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
import androidx.compose.foundation.Image
import androidx.compose.ui.res.painterResource
import com.psikochat.app.R

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun RegistrationScreen(navController: NavController, tokenManager: TokenManager) {
    val api = RetrofitClient.create(tokenManager)
    val repo = AuthRepository(api)
    val factory = object : ViewModelProvider.Factory {
        override fun <T : ViewModel> create(modelClass: Class<T>): T {
            @Suppress("UNCHECKED_CAST")
            return AuthViewModel(repo, tokenManager) as T
        }
    }
    val viewModel: AuthViewModel = viewModel(factory = factory)

    var fullName by remember { mutableStateOf("") }
    var email by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    var confirmPassword by remember { mutableStateOf("") }
    var passwordVisible by remember { mutableStateOf(false) }
    var confirmPasswordVisible by remember { mutableStateOf(false) }
    var validationError by remember { mutableStateOf<String?>(null) }
    val authState by viewModel.authState.collectAsState()
    
    val scrollState = rememberScrollState()
    val context = androidx.compose.ui.platform.LocalContext.current

    var accountType by remember { mutableStateOf("user") }
    var title by remember { mutableStateOf("") }
    var specialty by remember { mutableStateOf("") }
    var bio by remember { mutableStateOf("") }
    var showPsychologistSuccessDialog by remember { mutableStateOf(false) }

    if (authState is Resource.Success && (authState.data == true)) {
        if (accountType == "psychologist") {
            LaunchedEffect(Unit) {
                showPsychologistSuccessDialog = true
            }
        } else {
            LaunchedEffect(Unit) {
                viewModel.resetState()
                android.widget.Toast.makeText(context, "Kayıt başarılı", android.widget.Toast.LENGTH_SHORT).show()
                navController.navigate("login") {
                    popUpTo("register") { inclusive = true }
                    launchSingleTop = true
                }
            }
        }
    }

    Scaffold(
        topBar = {
            CenterAlignedTopAppBar(
                title = {
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.Center
                    ) {
                        Image(
                            painter = painterResource(id = R.drawable.ic_logo),
                            contentDescription = null,
                            modifier = Modifier
                                .size(20.dp)
                                .clip(CircleShape),
                            contentScale = androidx.compose.ui.layout.ContentScale.Crop
                        )
                        Spacer(modifier = Modifier.width(6.dp))
                        Text(
                            "PsikoChat",
                            style = MaterialTheme.typography.titleMedium,
                            fontWeight = FontWeight.Bold,
                            color = LoginTextColor
                        )
                    }
                },
                navigationIcon = {
                    IconButton(onClick = { navController.popBackStack() }) {
                        Icon(
                            imageVector = Icons.AutoMirrored.Filled.KeyboardArrowLeft,
                            contentDescription = "Geri",
                            tint = LoginTextColor
                        )
                    }
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
            Spacer(modifier = Modifier.height(28.dp))

            // Premium Brand Emblem
            Image(
                painter = painterResource(id = R.drawable.ic_logo),
                contentDescription = null,
                modifier = Modifier.size(120.dp),
                contentScale = androidx.compose.ui.layout.ContentScale.Fit
            )

            Spacer(modifier = Modifier.height(12.dp))

            Text(
                text = "PsikoChat",
                style = MaterialTheme.typography.headlineMedium.copy(
                    fontWeight = FontWeight.ExtraBold,
                    fontSize = 30.sp
                ),
                color = LoginTextColor,
                textAlign = TextAlign.Center
            )

            Spacer(modifier = Modifier.height(8.dp))

            Text(
                text = "Kişisel Zihinsel Asistanınız",
                style = MaterialTheme.typography.bodyLarge.copy(
                    fontWeight = FontWeight.Medium,
                    lineHeight = 22.sp,
                    letterSpacing = 0.15.sp
                ),
                color = LoginSecondaryText,
                textAlign = TextAlign.Center
            )

            Spacer(modifier = Modifier.height(28.dp))

            // Floating Premium Card
            Surface(
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(28.dp),
                color = PremiumWhiteCard,
                tonalElevation = 2.dp,
                border = BorderStroke(1.dp, SoftMintAccent.copy(alpha = 0.5f))
            ) {
                Column(
                    modifier = Modifier.padding(24.dp),
                    horizontalAlignment = Alignment.CenterHorizontally
                ) {
                    Text(
                        text = "Kayıt Ol",
                        style = MaterialTheme.typography.titleLarge.copy(
                            fontWeight = FontWeight.Bold
                        ),
                        color = LoginTextColor,
                        modifier = Modifier.align(Alignment.Start)
                    )

                    Text(
                        text = "Aramıza katılın ve zihinsel sağlık yolculuğunuza başlayın.",
                        style = MaterialTheme.typography.bodySmall,
                        color = LoginSecondaryText,
                        modifier = Modifier.align(Alignment.Start)
                    )

                    Spacer(modifier = Modifier.height(16.dp))

                    // Account Type Selector
                    Row(
                        modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp),
                        horizontalArrangement = Arrangement.spacedBy(12.dp)
                    ) {
                        listOf("Kullanıcı" to "user", "Psikolog" to "psychologist").forEach { (label, value) ->
                            val isSelected = accountType == value
                            Surface(
                                shape = RoundedCornerShape(16.dp),
                                color = if (isSelected) SoftMintAccent else SoftMintLight,
                                border = BorderStroke(1.dp, if (isSelected) DarkTealPrimary else SoftMintAccent),
                                modifier = Modifier.weight(1f).clickable { accountType = value }
                            ) {
                                Text(
                                    text = label,
                                    color = if (isSelected) DarkTealPrimary else LoginTextColor,
                                    fontWeight = FontWeight.Bold,
                                    textAlign = TextAlign.Center,
                                    modifier = Modifier.padding(vertical = 12.dp)
                                )
                            }
                        }
                    }

                    if (accountType == "psychologist") {
                        Spacer(modifier = Modifier.height(4.dp))
                        Text(
                            text = "Psikolog hesapları onay sürecinden geçer.",
                            style = MaterialTheme.typography.bodySmall.copy(
                                fontWeight = FontWeight.Medium,
                                color = SecondaryTealText
                            ),
                            modifier = Modifier.align(Alignment.Start)
                        )
                    }

                    Spacer(modifier = Modifier.height(16.dp))

                    // Full Name Field
                    OutlinedTextField(
                        value = fullName,
                        onValueChange = { fullName = it; validationError = null },
                        placeholder = { Text("Ad Soyad", color = LoginSecondaryText) },
                        textStyle = TextStyle(color = LoginTextColor),
                        modifier = Modifier.fillMaxWidth(),
                        shape = RoundedCornerShape(16.dp),
                        leadingIcon = {
                            Icon(
                                imageVector = Icons.Default.Person,
                                contentDescription = null,
                                tint = SecondaryTealText
                            )
                        },
                        colors = OutlinedTextFieldDefaults.colors(
                            focusedContainerColor = SoftMintLight,
                            unfocusedContainerColor = SoftMintLight,
                            focusedBorderColor = DarkTealPrimary,
                            unfocusedBorderColor = SoftMintAccent,
                            cursorColor = DarkTealPrimary
                        ),
                        singleLine = true
                    )

                    Spacer(modifier = Modifier.height(12.dp))

                    // Email Field
                    OutlinedTextField(
                        value = email,
                        onValueChange = { email = it; validationError = null },
                        placeholder = { Text("E-posta", color = LoginSecondaryText) },
                        textStyle = TextStyle(color = LoginTextColor),
                        modifier = Modifier.fillMaxWidth(),
                        shape = RoundedCornerShape(16.dp),
                        leadingIcon = {
                            Icon(
                                imageVector = Icons.Default.Email,
                                contentDescription = null,
                                tint = SecondaryTealText
                            )
                        },
                        colors = OutlinedTextFieldDefaults.colors(
                            focusedContainerColor = SoftMintLight,
                            unfocusedContainerColor = SoftMintLight,
                            focusedBorderColor = DarkTealPrimary,
                            unfocusedBorderColor = SoftMintAccent,
                            cursorColor = DarkTealPrimary
                        ),
                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Email),
                        singleLine = true
                    )

                    Spacer(modifier = Modifier.height(12.dp))

                    // Password Field
                    OutlinedTextField(
                        value = password,
                        onValueChange = { password = it; validationError = null },
                        placeholder = { Text("Şifre", color = LoginSecondaryText) },
                        textStyle = TextStyle(color = LoginTextColor),
                        modifier = Modifier.fillMaxWidth(),
                        shape = RoundedCornerShape(16.dp),
                        leadingIcon = {
                            Icon(
                                imageVector = Icons.Default.Lock,
                                contentDescription = null,
                                tint = SecondaryTealText
                            )
                        },
                        trailingIcon = {
                            val icon = if (passwordVisible) VisibilityIcon else VisibilityOffIcon
                            IconButton(onClick = { passwordVisible = !passwordVisible }) {
                                Icon(
                                    imageVector = icon,
                                    contentDescription = if (passwordVisible) "Şifreyi Gizle" else "Şifreyi Göster",
                                    tint = SecondaryTealText,
                                    modifier = Modifier.size(22.dp)
                                )
                            }
                        },
                        visualTransformation = if (passwordVisible) VisualTransformation.None else PasswordVisualTransformation(),
                        colors = OutlinedTextFieldDefaults.colors(
                            focusedContainerColor = SoftMintLight,
                            unfocusedContainerColor = SoftMintLight,
                            focusedBorderColor = DarkTealPrimary,
                            unfocusedBorderColor = SoftMintAccent,
                            cursorColor = DarkTealPrimary
                        ),
                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password),
                        singleLine = true
                    )

                    Spacer(modifier = Modifier.height(12.dp))

                    // Confirm Password Field
                    OutlinedTextField(
                        value = confirmPassword,
                        onValueChange = { confirmPassword = it; validationError = null },
                        placeholder = { Text("Şifre Tekrar", color = LoginSecondaryText) },
                        textStyle = TextStyle(color = LoginTextColor),
                        modifier = Modifier.fillMaxWidth(),
                        shape = RoundedCornerShape(16.dp),
                        leadingIcon = {
                            Icon(
                                imageVector = Icons.Default.Lock,
                                contentDescription = null,
                                tint = SecondaryTealText
                            )
                        },
                        trailingIcon = {
                            val icon = if (confirmPasswordVisible) VisibilityIcon else VisibilityOffIcon
                            IconButton(onClick = { confirmPasswordVisible = !confirmPasswordVisible }) {
                                Icon(
                                    imageVector = icon,
                                    contentDescription = if (confirmPasswordVisible) "Şifreyi Gizle" else "Şifreyi Göster",
                                    tint = SecondaryTealText,
                                    modifier = Modifier.size(22.dp)
                                )
                            }
                        },
                        visualTransformation = if (confirmPasswordVisible) VisualTransformation.None else PasswordVisualTransformation(),
                        colors = OutlinedTextFieldDefaults.colors(
                            focusedContainerColor = SoftMintLight,
                            unfocusedContainerColor = SoftMintLight,
                            focusedBorderColor = DarkTealPrimary,
                            unfocusedBorderColor = SoftMintAccent,
                            cursorColor = DarkTealPrimary
                        ),
                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password),
                        singleLine = true
                    )

                    if (accountType == "psychologist") {
                        Spacer(modifier = Modifier.height(12.dp))

                        // Title Field
                        OutlinedTextField(
                            value = title,
                            onValueChange = { title = it; validationError = null },
                            placeholder = { Text("Unvan (Örn: Uzm. Psk.)", color = LoginSecondaryText) },
                            textStyle = TextStyle(color = LoginTextColor),
                            modifier = Modifier.fillMaxWidth(),
                            shape = RoundedCornerShape(16.dp),
                            leadingIcon = {
                                Icon(
                                    imageVector = Icons.Default.Info,
                                    contentDescription = null,
                                    tint = SecondaryTealText
                                )
                            },
                            colors = OutlinedTextFieldDefaults.colors(
                                focusedContainerColor = SoftMintLight,
                                unfocusedContainerColor = SoftMintLight,
                                focusedBorderColor = DarkTealPrimary,
                                unfocusedBorderColor = SoftMintAccent,
                                cursorColor = DarkTealPrimary
                            ),
                            singleLine = true
                        )

                        Spacer(modifier = Modifier.height(12.dp))

                        // Specialty Field
                        OutlinedTextField(
                            value = specialty,
                            onValueChange = { specialty = it; validationError = null },
                            placeholder = { Text("Uzmanlık Alanı (Örn: Bilişsel Terapi)", color = LoginSecondaryText) },
                            textStyle = TextStyle(color = LoginTextColor),
                            modifier = Modifier.fillMaxWidth(),
                            shape = RoundedCornerShape(16.dp),
                            leadingIcon = {
                                Icon(
                                    imageVector = Icons.Default.Star,
                                    contentDescription = null,
                                    tint = SecondaryTealText
                                )
                            },
                            colors = OutlinedTextFieldDefaults.colors(
                                focusedContainerColor = SoftMintLight,
                                unfocusedContainerColor = SoftMintLight,
                                focusedBorderColor = DarkTealPrimary,
                                unfocusedBorderColor = SoftMintAccent,
                                cursorColor = DarkTealPrimary
                            ),
                            singleLine = true
                        )

                        Spacer(modifier = Modifier.height(12.dp))

                        // Bio Field
                        OutlinedTextField(
                            value = bio,
                            onValueChange = { bio = it; validationError = null },
                            placeholder = { Text("Biyografi (En az 20 karakter)", color = LoginSecondaryText) },
                            textStyle = TextStyle(color = LoginTextColor),
                            modifier = Modifier.fillMaxWidth(),
                            shape = RoundedCornerShape(16.dp),
                            leadingIcon = {
                                Icon(
                                    imageVector = Icons.Default.Edit,
                                    contentDescription = null,
                                    tint = SecondaryTealText
                                )
                            },
                            colors = OutlinedTextFieldDefaults.colors(
                                focusedContainerColor = SoftMintLight,
                                unfocusedContainerColor = SoftMintLight,
                                focusedBorderColor = DarkTealPrimary,
                                unfocusedBorderColor = SoftMintAccent,
                                cursorColor = DarkTealPrimary
                            ),
                            maxLines = 4,
                            minLines = 2
                        )
                    }

                    Spacer(modifier = Modifier.height(16.dp))

                    // Error Warning Banner
                    val displayError = validationError ?: (if (authState is Resource.Error) (authState as Resource.Error).message else null)
                    if (displayError != null) {
                        Surface(
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(bottom = 16.dp),
                            shape = RoundedCornerShape(12.dp),
                            color = MildAlertBg,
                            border = BorderStroke(1.dp, MildAlertText.copy(alpha = 0.3f))
                        ) {
                            Row(
                                modifier = Modifier.padding(12.dp),
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Icon(
                                    imageVector = Icons.Default.Warning,
                                    contentDescription = "Hata",
                                    tint = MildAlertText,
                                    modifier = Modifier.size(20.dp)
                                )
                                Spacer(modifier = Modifier.width(8.dp))
                                Text(
                                    text = displayError,
                                    color = MildAlertText,
                                    style = MaterialTheme.typography.bodyMedium.copy(
                                        fontWeight = FontWeight.Medium
                                    )
                                )
                            }
                        }
                    }

                    // Register Button
                    Button(
                        onClick = {
                            validationError = null
                            if (fullName.isBlank() || email.isBlank() || password.isBlank() || confirmPassword.isBlank()) {
                                validationError = "Lütfen tüm alanları doldurunuz."
                            } else if (!email.contains("@")) {
                                validationError = "Geçersiz e-posta formatı."
                            } else if (password != confirmPassword) {
                                validationError = "Şifreler birbirleriyle eşleşmedi."
                            } else if (accountType == "psychologist" && (title.isBlank() || specialty.isBlank() || bio.isBlank())) {
                                validationError = "Lütfen tüm alanları doldurunuz."
                            } else if (accountType == "psychologist" && bio.length < 20) {
                                validationError = "Biyografi en az 20 karakter uzunluğunda olmalıdır."
                            } else {
                                if (accountType == "psychologist") {
                                    viewModel.register(fullName, email, password, "psychologist", title, specialty, bio)
                                } else {
                                    viewModel.register(fullName, email, password, "user")
                                }
                            }
                        },
                        modifier = Modifier
                            .fillMaxWidth()
                            .height(56.dp),
                        shape = RoundedCornerShape(16.dp),
                        colors = ButtonDefaults.buttonColors(
                            containerColor = DarkTealPrimary,
                            contentColor = Color.White
                        ),
                        enabled = authState !is Resource.Loading
                    ) {
                        if (authState is Resource.Loading) {
                            CircularProgressIndicator(
                                color = Color.White,
                                modifier = Modifier.size(24.dp),
                                strokeWidth = 2.dp
                            )
                        } else {
                            Text(
                                "KAYIT OL",
                                color = Color.White,
                                fontWeight = FontWeight.Bold,
                                fontSize = 16.sp,
                                letterSpacing = 1.sp
                            )
                        }
                    }
                }
            }

            Spacer(modifier = Modifier.height(24.dp))

            // Navigation to Login Screen
            Row(
                modifier = Modifier.padding(bottom = 24.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = "Zaten hesabınız var mı? ",
                    color = LoginSecondaryText,
                    style = MaterialTheme.typography.bodyMedium
                )
                Text(
                    text = "Giriş Yap",
                    color = DarkTealPrimary,
                    fontWeight = FontWeight.Bold,
                    style = MaterialTheme.typography.bodyMedium,
                    modifier = Modifier.clickable { navController.popBackStack() }
                )
            }
        }
    }

    if (showPsychologistSuccessDialog) {
        AlertDialog(
            onDismissRequest = { },
            title = { Text("Kayıt Başarılı", fontWeight = FontWeight.Bold, color = LoginTextColor) },
            text = {
                Text(
                    "Psikolog hesabınız oluşturuldu. Onay sürecinden sonra giriş yapabilirsiniz.",
                    color = LoginTextColor
                )
            },
            confirmButton = {
                Button(
                    onClick = {
                        showPsychologistSuccessDialog = false
                        viewModel.resetState()
                        navController.navigate("login") {
                            popUpTo("register") { inclusive = true }
                            launchSingleTop = true
                        }
                    },
                    colors = ButtonDefaults.buttonColors(containerColor = DarkTealPrimary)
                ) {
                    Text("Tamam", color = Color.White)
                }
            }
        )
    }
}
