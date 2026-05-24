package com.psikochat.app.ui.insights

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.psikochat.app.data.model.WellnessReportResponse
import com.psikochat.app.data.model.ReflectionResponse
import com.psikochat.app.data.model.Resource
import com.psikochat.app.data.repository.ReflectionRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch

sealed class WellnessReportUiState {
    object Loading : WellnessReportUiState()
    data class Success(val report: WellnessReportResponse) : WellnessReportUiState()
    object Empty : WellnessReportUiState()
    data class Error(val message: String) : WellnessReportUiState()
}

sealed class ReflectionUiState {
    object Loading : ReflectionUiState()
    data class Success(val reflection: ReflectionResponse) : ReflectionUiState()
    object Empty : ReflectionUiState()
    data class Error(val message: String) : ReflectionUiState()
}

class ReflectionViewModel(private val repository: ReflectionRepository) : ViewModel() {

    private val _reportState = MutableStateFlow<WellnessReportUiState>(WellnessReportUiState.Loading)
    val reportState: StateFlow<WellnessReportUiState> = _reportState

    private val _reflectionState = MutableStateFlow<ReflectionUiState>(ReflectionUiState.Loading)
    val reflectionState: StateFlow<ReflectionUiState> = _reflectionState

    fun loadWellnessReport(period: String, days: Int = 7) {
        viewModelScope.launch {
            _reportState.value = WellnessReportUiState.Loading
            val resource = repository.getWellnessReport(period, days)
            if (resource is Resource.Success) {
                val report = resource.data
                if (report == null || report.total_messages < 4) {
                    _reportState.value = WellnessReportUiState.Empty
                } else {
                    _reportState.value = WellnessReportUiState.Success(report)
                }
            } else if (resource is Resource.Error) {
                _reportState.value = WellnessReportUiState.Error(resource.message ?: "Rapor yüklenemedi.")
            }
        }
    }

    fun loadReflection(period: String) {
        viewModelScope.launch {
            _reflectionState.value = ReflectionUiState.Loading
            val resource = repository.getReflections(period)
            if (resource is Resource.Success) {
                val reflection = resource.data
                if (reflection == null || reflection.reflection_title == "Yetersiz Veri") {
                    _reflectionState.value = ReflectionUiState.Empty
                } else {
                    _reflectionState.value = ReflectionUiState.Success(reflection)
                }
            } else if (resource is Resource.Error) {
                _reflectionState.value = ReflectionUiState.Error(resource.message ?: "Refleksiyon yüklenemedi.")
            }
        }
    }
}
