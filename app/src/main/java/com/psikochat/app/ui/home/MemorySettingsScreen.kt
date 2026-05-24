package com.psikochat.app.ui.home

import androidx.compose.animation.*
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
import androidx.compose.ui.graphics.vector.ImageVector
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
import com.psikochat.app.data.model.UserMemory
import com.psikochat.app.data.model.MemoryConsolidationResponse
import com.psikochat.app.data.model.Resource
import com.psikochat.app.data.repository.MemoryRepository
import com.psikochat.app.data.repository.ProfileRepository
import com.psikochat.app.ui.theme.*
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch

// ── View Model ────────────────────────────────────────────────────────────

class MemorySettingsViewModel(
    private val memoryRepo: MemoryRepository,
    private val profileRepo: ProfileRepository
) : ViewModel() {

    private val _memoriesState = MutableStateFlow<Resource<List<UserMemory>>>(Resource.Loading())
    val memoriesState: StateFlow<Resource<List<UserMemory>>> = _memoriesState

    private val _profileState = MutableStateFlow<Resource<com.psikochat.app.data.model.ProfileResponse>>(Resource.Loading())
    val profileState: StateFlow<Resource<com.psikochat.app.data.model.ProfileResponse>> = _profileState

    private val _deleteState = MutableStateFlow<Resource<Unit>?>(null)
    val deleteState: StateFlow<Resource<Unit>?> = _deleteState

    private val _refreshState = MutableStateFlow<Resource<MemoryConsolidationResponse>?>(null)
    val refreshState: StateFlow<Resource<MemoryConsolidationResponse>?> = _refreshState

    init {
        loadData()
    }

    fun loadData() {
        viewModelScope.launch {
            _memoriesState.value = Resource.Loading()
            _profileState.value = Resource.Loading()
            
            val profileRes = profileRepo.getProfile()
            _profileState.value = profileRes
            
            val memoriesRes = memoryRepo.getMemories()
            _memoriesState.value = memoriesRes
        }
    }

    fun deleteMemory(memoryId: Int) {
        viewModelScope.launch {
            _deleteState.value = Resource.Loading()
            val res = memoryRepo.deleteMemory(memoryId)
            _deleteState.value = res
            if (res is Resource.Success) {
                // Refresh list
                val memoriesRes = memoryRepo.getMemories()
                _memoriesState.value = memoriesRes
            }
        }
    }

    fun refreshMemories() {
        viewModelScope.launch {
            _refreshState.value = Resource.Loading()
            val res = memoryRepo.refreshMemories()
            _refreshState.value = res
            if (res is Resource.Success) {
                // Refresh list
                val memoriesRes = memoryRepo.getMemories()
                _memoriesState.value = memoriesRes
            }
        }
    }

    fun clearStates() {
        _deleteState.value = null
        _refreshState.value = null
    }
}

