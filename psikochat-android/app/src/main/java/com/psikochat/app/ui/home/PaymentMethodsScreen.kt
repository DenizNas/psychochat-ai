package com.psikochat.app.ui.home

import android.content.Intent
import android.net.Uri
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowLeft
import androidx.compose.material.icons.filled.Info
import androidx.compose.material.icons.filled.Lock
import androidx.compose.material.icons.filled.Star
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavController
import com.psikochat.app.data.api.RetrofitClient
import com.psikochat.app.data.local.TokenManager
import com.psikochat.app.data.repository.SubscriptionRepository
import com.psikochat.app.ui.components.PremiumButton
import com.psikochat.app.ui.components.PremiumCard
import com.psikochat.app.ui.theme.*

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun PaymentMethodsScreen(
    navController: NavController,
    tokenManager: TokenManager,
    paymentResult: String? = null
) {
    val context = LocalContext.current
    val api = remember(tokenManager) { RetrofitClient.create(tokenManager) }
    val repository = remember(api) { SubscriptionRepository(api) }
    val factory = remember(repository) {
        object : ViewModelProvider.Factory {
            @Suppress("UNCHECKED_CAST")
            override fun <T : ViewModel> create(modelClass: Class<T>): T {
                return PaymentMethodsViewModel(repository) as T
            }
        }
    }
    val viewModel: PaymentMethodsViewModel = viewModel(factory = factory)

    val subscriptionFactory = remember(repository) {
        object : ViewModelProvider.Factory {
            @Suppress("UNCHECKED_CAST")
            override fun <T : ViewModel> create(modelClass: Class<T>): T {
                return SubscriptionViewModel(repository) as T
            }
        }
    }
    val subscriptionViewModel: SubscriptionViewModel = viewModel(factory = subscriptionFactory)
    val isPremiumUser by subscriptionViewModel.isPremium.collectAsState()

    val plans by viewModel.plans.collectAsState()
    val currentSubscription by viewModel.currentSubscription.collectAsState()
    val paymentHistory by viewModel.paymentHistory.collectAsState()
    val isLoading by viewModel.isLoading.collectAsState()
    val errorMessage by viewModel.errorMessage.collectAsState()
    val checkoutUrlToOpen by viewModel.checkoutUrlToOpen.collectAsState()
    val paymentReturnMessage by viewModel.paymentReturnMessage.collectAsState()

    val scrollState = rememberScrollState()
    var showErrorDialog by remember { mutableStateOf<String?>(null) }
    var wasCheckoutLaunched by remember { mutableStateOf(false) }

    val lifecycleOwner = androidx.compose.ui.platform.LocalLifecycleOwner.current
    DisposableEffect(lifecycleOwner) {
        val observer = LifecycleEventObserver { _, event ->
            if (event == Lifecycle.Event.ON_RESUME) {
                if (wasCheckoutLaunched) {
                    viewModel.refreshAfterPaymentReturn()
                    subscriptionViewModel.refreshSubscription()
                    wasCheckoutLaunched = false
                } else {
                    viewModel.loadPaymentData()
                    subscriptionViewModel.refreshSubscription()
                }
            }
        }
        lifecycleOwner.lifecycle.addObserver(observer)
        onDispose {
            lifecycleOwner.lifecycle.removeObserver(observer)
        }
    }

    LaunchedEffect(paymentResult) {
        if (!paymentResult.isNullOrEmpty()) {
            viewModel.refreshAfterPaymentReturn()
            subscriptionViewModel.refreshSubscription()
        }
    }

    LaunchedEffect(checkoutUrlToOpen) {
        checkoutUrlToOpen?.let { url ->
            if (url.isNotEmpty()) {
                val intent = Intent(Intent.ACTION_VIEW, Uri.parse(url))
                context.startActivity(intent)
                viewModel.clearCheckoutUrl()
                wasCheckoutLaunched = true
            }
        }
    }

    LaunchedEffect(errorMessage) {
        if (errorMessage != null && plans.isNotEmpty()) {
            showErrorDialog = errorMessage
        }
    }

    Scaffold(
        topBar = {
            CenterAlignedTopAppBar(
                title = {
                    Text(
                        "Ödeme Yöntemleri",
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Bold,
                        color = LoginTextColor
                    )
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
        if (isLoading && plans.isEmpty()) {
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(padding),
                contentAlignment = Alignment.Center
            ) {
                CircularProgressIndicator(color = DarkTealPrimary)
            }
        } else if (plans.isEmpty() && errorMessage != null) {
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(padding)
                    .padding(horizontal = 24.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.Center
            ) {
                Icon(
                    imageVector = Icons.Default.Info,
                    contentDescription = null,
                    tint = Color(0xFFFF6B6B),
                    modifier = Modifier.size(56.dp)
                )
                Spacer(modifier = Modifier.height(16.dp))
                Text(
                    text = errorMessage ?: "Yükleme hatası",
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold,
                    color = LoginTextColor,
                    textAlign = TextAlign.Center
                )
                Spacer(modifier = Modifier.height(8.dp))
                Text(
                    text = "Abonelik verileri yüklenirken bir hata oluştu. Lütfen bağlantınızı kontrol edip tekrar deneyin.",
                    style = MaterialTheme.typography.bodySmall,
                    color = LoginSecondaryText,
                    textAlign = TextAlign.Center
                )
                Spacer(modifier = Modifier.height(24.dp))
                PremiumButton(
                    onClick = { viewModel.loadPaymentData() },
                    modifier = Modifier.fillMaxWidth(),
                    containerColor = DarkTealPrimary,
                    contentColor = Color.White
                ) {
                    Text("Tekrar Dene", fontWeight = FontWeight.Bold)
                }
            }
        } else {
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

                // Premium Active Success Banner
                if (isPremiumUser) {
                    Surface(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(bottom = 16.dp),
                        shape = RoundedCornerShape(20.dp),
                        color = SoftMintLight,
                        border = BorderStroke(1.5.dp, SoftMintAccent)
                    ) {
                        Row(
                            modifier = Modifier.padding(16.dp),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Box(
                                modifier = Modifier
                                    .size(36.dp)
                                    .clip(CircleShape)
                                    .background(DarkTealPrimary),
                                contentAlignment = Alignment.Center
                            ) {
                                Icon(
                                    imageVector = Icons.Default.Star,
                                    contentDescription = null,
                                    tint = Color.White,
                                    modifier = Modifier.size(18.dp)
                                )
                            }
                            Spacer(modifier = Modifier.width(14.dp))
                            Column {
                                Text(
                                    text = "Premium Plan Aktif!",
                                    fontWeight = FontWeight.Bold,
                                    color = DarkTealPrimary,
                                    fontSize = 14.sp
                                )
                                Text(
                                    text = "Tüm premium analizler, raporlar ve derinlikli öneriler kullanıma açık.",
                                    color = LoginTextColor.copy(alpha = 0.8f),
                                    fontSize = 11.sp,
                                    lineHeight = 15.sp
                                )
                            }
                        }
                    }
                }

                // Payment Return Banner
                paymentReturnMessage?.let { msg ->
                    Surface(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(bottom = 16.dp),
                        shape = RoundedCornerShape(16.dp),
                        color = if (msg.contains("aktif")) SoftMintLight else Color(0xFFFFF3DC),
                        border = BorderStroke(1.dp, if (msg.contains("aktif")) SoftMintAccent else Color(0xFFFFB347))
                    ) {
                        Row(
                            modifier = Modifier.padding(16.dp),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Icon(
                                imageVector = Icons.Default.Info,
                                contentDescription = null,
                                tint = if (msg.contains("aktif")) DarkTealPrimary else Color(0xFFFFB347),
                                modifier = Modifier.size(20.dp)
                            )
                            Spacer(modifier = Modifier.width(12.dp))
                            Text(
                                text = msg,
                                style = MaterialTheme.typography.bodySmall,
                                fontWeight = FontWeight.Bold,
                                color = LoginTextColor
                            )
                        }
                    }
                }

                // A. Header Subtitle
                Text(
                    text = "Premium üyelik ve ödeme bilgilerini buradan yönetebilirsin.",
                    style = MaterialTheme.typography.bodyMedium,
                    color = LoginSecondaryText,
                    textAlign = TextAlign.Center,
                    modifier = Modifier.padding(bottom = 24.dp)
                )

                // B. Current Plan Card
                PremiumCard(
                    modifier = Modifier.fillMaxWidth(),
                    cornerRadius = 24.dp
                ) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.SpaceBetween
                    ) {
                        Column(modifier = Modifier.weight(1f)) {
                            Text(
                                text = "Mevcut Plan",
                                style = MaterialTheme.typography.labelMedium,
                                fontWeight = FontWeight.Bold,
                                color = LoginSecondaryText
                            )
                            Spacer(modifier = Modifier.height(4.dp))
                            
                            val hasPremium = currentSubscription?.has_premium == true
                            val activePlanName = if (hasPremium) currentSubscription?.plan_name ?: "Premium Plan" else "Ücretsiz Plan"
                            
                            Text(
                                text = activePlanName,
                                style = MaterialTheme.typography.titleMedium,
                                fontWeight = FontWeight.Bold,
                                color = LoginTextColor
                            )
                        }
                        
                        val isPremium = currentSubscription?.has_premium == true
                        Surface(
                            shape = RoundedCornerShape(12.dp),
                            color = SoftMintAccent.copy(alpha = 0.5f),
                            border = BorderStroke(1.dp, SoftMintAccent)
                        ) {
                            Text(
                                text = if (isPremium) "Aktif" else "Ücretsiz",
                                color = DarkTealPrimary,
                                fontWeight = FontWeight.Bold,
                                fontSize = 12.sp,
                                modifier = Modifier.padding(horizontal = 12.dp, vertical = 6.dp)
                            )
                        }
                    }
                }

                Spacer(modifier = Modifier.height(12.dp))

                PremiumButton(
                    onClick = {
                        viewModel.refreshAfterPaymentReturn()
                        subscriptionViewModel.refreshSubscription()
                    },
                    modifier = Modifier.fillMaxWidth(),
                    containerColor = DarkTealPrimary,
                    contentColor = Color.White
                ) {
                    Text("Durumu Yenile", fontWeight = FontWeight.Bold)
                }

                Spacer(modifier = Modifier.height(20.dp))

                // C. Payment History Card (Replaces saved payment methods since no local card processing is allowed)
                PremiumCard(
                    modifier = Modifier.fillMaxWidth(),
                    cornerRadius = 24.dp
                ) {
                    Column(
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        Text(
                            text = "Ödeme Geçmişi",
                            style = MaterialTheme.typography.bodyMedium,
                            fontWeight = FontWeight.Bold,
                            color = LoginTextColor,
                            modifier = Modifier.align(Alignment.Start)
                        )
                        Spacer(modifier = Modifier.height(16.dp))

                        if (paymentHistory.isEmpty()) {
                            Column(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalAlignment = Alignment.CenterHorizontally
                            ) {
                                Box(
                                    modifier = Modifier
                                        .size(54.dp)
                                        .clip(CircleShape)
                                        .background(SoftMintAccent.copy(alpha = 0.4f)),
                                    contentAlignment = Alignment.Center
                                ) {
                                    Icon(
                                        imageVector = Icons.Default.Lock,
                                        contentDescription = null,
                                        tint = DarkTealPrimary,
                                        modifier = Modifier.size(24.dp)
                                    )
                                }
                                Spacer(modifier = Modifier.height(12.dp))
                                Text(
                                    text = "Henüz bir ödeme geçmişiniz bulunmuyor.",
                                    style = MaterialTheme.typography.bodyMedium,
                                    color = LoginSecondaryText,
                                    textAlign = TextAlign.Center
                                )
                            }
                        } else {
                            Column(
                                verticalArrangement = Arrangement.spacedBy(12.dp)
                            ) {
                                paymentHistory.forEach { transaction ->
                                    Row(
                                        modifier = Modifier.fillMaxWidth(),
                                        horizontalArrangement = Arrangement.SpaceBetween,
                                        verticalAlignment = Alignment.CenterVertically
                                    ) {
                                        Column(modifier = Modifier.weight(1f)) {
                                            Text(
                                                text = "İşlem: ${transaction.transaction_id.take(8)}...",
                                                style = MaterialTheme.typography.bodyMedium,
                                                fontWeight = FontWeight.SemiBold,
                                                color = LoginTextColor
                                            )
                                            Text(
                                                text = transaction.created_at,
                                                style = MaterialTheme.typography.labelSmall,
                                                color = LoginSecondaryText
                                            )
                                        }
                                        Column(horizontalAlignment = Alignment.End) {
                                            Text(
                                                text = "${transaction.amount} ${transaction.currency}",
                                                style = MaterialTheme.typography.bodyMedium,
                                                fontWeight = FontWeight.Bold,
                                                color = DarkTealPrimary
                                            )
                                            Surface(
                                                shape = RoundedCornerShape(8.dp),
                                                color = when (transaction.status.lowercase()) {
                                                    "success", "completed" -> SoftMintAccent.copy(alpha = 0.5f)
                                                    "failed" -> Color(0xFFFFE4E4)
                                                    else -> Color(0xFFFFF3DC)
                                                }
                                            ) {
                                                Text(
                                                    text = when (transaction.status.lowercase()) {
                                                        "success", "completed" -> "Başarılı"
                                                        "failed" -> "Başarısız"
                                                        else -> transaction.status
                                                    },
                                                    modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp),
                                                    color = when (transaction.status.lowercase()) {
                                                        "success", "completed" -> DarkTealPrimary
                                                        "failed" -> Color(0xFFFF6B6B)
                                                        else -> Color(0xFFFFB347)
                                                    },
                                                    fontSize = 10.sp,
                                                    fontWeight = FontWeight.Bold
                                                )
                                            }
                                        }
                                    }
                                    HorizontalDivider(color = SoftMintAccent.copy(alpha = 0.2f))
                                }
                            }
                        }
                    }
                }

                Spacer(modifier = Modifier.height(24.dp))

                // E. Premium Plans Preview Header
                Text(
                    text = "Premium Planlar",
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold,
                    color = LoginTextColor,
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(bottom = 12.dp),
                    textAlign = TextAlign.Start
                )

                // Premium Plans preview cards
                Column(
                    modifier = Modifier.fillMaxWidth(),
                    verticalArrangement = Arrangement.spacedBy(16.dp)
                ) {
                    val hasPremium = currentSubscription?.has_premium == true
                    val activePlanName = currentSubscription?.plan_name ?: ""

                    plans.forEach { plan ->
                        val isCurrent = if (hasPremium) {
                            plan.name == activePlanName
                        } else {
                            plan.price_lira == 0.0 || plan.name.lowercase().contains("ücretsiz") || plan.name.lowercase().contains("free")
                        }

                        val buttonText = if (isCurrent) {
                            "Mevcut Plan"
                        } else {
                            "Ödeme Sayfasına Git"
                        }

                        val enabled = !isCurrent && plan.price_lira > 0.0

                        PlanPreviewCard(
                            title = plan.name,
                            price = "${plan.price_lira} ₺",
                            period = " / " + when (plan.billing_interval) {
                                "month" -> "ay"
                                "year" -> "yıl"
                                else -> plan.billing_interval
                            },
                            benefits = plan.description.split(",").map { it.trim() }.filter { it.isNotEmpty() },
                            buttonText = buttonText,
                            isCurrent = isCurrent,
                            enabled = enabled,
                            onClick = {
                                viewModel.startCheckout(plan.id)
                            }
                        )
                    }
                }

                Spacer(modifier = Modifier.height(28.dp))

                // 4. Security Copy Info Box
                Surface(
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(16.dp),
                    color = SoftMintLight,
                    border = BorderStroke(1.dp, SoftMintAccent.copy(alpha = 0.5f))
                ) {
                    Row(
                        modifier = Modifier.padding(16.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Icon(
                            imageVector = Icons.Default.Info,
                            contentDescription = "Güvenlik Bilgisi",
                            tint = DarkTealPrimary,
                            modifier = Modifier.size(20.dp)
                        )
                        Spacer(modifier = Modifier.width(12.dp))
                        Text(
                            text = "Bu uygulama kart bilgisi almaz veya saklamaz. Ödeme işlemi güvenli ödeme sağlayıcı sayfasında tamamlanır.",
                            style = MaterialTheme.typography.bodySmall,
                            fontWeight = FontWeight.Medium,
                            color = LoginSecondaryText,
                            lineHeight = 16.sp
                        )
                    }
                }

                Spacer(modifier = Modifier.height(32.dp))
            }
        }
    }

    // Error Alert Dialog
    if (showErrorDialog != null) {
        AlertDialog(
            onDismissRequest = { showErrorDialog = null },
            title = {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(
                        imageVector = Icons.Default.Info,
                        contentDescription = null,
                        tint = Color(0xFFFF6B6B),
                        modifier = Modifier.size(24.dp)
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    Text(text = "Hata", fontWeight = FontWeight.Bold)
                }
            },
            text = {
                Text(
                    text = showErrorDialog ?: "",
                    color = LoginTextColor,
                    fontSize = 15.sp,
                    lineHeight = 20.sp
                )
            },
            confirmButton = {
                Button(
                    onClick = { showErrorDialog = null },
                    colors = ButtonDefaults.buttonColors(containerColor = DarkTealPrimary)
                ) {
                    Text("Tamam", color = Color.White)
                }
            }
        )
    }
}

