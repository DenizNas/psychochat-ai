package com.psikochat.app.ui.home

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.psikochat.app.data.model.Resource
import com.psikochat.app.data.model.WellnessPlanResponse
import com.psikochat.app.data.repository.WellnessScheduleRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch

class WellnessScheduleViewModel(private val repository: WellnessScheduleRepository) : ViewModel() {

    private val _scheduleState = MutableStateFlow<Resource<WellnessPlanResponse>>(Resource.Loading())
    val scheduleState: StateFlow<Resource<WellnessPlanResponse>> = _scheduleState

    private val _refreshState = MutableStateFlow<Resource<WellnessPlanResponse>?>(null)
    val refreshState: StateFlow<Resource<WellnessPlanResponse>?> = _refreshState

    init {
        loadSchedule()
    }

    fun loadSchedule() {
        viewModelScope.launch {
            _scheduleState.value = Resource.Loading()
            val result = repository.getWellnessPlan()
            _scheduleState.value = result
        }
    }

    fun refreshSchedule() {
        viewModelScope.launch {
            _refreshState.value = Resource.Loading()
            val result = repository.refreshWellnessPlan()
            _refreshState.value = result
            if (result is Resource.Success) {
                _scheduleState.value = result
            }
        }
    }

    fun clearRefreshState() {
        _refreshState.value = null
    }
}