// ── Composable Screen ──────────────────────────────────────────────────────

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MemorySettingsScreen(navController: NavController, tokenManager: TokenManager) {
    val api = RetrofitClient.create(tokenManager)
    val memoryRepo = MemoryRepository(api)
    val profileRepo = ProfileRepository(api)

    val factory = object : ViewModelProvider.Factory {
        override fun <T : ViewModel> create(modelClass: Class<T>): T {
            return MemorySettingsViewModel(memoryRepo, profileRepo) as T
        }
    }
    val viewModel: MemorySettingsViewModel = viewModel(factory = factory)

    val memoriesState by viewModel.memoriesState.collectAsState()
    val profileState by viewModel.profileState.collectAsState()
    val deleteState by viewModel.deleteState.collectAsState()
    val refreshState by viewModel.refreshState.collectAsState()

    val scope = rememberCoroutineScope()
    val snackbarHostState = remember { SnackbarHostState() }

    var showConsolidationDialog by remember { mutableStateOf<MemoryConsolidationResponse?>(null) }
    var memoryToDelete by remember { mutableStateOf<UserMemory?>(null) }

    LaunchedEffect(deleteState) {
        if (deleteState is Resource.Error) {
            snackbarHostState.showSnackbar(deleteState?.message ?: "Hafıza silinemedi.")
            viewModel.clearStates()
        } else if (deleteState is Resource.Success) {
            snackbarHostState.showSnackbar("Hafıza başarıyla silindi.")
            viewModel.clearStates()
            memoryToDelete = null
        }
    }

    LaunchedEffect(refreshState) {
        if (refreshState is Resource.Error) {
            snackbarHostState.showSnackbar(refreshState?.message ?: "Konsolidasyon başarısız.")
            viewModel.clearStates()
        } else if (refreshState is Resource.Success) {
            showConsolidationDialog = refreshState?.data
            viewModel.clearStates()
        }
    }

    Scaffold(
        snackbarHost = { SnackbarHost(snackbarHostState) },
        topBar = {
            CenterAlignedTopAppBar(
                title = {
                    Text(
                        "Hatırlanan Bilgiler",
                        style = MaterialTheme.typography.titleMedium,
                        color = LoginTextColor
                    )
                },
                navigationIcon = {
                    IconButton(onClick = { navController.popBackStack() }) {
                        Icon(Icons.Default.KeyboardArrowLeft, contentDescription = "Geri", tint = LoginTextColor)
                    }
                },
                actions = {
                    IconButton(
                        onClick = { viewModel.refreshMemories() },
                        enabled = refreshState !is Resource.Loading && memoriesState is Resource.Success
                    ) {
                        if (refreshState is Resource.Loading) {
                            CircularProgressIndicator(modifier = Modifier.size(20.dp), color = LoginButton, strokeWidth = 2.dp)
                        } else {
                            Icon(Icons.Default.Refresh, contentDescription = "Belleği Optimize Et", tint = LoginButton)
                        }
                    }
                },
                colors = TopAppBarDefaults.centerAlignedTopAppBarColors(containerColor = Color.Transparent)
            )
        },
        containerColor = LoginBackground
    ) { padding ->
        Box(modifier = Modifier.fillMaxSize().padding(padding)) {
            when (profileState) {
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
                        Text(profileState.message ?: "Profil bilgisi alınamadı.", color = LoginTextColor)
                        Button(onClick = { viewModel.loadData() }, colors = ButtonDefaults.buttonColors(containerColor = LoginButton)) {
                            Text("Tekrar Dene")
                        }
                    }
                }
                is Resource.Success -> {
                    val profile = profileState.data!!
                    val isPrivacyModeActive = profile.privacyMode

                    Column(
                        modifier = Modifier
                            .fillMaxSize()
                            .padding(horizontal = 24.dp)
                    ) {
                        // Premium Wording Card
                        Card(
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(vertical = 12.dp),
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
                                    Icon(Icons.Default.Star, contentDescription = null, tint = LoginButton, modifier = Modifier.size(20.dp))
                                }
                                Spacer(modifier = Modifier.width(16.dp))
                                Column {
                                    Text(
                                        text = "Kişiselleştirilmiş Deneyim",
                                        fontWeight = FontWeight.Bold,
                                        color = LoginTextColor,
                                        fontSize = 14.sp
                                    )
                                    Text(
                                        text = "Bunları senin deneyimini kişiselleştirmek için hatırlıyorum.",
                                        color = LoginSecondaryText,
                                        fontSize = 12.sp,
                                        lineHeight = 16.sp
                                    )
                                }
                            }
                        }

                        // Privacy Mode Warning Card
                        if (isPrivacyModeActive) {
                            Card(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .padding(bottom = 12.dp),
                                shape = RoundedCornerShape(20.dp),
                                colors = CardDefaults.cardColors(containerColor = Color.Red.copy(alpha = 0.08f))
                            ) {
                                Row(
                                    modifier = Modifier.padding(16.dp),
                                    verticalAlignment = Alignment.CenterVertically
                                ) {
                                    Icon(Icons.Default.Lock, contentDescription = null, tint = Color.Red, modifier = Modifier.size(24.dp))
                                    Spacer(modifier = Modifier.width(16.dp))
                                    Column {
                                        Text(
                                            text = "Gizlilik Modu Aktif",
                                            fontWeight = FontWeight.Bold,
                                            color = Color.Red,
                                            fontSize = 14.sp
                                        )
                                        Text(
                                            text = "Gizlilik modu açıkken yeni bellek analiz edilmez ve mevcut bellekler yanıtlara dahil edilmez.",
                                            color = Color.Black.copy(alpha = 0.7f),
                                            fontSize = 11.sp,
                                            lineHeight = 15.sp
                                        )
                                    }
                                }
                            }
                        }

                        // Memories List Section
                        when (memoriesState) {
                            is Resource.Loading -> {
                                Box(modifier = Modifier.fillMaxWidth().weight(1f)) {
                                    CircularProgressIndicator(modifier = Modifier.align(Alignment.Center), color = LoginButton)
                                }
                            }
                            is Resource.Error -> {
                                Box(modifier = Modifier.fillMaxWidth().weight(1f), contentAlignment = Alignment.Center) {
                                    Text(memoriesState.message ?: "Bilgiler yüklenemedi.", color = LoginTextColor)
                                }
                            }
                            is Resource.Success -> {
                                val memories = memoriesState.data!!
                                if (memories.isEmpty()) {
                                    Box(
                                        modifier = Modifier.fillMaxWidth().weight(1f),
                                        contentAlignment = Alignment.Center
                                    ) {
                                        Column(horizontalAlignment = Alignment.CenterHorizontally) {
                                            Icon(Icons.Default.Info, contentDescription = null, tint = Color.Gray, modifier = Modifier.size(40.dp))
                                            Spacer(modifier = Modifier.height(8.dp))
                                            Text(
                                                "Henüz kayıtlı bir bilgi yok.",
                                                color = LoginSecondaryText,
                                                fontSize = 14.sp,
                                                textAlign = TextAlign.Center
                                            )
                                        }
                                    }
                                } else {
                                    LazyColumn(
                                        modifier = Modifier.weight(1f),
                                        verticalArrangement = Arrangement.spacedBy(10.dp)
                                    ) {
                                        items(memories, key = { it.id }) { memory ->
                                            MemoryItemRow(
                                                memory = memory,
                                                onDelete = { memoryToDelete = memory }
                                            )
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    // Deletion Confirmation Dialog
    if (memoryToDelete != null) {
        AlertDialog(
            onDismissRequest = { memoryToDelete = null },
            title = { Text("Bilgiyi Unut?", fontWeight = FontWeight.Bold) },
            text = {
                Text("Bu bilginin hatırlanmasını istemediğinden emin misin?\n\n\"${memoryToDelete?.memoryText}\"")
            },
            confirmButton = {
                Button(
                    onClick = { memoryToDelete?.let { viewModel.deleteMemory(it.id) } },
                    colors = ButtonDefaults.buttonColors(containerColor = Color.Red),
                    enabled = deleteState !is Resource.Loading
                ) {
                    if (deleteState is Resource.Loading) {
                        CircularProgressIndicator(modifier = Modifier.size(20.dp), color = Color.White)
                    } else {
                        Text("Unut")
                    }
                }
            },
            dismissButton = {
                TextButton(onClick = { memoryToDelete = null }, enabled = deleteState !is Resource.Loading) {
                    Text("İptal")
                }
            }
        )
    }

    // Consolidation Completion Stats Dialog
    if (showConsolidationDialog != null) {
        val stats = showConsolidationDialog!!
        AlertDialog(
            onDismissRequest = { showConsolidationDialog = null },
            title = { Text("Bellek Optimize Edildi", fontWeight = FontWeight.Bold) },
            text = {
                Column {
                    Text("Kişisel hafıza motoru başarıyla tarandı ve optimize edildi.", fontSize = 14.sp)
                    Spacer(modifier = Modifier.height(16.dp))
                    Text("• Taranan Bilgi: ${stats.processed}", fontSize = 13.sp)
                    Text("• Birleştirilen Yinelenenler: ${stats.merged}", fontSize = 13.sp)
                    Text("• Zaman Aşımına Uğrayanlar: ${stats.decayed}", fontSize = 13.sp)
                    Text("• Çelişkili Düzeltmeler: ${stats.contradicted}", fontSize = 13.sp)
                }
            },
            confirmButton = {
                Button(
                    onClick = { showConsolidationDialog = null },
                    colors = ButtonDefaults.buttonColors(containerColor = LoginButton)
                ) {
                    Text("Harika")
                }
            }
        )
    }
}

// ── Helper UI Components ──────────────────────────────────────────────────

@Composable
fun MemoryItemRow(memory: UserMemory, onDelete: () -> Unit) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(containerColor = Color.White)
    ) {
        Row(
            modifier = Modifier.padding(14.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            val (icon, tint) = getCategoryMeta(memory.memoryType)
            
            Box(
                modifier = Modifier
                    .size(36.dp)
                    .clip(CircleShape)
                    .background(tint.copy(alpha = 0.1f)),
                contentAlignment = Alignment.Center
            ) {
                Icon(icon, contentDescription = null, tint = tint, modifier = Modifier.size(18.dp))
            }
            Spacer(modifier = Modifier.width(14.dp))
            
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = formatMemoryTypeLabel(memory.memoryType),
                    fontWeight = FontWeight.Bold,
                    fontSize = 11.sp,
                    color = LoginSecondaryText
                )
                Spacer(modifier = Modifier.height(2.dp))
                Text(
                    text = memory.memoryText,
                    fontSize = 13.sp,
                    fontWeight = FontWeight.Medium,
                    color = LoginTextColor,
                    lineHeight = 17.sp
                )
            }
            
            IconButton(onClick = onDelete) {
                Icon(
                    Icons.Default.Delete,
                    contentDescription = "Bilgiyi Sil",
                    tint = Color.Red.copy(alpha = 0.7f),
                    modifier = Modifier.size(20.dp)
                )
            }
        }
    }
}

private fun getCategoryMeta(type: String): Pair<ImageVector, Color> {
    return when (type) {
        "preference" -> Icons.Default.ThumbUp to LoginButton
        "coping_strategy" -> Icons.Default.Favorite to Color(0xFFE91E63)
        "routine" -> Icons.Default.DateRange to Color(0xFF9C27B0)
        "goal" -> Icons.Default.Star to Color(0xFFFF9800)
        "boundary" -> Icons.Default.Lock to Color(0xFF4CAF50)
        "wellness_pattern" -> Icons.Default.CheckCircle to Color(0xFF00BCD4)
        "important_person" -> Icons.Default.Person to Color(0xFF3F51B5)
        "recurring_stressor" -> Icons.Default.Warning to Color(0xFFFF5722)
        else -> Icons.Default.Info to Color.Gray
    }
}

private fun formatMemoryTypeLabel(type: String): String {
    return when (type) {
        "preference" -> "Tercih"
        "coping_strategy" -> "Destek Stratejisi"
        "routine" -> "Rutin"
        "goal" -> "Hedef"
        "boundary" -> "Sınır"
        "wellness_pattern" -> "İyi Oluş Örüntüsü"
        "important_person" -> "Önemli Kişi"
        "recurring_stressor" -> "Stres Etkeni"
        else -> "Hafıza"
    }
}
