package com.psikochat.app.ui.home

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.psikochat.app.data.model.Resource
import com.psikochat.app.data.model.WellnessDashboardResponse
import com.psikochat.app.data.repository.WellnessDashboardRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch

import com.psikochat.app.data.local.TokenManager
import com.psikochat.app.data.sync.SyncManager
import kotlinx.coroutines.flow.first

class WellnessDashboardViewModel(
    private val repository: WellnessDashboardRepository,
    private val tokenManager: TokenManager,
    private val syncManager: SyncManager
) : ViewModel() {

    private val _dashboardState = MutableStateFlow<Resource<WellnessDashboardResponse>>(Resource.Loading())
    val dashboardState: StateFlow<Resource<WellnessDashboardResponse>> = _dashboardState

    private val _selectedDays = MutableStateFlow(7)
    val selectedDays: StateFlow<Int> = _selectedDays

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
            _dashboardState.value = Resource.Loading()
            val username = tokenManager.getUsername().first()
            val isOnline = syncManager.isOnline.value
            val result = repository.getWellnessDashboard(
                userId = username,
                days = _selectedDays.value,
                isOnline = isOnline
            )
            _dashboardState.value = result
        }
    }
}
