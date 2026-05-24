package com.psikochat.app.ui.home

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.psikochat.app.data.local.TokenManager
import com.psikochat.app.data.sync.SyncManager
import com.psikochat.app.data.model.Resource
import com.psikochat.app.data.model.WellnessReport
import com.psikochat.app.data.repository.WellnessReportRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch

class WellnessReportViewModel(
    private val repository: WellnessReportRepository,
    private val tokenManager: TokenManager,
    private val syncManager: SyncManager
) : ViewModel() {

    private val _reportState = MutableStateFlow<Resource<WellnessReport>>(Resource.Loading())
    val reportState: StateFlow<Resource<WellnessReport>> = _reportState

    private val _selectedPeriod = MutableStateFlow("weekly")
    val selectedPeriod: StateFlow<String> = _selectedPeriod

    init {
        loadReport()
    }

    fun selectPeriod(period: String) {
        if (_selectedPeriod.value != period) {
            _selectedPeriod.value = period
            loadReport()
        }
    }

    fun loadReport() {
        viewModelScope.launch {
            _reportState.value = Resource.Loading()
            val period = _selectedPeriod.value
            val username = tokenManager.getUsername().first()
            val isOnline = syncManager.isOnline.value
            // For both daily and weekly, query last 7 days of metadata to cross sufficient history limits
            val result = repository.getWellnessReport(
                userId = username,
                period = period,
                days = 7,
                isOnline = isOnline
            )
            _reportState.value = result
        }
    }
}
