package com.psikochat.app.ui.home

import androidx.compose.animation.*
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.KeyboardArrowLeft
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavController
import com.psikochat.app.data.api.PsikoApi
import com.psikochat.app.data.api.RetrofitClient
import com.psikochat.app.data.local.TokenManager
import com.psikochat.app.data.model.AdminPsychologist
import com.psikochat.app.data.model.Resource
import com.psikochat.app.ui.theme.*
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch

// ── View Model ────────────────────────────────────────────────────────────

class AdminPsychologistViewModel(private val api: PsikoApi) : ViewModel() {

    private val _pendingState = MutableStateFlow<Resource<List<AdminPsychologist>>>(Resource.Loading())
    val pendingState: StateFlow<Resource<List<AdminPsychologist>>> = _pendingState

    private val _allState = MutableStateFlow<Resource<List<AdminPsychologist>>>(Resource.Loading())
    val allState: StateFlow<Resource<List<AdminPsychologist>>> = _allState

    private val _actionState = MutableStateFlow<Resource<String>?>(null)
    val actionState: StateFlow<Resource<String>?> = _actionState

    init {
        loadData()
    }

    private fun getAdminAuthHeader(): String {
        // DEVELOPMENT-ONLY: Static admin credentials checked at backend basic auth layer
        val credentials = "admin:psiko_secret123"
        val base64 = android.util.Base64.encodeToString(credentials.toByteArray(), android.util.Base64.NO_WRAP)
        return "Basic $base64"
    }

    fun loadData() {
        viewModelScope.launch {
            _pendingState.value = Resource.Loading()
            _allState.value = Resource.Loading()
            
            try {
                val header = getAdminAuthHeader()
                val pending = api.getPendingPsychologists(header)
                _pendingState.value = Resource.Success(pending)
            } catch (e: Exception) {
                _pendingState.value = Resource.Error(e.message ?: "Bekleyen başvurular alınırken hata oluştu.")
            }

            try {
                val header = getAdminAuthHeader()
                val all = api.getAllPsychologists(header)
                _allState.value = Resource.Success(all)
            } catch (e: Exception) {
                _allState.value = Resource.Error(e.message ?: "Tüm uzmanlar alınırken hata oluştu.")
            }
        }
    }

    fun approvePsychologist(username: String) {
        viewModelScope.launch {
            _actionState.value = Resource.Loading()
            try {
                val header = getAdminAuthHeader()
                val response = api.approvePsychologist(username, header)
                _actionState.value = Resource.Success(response["message"] ?: "Onaylandı")
                loadData()
            } catch (e: Exception) {
                _actionState.value = Resource.Error(e.message ?: "Onaylama işlemi başarısız oldu.")
            }
        }
    }

    fun rejectPsychologist(username: String) {
        viewModelScope.launch {
            _actionState.value = Resource.Loading()
            try {
                val header = getAdminAuthHeader()
                val response = api.rejectPsychologist(username, header)
                _actionState.value = Resource.Success(response["message"] ?: "Reddedildi")
                loadData()
            } catch (e: Exception) {
                _actionState.value = Resource.Error(e.message ?: "Reddetme işlemi başarısız oldu.")
            }
        }
    }

    fun clearActionState() {
        _actionState.value = null
    }
}

