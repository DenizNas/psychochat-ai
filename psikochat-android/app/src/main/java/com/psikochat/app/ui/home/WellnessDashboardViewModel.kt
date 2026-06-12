package com.psikochat.app.ui.home

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.psikochat.app.data.model.Resource
import com.psikochat.app.data.model.WellnessDashboardResponse
import com.psikochat.app.data.repository.WellnessDashboardRepository
import com.psikochat.app.data.repository.ProgressRepository
import com.psikochat.app.data.local.entity.ScoreSnapshot
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch

import com.psikochat.app.data.local.TokenManager
import com.psikochat.app.data.sync.SyncManager
import kotlinx.coroutines.flow.first

class WellnessDashboardViewModel(
    private val repository: WellnessDashboardRepository,
    private val tokenManager: TokenManager,
    private val syncManager: SyncManager,
    private val progressRepository: ProgressRepository
) : ViewModel() {

    private val _dashboardState = MutableStateFlow<Resource<WellnessDashboardResponse>>(Resource.Loading())
    val dashboardState: StateFlow<Resource<WellnessDashboardResponse>> = _dashboardState

    private val _selectedDays = MutableStateFlow(7)
    val selectedDays: StateFlow<Int> = _selectedDays

    val last7DaysSnapshots: StateFlow<List<ScoreSnapshot>> = progressRepository.loadLast7Days()
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), emptyList())

    val last30DaysSnapshots: StateFlow<List<ScoreSnapshot>> = progressRepository.loadLast30Days()
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), emptyList())

    init {
        loadDashboard()
    }

    fun selectDays(days: Int) {
        if (_selectedDays.value != days) {
            _selectedDays.value = days
            loadDashboard()
        }
    }

    fun loadDashboard() {
        viewModelScope.launch {
            if (SubscriptionViewModel.getCachedSubscription()?.has_premium != true) {
                _dashboardState.value = Resource.Error("Premium Üyelik Gereklidir.", isPremiumRequired = true)
                return@launch
            }
            _dashboardState.value = Resource.Loading()
            val username = tokenManager.getUsername().first()
            val isOnline = syncManager.isOnline.value
            val result = repository.getWellnessDashboard(
                userId = username,
                days = _selectedDays.value,
                isOnline = isOnline
            )
            _dashboardState.value = result
            
            // Only capture snapshots on successful HTTP REST dashboard load requests
            if (result is Resource.Success && result.data != null) {
                val score = result.data.wellnessScore.score
                if (score != null) {
                    // Triggers local-only boundary protection snapshot logs
                    progressRepository.saveDailyScoreSnapshot(score)
                }
            }
        }
    }
}