@Composable
fun PlanPreviewCard(
    title: String,
    price: String,
    period: String,
    benefits: List<String>,
    buttonText: String,
    isCurrent: Boolean,
    enabled: Boolean,
    onClick: () -> Unit
) {
    PremiumCard(
        modifier = Modifier.fillMaxWidth(),
        cornerRadius = 24.dp
    ) {
        Column(modifier = Modifier.fillMaxWidth()) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = title,
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold,
                    color = LoginTextColor
                )
                Row(verticalAlignment = Alignment.Bottom) {
                    Text(
                        text = price,
                        style = MaterialTheme.typography.titleLarge,
                        fontWeight = FontWeight.Bold,
                        color = DarkTealPrimary
                    )
                    Text(
                        text = period,
                        style = MaterialTheme.typography.labelSmall,
                        color = LoginSecondaryText,
                        modifier = Modifier.padding(bottom = 2.dp, start = 2.dp)
                    )
                }
            }

            Spacer(modifier = Modifier.height(12.dp))
            HorizontalDivider(color = SoftMintAccent.copy(alpha = 0.3f))
            Spacer(modifier = Modifier.height(12.dp))

            Column(
                modifier = Modifier.fillMaxWidth(),
                verticalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                benefits.forEach { benefit ->
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Box(
                            modifier = Modifier
                                .size(6.dp)
                                .clip(CircleShape)
                                .background(DarkTealPrimary)
                        )
                        Spacer(modifier = Modifier.width(10.dp))
                        Text(
                            text = benefit,
                            style = MaterialTheme.typography.bodySmall,
                            color = LoginSecondaryText,
                            lineHeight = 16.sp
                        )
                    }
                }
            }

            Spacer(modifier = Modifier.height(16.dp))

            PremiumButton(
                onClick = onClick,
                modifier = Modifier.fillMaxWidth(),
                enabled = enabled,
                containerColor = if (isCurrent) SoftMintAccent else DarkTealPrimary,
                contentColor = if (isCurrent) DarkTealPrimary else Color.White
            ) {
                Text(
                    text = buttonText,
                    fontWeight = FontWeight.Bold,
                    fontSize = 14.sp
                )
            }
        }
    }
}