// ── Composable Screen ──────────────────────────────────────────────────────

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AdminPsychologistApprovalScreen(navController: NavController, tokenManager: TokenManager) {
    val api = RetrofitClient.create(tokenManager)
    val factory = object : ViewModelProvider.Factory {
        override fun <T : ViewModel> create(modelClass: Class<T>): T {
            return AdminPsychologistViewModel(api) as T
        }
    }
    val viewModel: AdminPsychologistViewModel = viewModel(factory = factory)

    val pendingState by viewModel.pendingState.collectAsState()
    val allState by viewModel.allState.collectAsState()
    val actionState by viewModel.actionState.collectAsState()

    val snackbarHostState = remember { SnackbarHostState() }

    LaunchedEffect(actionState) {
        if (actionState is Resource.Error) {
            snackbarHostState.showSnackbar(actionState?.message ?: "İşlem gerçekleştirilemedi.")
            viewModel.clearActionState()
        } else if (actionState is Resource.Success) {
            snackbarHostState.showSnackbar(actionState?.data ?: "İşlem başarılı.")
            viewModel.clearActionState()
        }
    }

    Scaffold(
        snackbarHost = { SnackbarHost(snackbarHostState) },
        topBar = {
            CenterAlignedTopAppBar(
                title = {
                    Text(
                        "Uzman Başvuruları",
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
            if (pendingState is Resource.Loading || allState is Resource.Loading) {
                CircularProgressIndicator(modifier = Modifier.align(Alignment.Center), color = LoginButton)
            } else if (pendingState is Resource.Error) {
                Column(
                    modifier = Modifier.align(Alignment.Center).padding(24.dp),
                    horizontalAlignment = Alignment.CenterHorizontally
                ) {
                    Icon(Icons.Default.Warning, contentDescription = null, tint = DangerRed, modifier = Modifier.size(48.dp))
                    Spacer(modifier = Modifier.height(16.dp))
                    Text(pendingState.message ?: "Bir hata oluştu.", color = LoginTextColor, textAlign = TextAlign.Center)
                    Spacer(modifier = Modifier.height(16.dp))
                    Button(onClick = { viewModel.loadData() }, colors = ButtonDefaults.buttonColors(containerColor = LoginButton)) {
                        Text("Tekrar Dene")
                    }
                }
            } else {
                val pendingList = (pendingState as Resource.Success<List<AdminPsychologist>>).data ?: emptyList()
                val allList = (allState as Resource.Success<List<AdminPsychologist>>).data ?: emptyList()
                
                val approvedList = allList.filter { it.status == "approved" }
                val rejectedList = allList.filter { it.status == "rejected" }

                LazyColumn(
                    modifier = Modifier
                        .fillMaxSize()
                        .padding(horizontal = 20.dp),
                    verticalArrangement = Arrangement.spacedBy(12.dp)
                ) {
                    // ── Section 1: Pending Applications ──
                    item {
                        SectionHeader("Bekleyen Başvurular (${pendingList.size})")
                    }
                    if (pendingList.isEmpty()) {
                        item {
                            EmptyStateCard("Bekleyen uzman başvurusu bulunmamaktadır.")
                        }
                    } else {
                        items(pendingList, key = { it.username }) { psychologist ->
                            PendingPsychologistCard(
                                psychologist = psychologist,
                                onApprove = { viewModel.approvePsychologist(psychologist.username) },
                                onReject = { viewModel.rejectPsychologist(psychologist.username) },
                                isActionLoading = actionState is Resource.Loading
                            )
                        }
                    }

                    // ── Section 2: Approved Psychologists ──
                    item {
                        SectionHeader("Onaylanan Uzmanlar (${approvedList.size})")
                    }
                    if (approvedList.isEmpty()) {
                        item {
                            EmptyStateCard("Onaylanmış uzman bulunmamaktadır.")
                        }
                    } else {
                        items(approvedList, key = { it.username }) { psychologist ->
                            ReadOnlyPsychologistCard(psychologist = psychologist, accentColor = LoginButton)
                        }
                    }

                    // ── Section 3: Rejected Psychologists ──
                    item {
                        SectionHeader("Reddedilen Uzmanlar (${rejectedList.size})")
                    }
                    if (rejectedList.isEmpty()) {
                        item {
                            EmptyStateCard("Reddedilmiş uzman bulunmamaktadır.")
                        }
                    } else {
                        items(rejectedList, key = { it.username }) { psychologist ->
                            ReadOnlyPsychologistCard(psychologist = psychologist, accentColor = DangerRed)
                        }
                    }
                    
                    item {
                        Spacer(modifier = Modifier.height(24.dp))
                    }
                }
            }
        }
    }
}

// ── UI Components ─────────────────────────────────────────────────────────

@Composable
fun SectionHeader(title: String) {
    Text(
        text = title,
        fontWeight = FontWeight.Bold,
        fontSize = 16.sp,
        color = LoginTextColor,
        modifier = Modifier.padding(top = 16.dp, bottom = 4.dp)
    )
}

@Composable
fun EmptyStateCard(text: String) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(containerColor = PremiumWhiteCard)
    ) {
        Box(
            modifier = Modifier.padding(16.dp),
            contentAlignment = Alignment.Center
        ) {
            Text(
                text = text,
                color = LoginSecondaryText,
                fontSize = 13.sp,
                textAlign = TextAlign.Center,
                modifier = Modifier.fillMaxWidth()
            )
        }
    }
}

@Composable
fun PendingPsychologistCard(
    psychologist: AdminPsychologist,
    onApprove: () -> Unit,
    onReject: () -> Unit,
    isActionLoading: Boolean
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(20.dp),
        colors = CardDefaults.cardColors(containerColor = Color.White)
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Text(
                text = "${psychologist.title} ${psychologist.fullName ?: psychologist.username}",
                fontWeight = FontWeight.Bold,
                fontSize = 15.sp,
                color = LoginTextColor
            )
            Spacer(modifier = Modifier.height(4.dp))
            Text(text = "E-posta: ${psychologist.email ?: "-"}", fontSize = 12.sp, color = LoginSecondaryText)
            Text(text = "Uzmanlık: ${psychologist.specialty}", fontSize = 12.sp, color = LoginSecondaryText)
            Text(text = "Kayıt Tarihi: ${psychologist.createdAt.substringBefore("T")}", fontSize = 12.sp, color = LoginSecondaryText)

            Spacer(modifier = Modifier.height(14.dp))
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                Button(
                    onClick = onApprove,
                    modifier = Modifier.weight(1f),
                    colors = ButtonDefaults.buttonColors(containerColor = LoginButton),
                    shape = RoundedCornerShape(12.dp),
                    enabled = !isActionLoading
                ) {
                    Text("Onayla", color = Color.White, fontWeight = FontWeight.Bold, fontSize = 13.sp)
                }

                Button(
                    onClick = onReject,
                    modifier = Modifier.weight(1f),
                    colors = ButtonDefaults.buttonColors(containerColor = DangerRed),
                    shape = RoundedCornerShape(12.dp),
                    enabled = !isActionLoading
                ) {
                    Text("Reddet", color = Color.White, fontWeight = FontWeight.Bold, fontSize = 13.sp)
                }
            }
        }
    }
}

@Composable
fun ReadOnlyPsychologistCard(psychologist: AdminPsychologist, accentColor: Color) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(containerColor = PremiumWhiteCard)
    ) {
        Column(modifier = Modifier.padding(14.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = "${psychologist.title} ${psychologist.fullName ?: psychologist.username}",
                    fontWeight = FontWeight.Bold,
                    fontSize = 14.sp,
                    color = LoginTextColor,
                    modifier = Modifier.weight(1f)
                )
                
                Surface(
                    shape = RoundedCornerShape(8.dp),
                    color = accentColor.copy(alpha = 0.1f)
                ) {
                    Text(
                        text = if (psychologist.status == "approved") "ONAYLI" else "REDDEDİLDİ",
                        color = accentColor,
                        fontSize = 10.sp,
                        fontWeight = FontWeight.Bold,
                        modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp)
                    )
                }
            }
            Spacer(modifier = Modifier.height(4.dp))
            Text(text = "E-posta: ${psychologist.email ?: "-"}", fontSize = 12.sp, color = LoginSecondaryText)
            Text(text = "Uzmanlık: ${psychologist.specialty}", fontSize = 12.sp, color = LoginSecondaryText)
        }
    }
}
