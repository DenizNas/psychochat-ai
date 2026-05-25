package com.psikochat.app.ui.home

import android.widget.Toast
import androidx.compose.animation.*
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalClipboardManager
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavController
import com.psikochat.app.data.api.RetrofitClient
import com.psikochat.app.data.local.TokenManager
import com.psikochat.app.data.model.UserConsentResponse
import com.psikochat.app.data.model.UpdateConsentRequest
import com.psikochat.app.data.model.Resource
import com.psikochat.app.data.repository.PrivacyRepository
import com.psikochat.app.ui.theme.*
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch

// ── View Model ────────────────────────────────────────────────────────────

class PrivacyDataViewModel(private val repository: PrivacyRepository) : ViewModel() {

    private val _consentState = MutableStateFlow<Resource<UserConsentResponse>>(Resource.Loading())
    val consentState: StateFlow<Resource<UserConsentResponse>> = _consentState

    private val _updateState = MutableStateFlow<Resource<UserConsentResponse>?>(null)
    val updateState: StateFlow<Resource<UserConsentResponse>?> = _updateState

    private val _exportState = MutableStateFlow<Resource<Map<String, Any>>?>(null)
    val exportState: StateFlow<Resource<Map<String, Any>>?> = _exportState

    private val _deleteState = MutableStateFlow<Resource<Map<String, String>>?>(null)
    val deleteState: StateFlow<Resource<Map<String, String>>?> = _deleteState

    init {
        loadConsent()
    }

    fun loadConsent() {
        viewModelScope.launch {
            _consentState.value = Resource.Loading()
            _consentState.value = repository.getPrivacyConsent()
        }
    }

    fun updateConsent(
        analytics: Boolean,
        wellness: Boolean,
        notifications: Boolean,
        aiProcessing: Boolean
    ) {
        viewModelScope.launch {
            _updateState.value = Resource.Loading()
            val request = UpdateConsentRequest(
                analyticsConsent = analytics,
                wellnessInsightsConsent = wellness,
                notificationsConsent = notifications,
                aiProcessingConsent = aiProcessing
            )
            val res = repository.updatePrivacyConsent(request)
            _updateState.value = res
            if (res is Resource.Success) {
                _consentState.value = Resource.Success(res.data!!)
            }
        }
    }

    fun exportUserData() {
        viewModelScope.launch {
            _exportState.value = Resource.Loading()
            _exportState.value = repository.exportPrivacyData()
        }
    }

    fun deleteAccount(confirm: String) {
        viewModelScope.launch {
            _deleteState.value = Resource.Loading()
            _deleteState.value = repository.deletePrivacyAccount(confirm)
        }
    }

    fun clearStates() {
        _updateState.value = null
        _exportState.value = null
        _deleteState.value = null
    }
}

