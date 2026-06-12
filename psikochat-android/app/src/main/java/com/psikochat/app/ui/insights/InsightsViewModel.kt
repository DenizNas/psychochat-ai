package com.psikochat.app.ui.insights

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.psikochat.app.data.model.BehavioralInsight
import com.psikochat.app.data.model.WellnessDashboardResponse
import com.psikochat.app.data.model.SmartIntervention
import com.psikochat.app.data.model.Resource
import com.psikochat.app.data.repository.AnalyticsRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch

// EmotionSummaryResponse does not exist — WellnessDashboardResponse is the correct model
// that AnalyticsRepository.getEmotionSummary() returns (via WellnessDashboardResponse fields).
// We use WellnessDashboardResponse as the summary carrier for InsightsScreen.
sealed class InsightsUiState {
    object Loading : InsightsUiState()
    data class Success(
        val insights: List<BehavioralInsight>,
        val summary: WellnessDashboardResponse,
        val interventions: List<SmartIntervention>
    ) : InsightsUiState()
    object Empty : InsightsUiState()
    data class Error(val message: String, val isPremiumRequired: Boolean = false) : InsightsUiState()
}

class InsightsViewModel(private val repository: AnalyticsRepository) : ViewModel() {

    private val _uiState = MutableStateFlow<InsightsUiState>(InsightsUiState.Loading)
    val uiState: StateFlow<InsightsUiState> = _uiState

    fun loadInsightsAndSummary(days: Int = 7) {
        viewModelScope.launch {
            if (com.psikochat.app.ui.home.SubscriptionViewModel.getCachedSubscription()?.has_premium != true) {
                _uiState.value = InsightsUiState.Error("Gelişmiş analizler Premium üyelik gerektirir.", isPremiumRequired = true)
                return@launch
            }
            _uiState.value = InsightsUiState.Loading

            // Optimized: Fetch the unified dashboard response once instead of 3 redundant calls
            val summaryResource = repository.getEmotionSummary(days)

            if (summaryResource is Resource.Success) {
                val summaryData = summaryResource.data

                // Enforce strict noise threshold: less than 4 interactions is mapped to empty state
                if (summaryData == null || summaryData.overview.totalMessages < 4) {
                    _uiState.value = InsightsUiState.Empty
                } else {
                    _uiState.value = InsightsUiState.Success(
                        insights = summaryData.sections.topInsights,
                        summary = summaryData,
                        interventions = summaryData.sections.activeInterventions
                    )
                }
            } else {
                val errorRes = summaryResource as? Resource.Error
                val errorMsg = errorRes?.message ?: "Veriler yüklenirken bir hata oluştu."
                val isPremium = errorRes?.isPremiumRequired ?: false
                _uiState.value = InsightsUiState.Error(errorMsg, isPremiumRequired = isPremium)
            }
        }
    }
}
