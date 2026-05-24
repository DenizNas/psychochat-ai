package com.psikochat.app.ui.insights

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.psikochat.app.data.model.BehavioralInsight
import com.psikochat.app.data.model.EmotionSummaryResponse
import com.psikochat.app.data.model.SmartIntervention
import com.psikochat.app.data.model.Resource
import com.psikochat.app.data.repository.AnalyticsRepository
import kotlinx.coroutines.async
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch

sealed class InsightsUiState {
    object Loading : InsightsUiState()
    data class Success(
        val insights: List<BehavioralInsight>,
        val summary: EmotionSummaryResponse,
        val interventions: List<SmartIntervention>
    ) : InsightsUiState()
    object Empty : InsightsUiState()
    data class Error(val message: String) : InsightsUiState()
}

class InsightsViewModel(private val repository: AnalyticsRepository) : ViewModel() {

    private val _uiState = MutableStateFlow<InsightsUiState>(InsightsUiState.Loading)
    val uiState: StateFlow<InsightsUiState> = _uiState

    fun loadInsightsAndSummary(days: Int = 7) {
        viewModelScope.launch {
            _uiState.value = InsightsUiState.Loading
            
            // Execute parallel network calls for optimal performance
            val insightsDeferred = async { repository.getInsights(days) }
            val summaryDeferred = async { repository.getEmotionSummary(days) }
            val interventionsDeferred = async { repository.getInterventions(days) }

            val insightsResource = insightsDeferred.await()
            val summaryResource = summaryDeferred.await()
            val interventionsResource = interventionsDeferred.await()

            if (insightsResource is Resource.Success && 
                summaryResource is Resource.Success && 
                interventionsResource is Resource.Success) {
                
                val insightsData = insightsResource.data ?: emptyList()
                val summaryData = summaryResource.data
                val interventionsData = interventionsResource.data ?: emptyList()
                
                // Enforce strict noise threshold: less than 4 interactions is mapped to empty state
                if (summaryData == null || summaryData.total_messages < 4) {
                    _uiState.value = InsightsUiState.Empty
                } else {
                    _uiState.value = InsightsUiState.Success(
                        insights = insightsData,
                        summary = summaryData,
                        interventions = interventionsData
                    )
                }
            } else {
                val errorMsg = when {
                    insightsResource is Resource.Error -> insightsResource.message
                    summaryResource is Resource.Error -> summaryResource.message
                    interventionsResource is Resource.Error -> interventionsResource.message
                    else -> "Veriler yüklenirken bir hata oluştu."
                }
                _uiState.value = InsightsUiState.Error(errorMsg ?: "Veriler yüklenemedi.")
            }
        }
    }
}