// ── Composable Screen ──────────────────────────────────────────────────────

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun PrivacyDataScreen(navController: NavController, tokenManager: TokenManager) {
    val api = RetrofitClient.create(tokenManager)
    val repository = PrivacyRepository(api)
    val context = LocalContext.current
    val clipboardManager = LocalClipboardManager.current

    val factory = object : ViewModelProvider.Factory {
        override fun <T : ViewModel> create(modelClass: Class<T>): T {
            return PrivacyDataViewModel(repository) as T
        }
    }
    val viewModel: PrivacyDataViewModel = viewModel(factory = factory)

    val consentState by viewModel.consentState.collectAsState()
    val updateState by viewModel.updateState.collectAsState()
    val exportState by viewModel.exportState.collectAsState()
    val deleteState by viewModel.deleteState.collectAsState()

    val scope = rememberCoroutineScope()
    val snackbarHostState = remember { SnackbarHostState() }

    var showExportDialog by remember { mutableStateOf<String?>(null) }
    var showDeleteDialog by remember { mutableStateOf(false) }
    var deleteConfirmationText by remember { mutableStateOf("") }

    // State bindings for local toggles to prevent lag during server updates
    var analyticsConsent by remember { mutableStateOf(false) }
    var wellnessConsent by remember { mutableStateOf(false) }
    var notificationsConsent by remember { mutableStateOf(false) }
    var aiConsent by remember { mutableStateOf(false) }

    // Sync state when loaded successfully
    LaunchedEffect(consentState) {
        if (consentState is Resource.Success) {
            val data = (consentState as Resource.Success<UserConsentResponse>).data!!
            analyticsConsent = data.analyticsConsent
            wellnessConsent = data.wellnessInsightsConsent
            notificationsConsent = data.notificationsConsent
            aiConsent = data.aiProcessingConsent
        }
    }

    LaunchedEffect(updateState) {
        if (updateState is Resource.Error) {
            snackbarHostState.showSnackbar(updateState?.message ?: "Onay ayarları güncellenemedi.")
            viewModel.clearStates()
        } else if (updateState is Resource.Success) {
            snackbarHostState.showSnackbar("Gizlilik izinleriniz başarıyla güncellendi.")
            viewModel.clearStates()
        }
    }

    LaunchedEffect(exportState) {
        if (exportState is Resource.Error) {
            snackbarHostState.showSnackbar(exportState?.message ?: "Kişisel veriler dışa aktarılamadı.")
            viewModel.clearStates()
        } else if (exportState is Resource.Success) {
            // Convert exported Map to readable formatted JSON string
            val rawMap = (exportState as Resource.Success<Map<String, Any>>).data!!
            val prettyJson = try {
                org.json.JSONObject(rawMap).toString(4)
            } catch (e: Exception) {
                rawMap.toString()
            }
            showExportDialog = prettyJson
            viewModel.clearStates()
        }
    }

    LaunchedEffect(deleteState) {
        if (deleteState is Resource.Error) {
            Toast.makeText(context, deleteState?.message ?: "Silme işlemi başarısız.", Toast.LENGTH_LONG).show()
            viewModel.clearStates()
        } else if (deleteState is Resource.Success) {
            Toast.makeText(context, "Hesabınız ve kişisel verileriniz kalıcı olarak silindi.", Toast.LENGTH_LONG).show()
            viewModel.clearStates()
            showDeleteDialog = false
            tokenManager.clearAuthData()
            navController.navigate("auth_graph") {
                popUpTo("main_graph") { inclusive = true }
                launchSingleTop = true
            }
        }
    }

    Scaffold(
        snackbarHost = { SnackbarHost(snackbarHostState) },
        topBar = {
            CenterAlignedTopAppBar(
                title = {
                    Text(
                        "Kişisel Veriler ve İzinler",
                        style = MaterialTheme.typography.titleMedium,
                        color = LoginTextColor
                    )
                },
                navigationIcon = {
                    IconButton(onClick = { navController.popBackStack() }) {
                        Icon(Icons.Default.KeyboardArrowLeft, contentDescription = "Geri", tint = LoginTextColor)
                    }
                },
                colors = TopAppBarDefaults.centerAlignedTopAppBarColors(containerColor = Color.Transparent)
            )
        },
        containerColor = LoginBackground
    ) { padding ->
        Box(modifier = Modifier.fillMaxSize().padding(padding)) {
            when (consentState) {
                is Resource.Loading -> {
                    CircularProgressIndicator(modifier = Modifier.align(Alignment.Center), color = LoginButton)
                }
                is Resource.Error -> {
                    Column(
                        modifier = Modifier.align(Alignment.Center).padding(24.dp),
                        horizontalAlignment = Alignment.CenterHorizontally
                    ) {
                        Icon(Icons.Default.Warning, contentDescription = null, tint = Color.Red, modifier = Modifier.size(48.dp))
                        Spacer(modifier = Modifier.height(16.dp))
                        Text(consentState.message ?: "Bilgiler alınamadı.", color = LoginTextColor)
                        Spacer(modifier = Modifier.height(8.dp))
                        Button(onClick = { viewModel.loadConsent() }, colors = ButtonDefaults.buttonColors(containerColor = LoginButton)) {
                            Text("Tekrar Dene")
                        }
                    }
                }
                is Resource.Success -> {
                    Column(
                        modifier = Modifier
                            .fillMaxSize()
                            .padding(horizontal = 24.dp)
                            .verticalScroll(rememberScrollState()),
                        horizontalAlignment = Alignment.CenterHorizontally
                    ) {
                        Spacer(modifier = Modifier.height(16.dp))

                        // GDPR Info Banner Card
                        Card(
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(vertical = 8.dp),
                            shape = RoundedCornerShape(20.dp),
                            colors = CardDefaults.cardColors(containerColor = Color.White)
                        ) {
                            Row(
                                modifier = Modifier.padding(16.dp),
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Box(
                                    modifier = Modifier
                                        .size(40.dp)
                                        .clip(CircleShape)
                                        .background(LoginButton.copy(alpha = 0.1f)),
                                    contentAlignment = Alignment.Center
                                ) {
                                    Icon(Icons.Default.Info, contentDescription = null, tint = LoginButton, modifier = Modifier.size(20.dp))
                                }
                                Spacer(modifier = Modifier.width(16.dp))
                                Column {
                                    Text(
                                        text = "KVKK & GDPR Güvencesi",
                                        fontWeight = FontWeight.Bold,
                                        color = LoginTextColor,
                                        fontSize = 14.sp
                                    )
                                    Text(
                                        text = "Verileriniz üst düzey güvenlik standartlarında korunur. Dilediğiniz zaman verilerinizi indirebilir veya silebilirsiniz.",
                                        color = LoginSecondaryText,
                                        fontSize = 12.sp,
                                        lineHeight = 16.sp
                                    )
                                }
                            }
                        }

                        Spacer(modifier = Modifier.height(16.dp))

                        // Opt-in Consent Toggles Group
                        Surface(
                            modifier = Modifier.fillMaxWidth(),
                            shape = RoundedCornerShape(24.dp),
                            color = Color.White.copy(alpha = 0.9f)
                        ) {
                            Column(modifier = Modifier.padding(16.dp)) {
                                Text("Açık Rıza ve Onay Tercihleri", fontWeight = FontWeight.Bold, color = LoginTextColor, modifier = Modifier.padding(bottom = 8.dp))

                                PrivacySwitchItem(
                                    title = "Anonim Analitik İzni",
                                    description = "Uygulama deneyimini iyileştirmek üzere anonim kullanım istatistiklerinin toplanmasına izin veriyorum.",
                                    checked = analyticsConsent
                                ) {
                                    analyticsConsent = it
                                    viewModel.updateConsent(analyticsConsent, wellnessConsent, notificationsConsent, aiConsent)
                                }

                                Divider(color = Color.LightGray.copy(alpha = 0.3f), modifier = Modifier.padding(vertical = 12.dp))

                                PrivacySwitchItem(
                                    title = "Wellness & Duygu Analizi İçgörüleri",
                                    description = "Yapay zekanın duygu durum grafiklerini ve haftalık wellness raporlarımı oluşturmasına izin veriyorum.",
                                    checked = wellnessConsent
                                ) {
                                    wellnessConsent = it
                                    viewModel.updateConsent(analyticsConsent, wellnessConsent, notificationsConsent, aiConsent)
                                }

                                Divider(color = Color.LightGray.copy(alpha = 0.3f), modifier = Modifier.padding(vertical = 12.dp))

                                PrivacySwitchItem(
                                    title = "Bildirim ve Hatırlatmalar",
                                    description = "Kişiselleştirilmiş wellness uyarıları ve günlük ruh hali hatırlatıcı bildirimleri almayı kabul ediyorum.",
                                    checked = notificationsConsent
                                ) {
                                    notificationsConsent = it
                                    viewModel.updateConsent(analyticsConsent, wellnessConsent, notificationsConsent, aiConsent)
                                }

                                Divider(color = Color.LightGray.copy(alpha = 0.3f), modifier = Modifier.padding(vertical = 12.dp))

                                PrivacySwitchItem(
                                    title = "AI Yanıt İşleme ve Bellek Kaydı",
                                    description = "Yapay zeka modellerinin psikolojik destek süreçlerimi iyileştirmek için bellek çıkarmasına ve verilerimi işlemesine rıza gösteriyorum.",
                                    checked = aiConsent
                                ) {
                                    aiConsent = it
                                    viewModel.updateConsent(analyticsConsent, wellnessConsent, notificationsConsent, aiConsent)
                                }
                            }
                        }

                        Spacer(modifier = Modifier.height(24.dp))

                        // GDPR Operations Card (Data Portability and Right to be Forgotten)
                        Surface(
                            modifier = Modifier.fillMaxWidth(),
                            shape = RoundedCornerShape(24.dp),
                            color = Color.White.copy(alpha = 0.9f)
                        ) {
                            Column(modifier = Modifier.padding(16.dp)) {
                                Text("Veri Taşınabilirliği ve Haklar", fontWeight = FontWeight.Bold, color = LoginTextColor, modifier = Modifier.padding(bottom = 8.dp))

                                // Export Button
                                Row(
                                    modifier = Modifier
                                        .fillMaxWidth()
                                        .clickable { viewModel.exportUserData() }
                                        .padding(vertical = 12.dp),
                                    verticalAlignment = Alignment.CenterVertically
                                ) {
                                    Icon(Icons.Default.Share, contentDescription = null, tint = LoginButton)
                                    Spacer(modifier = Modifier.width(16.dp))
                                    Column(modifier = Modifier.weight(1f)) {
                                        Text("Verilerimi Dışa Aktar (GDPR)", fontWeight = FontWeight.Medium, color = LoginTextColor)
                                        Text("Profilinizi, ruh hali günlüklerinizi ve hafıza verilerinizi şeffaf bir JSON formatında indirin.", fontSize = 11.sp, color = LoginSecondaryText)
                                    }
                                    if (exportState is Resource.Loading) {
                                        CircularProgressIndicator(modifier = Modifier.size(20.dp), color = LoginButton, strokeWidth = 2.dp)
                                    } else {
                                        Icon(Icons.Default.KeyboardArrowRight, contentDescription = null, tint = Color.Gray)
                                    }
                                }

                                Divider(color = Color.LightGray.copy(alpha = 0.3f), modifier = Modifier.padding(vertical = 12.dp))

                                // Delete Button
                                Row(
                                    modifier = Modifier
                                        .fillMaxWidth()
                                        .clickable { showDeleteDialog = true }
                                        .padding(vertical = 12.dp),
                                    verticalAlignment = Alignment.CenterVertically
                                ) {
                                    Icon(Icons.Default.Delete, contentDescription = null, tint = Color.Red)
                                    Spacer(modifier = Modifier.width(16.dp))
                                    Column(modifier = Modifier.weight(1f)) {
                                        Text("Hesabımı ve Verilerimi Sil", fontWeight = FontWeight.Medium, color = Color.Red)
                                        Text("Hesabınızı kalıcı olarak kapatın ve tüm verilerinizi geri döndürülemez şekilde sistemden kaldırın.", fontSize = 11.sp, color = LoginSecondaryText)
                                    }
                                    Icon(Icons.Default.KeyboardArrowRight, contentDescription = null, tint = Color.Gray)
                                }
                            }
                        }

                        Spacer(modifier = Modifier.height(24.dp))
                        Text("Veri İzinleri Sürümü: v1.0", fontSize = 12.sp, color = LoginSecondaryText)
                        Spacer(modifier = Modifier.height(24.dp))
                    }
                }
            }
        }
    }

    // GDPR Export Dialog Viewer
    if (showExportDialog != null) {
        AlertDialog(
            onDismissRequest = { showExportDialog = null },
            title = { Text("Kişisel Veri İhracatı", fontWeight = FontWeight.Bold) },
            text = {
                Column(modifier = Modifier.fillMaxWidth()) {
                    Text(
                        "Kişisel verileriniz GDPR Madde 20 kapsamında başarıyla hazırlanmıştır. JSON verisini kopyalayıp dilediğiniz platforma taşıyabilirsiniz.",
                        fontSize = 13.sp,
                        color = LoginTextColor,
                        modifier = Modifier.padding(bottom = 12.dp)
                    )
                    
                    Box(
                        modifier = Modifier
                            .fillMaxWidth()
                            .height(200.dp)
                            .background(Color(0xFFF5F5F5), RoundedCornerShape(12.dp))
                            .padding(8.dp)
                            .verticalScroll(rememberScrollState())
                    ) {
                        Text(
                            text = showExportDialog!!,
                            fontSize = 11.sp,
                            fontFamily = androidx.compose.ui.text.font.FontFamily.Monospace,
                            color = Color.Black.copy(alpha = 0.8f)
                        )
                    }
                }
            },
            confirmButton = {
                Button(
                    onClick = {
                        showExportDialog?.let {
                            clipboardManager.setText(AnnotatedString(it))
                            Toast.makeText(context, "Veriler panoya kopyalandı", Toast.LENGTH_SHORT).show()
                        }
                    },
                    colors = ButtonDefaults.buttonColors(containerColor = LoginButton)
                ) {
                    Icon(Icons.Default.Share, contentDescription = null, modifier = Modifier.size(16.dp))
                    Spacer(modifier = Modifier.width(8.dp))
                    Text("Kopyala")
                }
            },
            dismissButton = {
                TextButton(onClick = { showExportDialog = null }) {
                    Text("Kapat")
                }
            }
        )
    }

    // Irreversible Account Deletion Confirmation Dialog
    if (showDeleteDialog) {
        AlertDialog(
            onDismissRequest = { 
                if (deleteState !is Resource.Loading) {
                    showDeleteDialog = false 
                    deleteConfirmationText = ""
                }
            },
            title = { 
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(Icons.Default.Warning, contentDescription = null, tint = Color.Red, modifier = Modifier.size(24.dp))
                    Spacer(modifier = Modifier.width(8.dp))
                    Text("Kalıcı Silme İşlemi!", fontWeight = FontWeight.Bold, color = Color.Red)
                }
            },
            text = {
                Column {
                    Text(
                        text = "Bu işlem GERİ ALINAMAZ. Hesap oturumunuz kalıcı olarak sonlandırılacak, verileriniz yasal sınırlar haricinde sistemden tamamen kazınacaktır.",
                        fontSize = 13.sp,
                        fontWeight = FontWeight.Bold,
                        color = LoginTextColor
                    )
                    Spacer(modifier = Modifier.height(8.dp))
                    Text(
                        text = "Onaylamak için lütfen aşağıdaki kutuya tam olarak DELETE_MY_DATA yazın:",
                        fontSize = 12.sp,
                        color = LoginSecondaryText
                    )
                    Spacer(modifier = Modifier.height(12.dp))
                    OutlinedTextField(
                        value = deleteConfirmationText,
                        onValueChange = { deleteConfirmationText = it },
                        modifier = Modifier.fillMaxWidth(),
                        placeholder = { Text("DELETE_MY_DATA", fontSize = 13.sp) },
                        singleLine = true,
                        colors = OutlinedTextFieldDefaults.colors(
                            focusedBorderColor = Color.Red,
                            unfocusedBorderColor = Color.Gray
                        ),
                        enabled = deleteState !is Resource.Loading
                    )
                }
            },
            confirmButton = {
                Button(
                    onClick = { 
                        if (deleteConfirmationText == "DELETE_MY_DATA") {
                            viewModel.deleteAccount("DELETE_MY_DATA")
                        }
                    },
                    colors = ButtonDefaults.buttonColors(containerColor = Color.Red),
                    enabled = deleteConfirmationText == "DELETE_MY_DATA" && deleteState !is Resource.Loading
                ) {
                    if (deleteState is Resource.Loading) {
                        CircularProgressIndicator(modifier = Modifier.size(20.dp), color = Color.White, strokeWidth = 2.dp)
                    } else {
                        Text("Verileri Kalıcı Olarak Yok Et")
                    }
                }
            },
            dismissButton = {
                TextButton(
                    onClick = { 
                        showDeleteDialog = false 
                        deleteConfirmationText = ""
                    },
                    enabled = deleteState !is Resource.Loading
                ) {
                    Text("Vazgeç")
                }
            }
        )
    }
}

@Composable
fun PrivacySwitchItem(
    title: String,
    description: String,
    checked: Boolean,
    onCheckedChange: (Boolean) -> Unit
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 8.dp),
        verticalAlignment = Alignment.Top,
        horizontalArrangement = Arrangement.SpaceBetween
    ) {
        Column(modifier = Modifier.weight(1f).padding(end = 16.dp)) {
            Text(text = title, fontWeight = FontWeight.Bold, color = LoginTextColor, fontSize = 14.sp)
            Spacer(modifier = Modifier.height(2.dp))
            Text(text = description, fontSize = 11.sp, color = LoginSecondaryText, lineHeight = 15.sp)
        }
        Switch(
            checked = checked,
            onCheckedChange = onCheckedChange,
            colors = SwitchDefaults.colors(
                checkedThumbColor = LoginButton,
                checkedTrackColor = LoginButton.copy(alpha = 0.5f)
            )
        )
    }
}
