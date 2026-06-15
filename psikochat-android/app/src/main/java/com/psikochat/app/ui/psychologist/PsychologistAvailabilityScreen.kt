package com.psikochat.app.ui.psychologist

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.KeyboardArrowDown
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
import com.psikochat.app.data.model.AvailabilityDto
import com.psikochat.app.data.model.Resource
import com.psikochat.app.data.repository.PsychologistAvailabilityRepository
import com.psikochat.app.ui.theme.*
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun PsychologistAvailabilityScreen(navController: NavController, tokenManager: TokenManager) {
    val context = androidx.compose.ui.platform.LocalContext.current
    val api = RetrofitClient.create(tokenManager)
    val repository = PsychologistAvailabilityRepository(api)
    val factory = remember {
        PsychologistAvailabilityViewModelFactory(repository)
    }
    val viewModel: PsychologistAvailabilityViewModel = viewModel(factory = factory)

    val availabilityState by viewModel.availabilityState.collectAsState()
    val createState by viewModel.createState.collectAsState()
    val deleteState by viewModel.deleteState.collectAsState()

    val scope = rememberCoroutineScope()
    val snackbarHostState = remember { SnackbarHostState() }

    // Input States
    var selectedDayIndex by remember { mutableStateOf(0) } // 0: Pazartesi, ..., 6: Pazar
    var selectedStartTime by remember { mutableStateOf("09:00") }
    var selectedEndTime by remember { mutableStateOf("17:00") }
    var selectedDuration by remember { mutableStateOf(60) } // 30, 45, 60, 90

    // Dropdown States
    var startDropdownExpanded by remember { mutableStateOf(false) }
    var endDropdownExpanded by remember { mutableStateOf(false) }

    val daysOfWeek = listOf("Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar")
    val durations = listOf(30 to "30 dk", 45 to "45 dk", 60 to "60 dk", 90 to "90 dk")

    val timesList = remember {
        (8..22).flatMap { hour ->
            listOf(
                String.format("%02d:00", hour),
                String.format("%02d:30", hour)
            )
        }
    }

    // Observe mutations
    LaunchedEffect(createState) {
        if (createState is Resource.Success) {
            snackbarHostState.showSnackbar("Müsaitlik başarıyla eklendi.")
            viewModel.clearMutations()
        } else if (createState is Resource.Error) {
            snackbarHostState.showSnackbar((createState as Resource.Error).message ?: "Ekleme sırasında bir hata oluştu.")
            viewModel.clearMutations()
        }
    }

    LaunchedEffect(deleteState) {
        if (deleteState is Resource.Success) {
            snackbarHostState.showSnackbar("Müsaitlik silindi.")
            viewModel.clearMutations()
        } else if (deleteState is Resource.Error) {
            snackbarHostState.showSnackbar((deleteState as Resource.Error).message ?: "Silme sırasında bir hata oluştu.")
            viewModel.clearMutations()
        }
    }

    Scaffold(
        snackbarHost = { SnackbarHost(snackbarHostState) },
        topBar = {
            CenterAlignedTopAppBar(
                title = {
                    Text(
                        "Müsaitlik Yönetimi",
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Bold,
                        color = LoginTextColor
                    )
                },
                navigationIcon = {
                    IconButton(onClick = { navController.popBackStack() }) {
                        Icon(
                            imageVector = Icons.AutoMirrored.Filled.ArrowBack,
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
                .padding(horizontal = 24.dp)
        ) {
            // 1. Add Availability Card
            Surface(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(vertical = 8.dp),
                shape = RoundedCornerShape(24.dp),
                color = PremiumWhiteCard,
                border = BorderStroke(1.dp, SoftMintAccent.copy(alpha = 0.5f)),
                shadowElevation = 2.dp
            ) {
                Column(
                    modifier = Modifier.padding(20.dp),
                    horizontalAlignment = Alignment.Start
                ) {
                    Text(
                        text = "Yeni Müsaitlik Ekle",
                        fontSize = 15.sp,
                        fontWeight = FontWeight.Bold,
                        color = LoginTextColor
                    )
                    Spacer(modifier = Modifier.height(12.dp))

                    Text(
                        text = "Gün",
                        fontSize = 12.sp,
                        fontWeight = FontWeight.Bold,
                        color = LoginSecondaryText
                    )
                    Spacer(modifier = Modifier.height(6.dp))

                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .horizontalScroll(rememberScrollState()),
                        horizontalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        daysOfWeek.forEachIndexed { index, day ->
                            val isSelected = selectedDayIndex == index
                            Surface(
                                modifier = Modifier.clickable { selectedDayIndex = index },
                                shape = RoundedCornerShape(12.dp),
                                color = if (isSelected) DarkTealPrimary else SoftMintAccent.copy(alpha = 0.2f),
                                border = BorderStroke(1.dp, if (isSelected) DarkTealPrimary else Color.Transparent)
                            ) {
                                Text(
                                    text = day,
                                    color = if (isSelected) Color.White else LoginTextColor,
                                    fontSize = 12.sp,
                                    fontWeight = FontWeight.SemiBold,
                                    modifier = Modifier.padding(horizontal = 12.dp, vertical = 8.dp)
                                )
                            }
                        }
                    }

                    Spacer(modifier = Modifier.height(16.dp))

                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(16.dp)
                    ) {
                        // Start Time Dropdown
                        Column(modifier = Modifier.weight(1f)) {
                            Text(
                                text = "Başlangıç",
                                fontSize = 12.sp,
                                fontWeight = FontWeight.Bold,
                                color = LoginSecondaryText
                            )
                            Spacer(modifier = Modifier.height(6.dp))
                            Box {
                                OutlinedCard(
                                    onClick = { startDropdownExpanded = true },
                                    shape = RoundedCornerShape(12.dp),
                                    border = BorderStroke(1.dp, Color.LightGray.copy(alpha = 0.5f)),
                                    modifier = Modifier.fillMaxWidth()
                                ) {
                                    Row(
                                        modifier = Modifier
                                            .fillMaxWidth()
                                            .padding(horizontal = 12.dp, vertical = 12.dp),
                                        horizontalArrangement = Arrangement.SpaceBetween,
                                        verticalAlignment = Alignment.CenterVertically
                                    ) {
                                        Text(text = selectedStartTime, fontSize = 14.sp, fontWeight = FontWeight.SemiBold, color = LoginTextColor)
                                        Icon(Icons.Default.KeyboardArrowDown, contentDescription = null, tint = LoginSecondaryText)
                                    }
                                }
                                DropdownMenu(
                                    expanded = startDropdownExpanded,
                                    onDismissRequest = { startDropdownExpanded = false }
                                ) {
                                    timesList.forEach { t ->
                                        DropdownMenuItem(
                                            text = { Text(t) },
                                            onClick = {
                                                selectedStartTime = t
                                                startDropdownExpanded = false
                                            }
                                        )
                                    }
                                }
                            }
                        }

                        // End Time Dropdown
                        Column(modifier = Modifier.weight(1f)) {
                            Text(
                                text = "Bitiş",
                                fontSize = 12.sp,
                                fontWeight = FontWeight.Bold,
                                color = LoginSecondaryText
                            )
                            Spacer(modifier = Modifier.height(6.dp))
                            Box {
                                OutlinedCard(
                                    onClick = { endDropdownExpanded = true },
                                    shape = RoundedCornerShape(12.dp),
                                    border = BorderStroke(1.dp, Color.LightGray.copy(alpha = 0.5f)),
                                    modifier = Modifier.fillMaxWidth()
                                ) {
                                    Row(
                                        modifier = Modifier
                                            .fillMaxWidth()
                                            .padding(horizontal = 12.dp, vertical = 12.dp),
                                        horizontalArrangement = Arrangement.SpaceBetween,
                                        verticalAlignment = Alignment.CenterVertically
                                    ) {
                                        Text(text = selectedEndTime, fontSize = 14.sp, fontWeight = FontWeight.SemiBold, color = LoginTextColor)
                                        Icon(Icons.Default.KeyboardArrowDown, contentDescription = null, tint = LoginSecondaryText)
                                    }
                                }
                                DropdownMenu(
                                    expanded = endDropdownExpanded,
                                    onDismissRequest = { endDropdownExpanded = false }
                                ) {
                                    timesList.forEach { t ->
                                        DropdownMenuItem(
                                            text = { Text(t) },
                                            onClick = {
                                                selectedEndTime = t
                                                endDropdownExpanded = false
                                            }
                                        )
                                    }
                                }
                            }
                        }
                    }

                    Spacer(modifier = Modifier.height(16.dp))

                    Text(
                        text = "Seans Süresi",
                        fontSize = 12.sp,
                        fontWeight = FontWeight.Bold,
                        color = LoginSecondaryText
                    )
                    Spacer(modifier = Modifier.height(6.dp))
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        durations.forEach { (mins, label) ->
                            val isSelected = selectedDuration == mins
                            Surface(
                                modifier = Modifier
                                    .weight(1f)
                                    .clickable { selectedDuration = mins },
                                shape = RoundedCornerShape(12.dp),
                                color = if (isSelected) DarkTealPrimary else SoftMintAccent.copy(alpha = 0.2f),
                                border = BorderStroke(1.dp, if (isSelected) DarkTealPrimary else Color.Transparent)
                            ) {
                                Text(
                                    text = label,
                                    color = if (isSelected) Color.White else LoginTextColor,
                                    fontSize = 12.sp,
                                    fontWeight = FontWeight.SemiBold,
                                    textAlign = TextAlign.Center,
                                    modifier = Modifier.padding(vertical = 10.dp)
                                )
                            }
                        }
                    }

                    Spacer(modifier = Modifier.height(20.dp))

                    val isAdding = createState is Resource.Loading
                    Button(
                        onClick = {
                            viewModel.createAvailability(
                                dayOfWeek = selectedDayIndex,
                                startTime = selectedStartTime,
                                endTime = selectedEndTime,
                                duration = selectedDuration
                            )
                        },
                        enabled = !isAdding,
                        modifier = Modifier
                            .fillMaxWidth()
                            .height(48.dp),
                        shape = RoundedCornerShape(16.dp),
                        colors = ButtonDefaults.buttonColors(containerColor = DarkTealPrimary)
                    ) {
                        if (isAdding) {
                            CircularProgressIndicator(color = Color.White, modifier = Modifier.size(20.dp))
                        } else {
                            Text("Müsaitlik Ekle", color = Color.White, fontWeight = FontWeight.Bold)
                        }
                    }
                }
            }

            Spacer(modifier = Modifier.height(12.dp))

            Text(
                text = "Mevcut Müsaitlikleriniz",
                fontSize = 14.sp,
                fontWeight = FontWeight.Bold,
                color = LoginTextColor,
                modifier = Modifier.padding(vertical = 8.dp)
            )

            when (val state = availabilityState) {
                is Resource.Loading -> {
                    Box(modifier = Modifier.weight(1f).fillMaxWidth(), contentAlignment = Alignment.Center) {
                        CircularProgressIndicator(color = DarkTealPrimary)
                    }
                }
                is Resource.Error -> {
                    Box(modifier = Modifier.weight(1f).fillMaxWidth(), contentAlignment = Alignment.Center) {
                        Column(horizontalAlignment = Alignment.CenterHorizontally) {
                            Icon(Icons.Default.Warning, contentDescription = null, tint = DangerRed, modifier = Modifier.size(36.dp))
                            Spacer(modifier = Modifier.height(8.dp))
                            Text(state.message ?: "Müsaitlik listesi alınamadı.", color = LoginTextColor, textAlign = TextAlign.Center)
                        }
                    }
                }
                is Resource.Success -> {
                    val list = state.data ?: emptyList()
                    if (list.isEmpty()) {
                        Box(modifier = Modifier.weight(1f).fillMaxWidth(), contentAlignment = Alignment.Center) {
                            Text(
                                "Müsaitlik saati tanımlanmamış. Yukarıdan ekleyebilirsiniz.",
                                color = LoginSecondaryText,
                                textAlign = TextAlign.Center,
                                fontSize = 13.sp
                            )
                        }
                    } else {
                        LazyColumn(
                            modifier = Modifier.weight(1f),
                            verticalArrangement = Arrangement.spacedBy(10.dp),
                            contentPadding = PaddingValues(bottom = 24.dp)
                        ) {
                            items(list, key = { it.id }) { item ->
                                val dayName = daysOfWeek.getOrNull(item.dayOfWeek) ?: ""
                                Surface(
                                    modifier = Modifier.fillMaxWidth(),
                                    shape = RoundedCornerShape(16.dp),
                                    color = PremiumWhiteCard,
                                    border = BorderStroke(1.dp, SoftMintAccent.copy(alpha = 0.5f))
                                ) {
                                    Row(
                                        modifier = Modifier.padding(16.dp),
                                        verticalAlignment = Alignment.CenterVertically,
                                        horizontalArrangement = Arrangement.SpaceBetween
                                    ) {
                                        Column {
                                            Text(
                                                text = dayName,
                                                fontWeight = FontWeight.Bold,
                                                fontSize = 14.sp,
                                                color = LoginTextColor
                                            )
                                            Spacer(modifier = Modifier.height(4.dp))
                                            Text(
                                                text = "${item.startTime} - ${item.endTime} (${item.slotDurationMinutes} dk seanslar)",
                                                fontSize = 12.sp,
                                                color = LoginSecondaryText
                                            )
                                        }

                                        IconButton(
                                            onClick = { viewModel.deleteAvailability(item.id) }
                                        ) {
                                            Icon(
                                                imageVector = Icons.Default.Delete,
                                                contentDescription = "Sil",
                                                tint = DangerRed
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
}
