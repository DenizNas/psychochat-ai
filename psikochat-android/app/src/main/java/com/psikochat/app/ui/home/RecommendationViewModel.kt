package com.psikochat.app.ui.home

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.psikochat.app.data.model.Resource
import com.psikochat.app.data.model.WellnessRecommendation
import com.psikochat.app.data.repository.RecommendationRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch

/**
 * RecommendationViewModel
 * =======================
 * Faz 10 Prompt 7 — Advanced Analytics & Recommendation Engine
 *
 * ViewModel for the RecommendationScreen / WellnessDashboard recommendations section.
 *
 * State machine:
 *   Loading → Success(recs) | Error(msg) | Empty (no consent / privacy mode)
 *
 * Privacy:
 *   - No raw text is stored or passed to UI
 *   - All recommendation content is wellness-safe (no medical diagnosis language)
 */
class RecommendationViewModel(
    private val repository: RecommendationRepository
) : ViewModel() {

    private val _state = MutableStateFlow<Resource<List<WellnessRecommendation>>>(Resource.Loading())
    val state: StateFlow<Resource<List<WellnessRecommendation>>> = _state

    private val _isRefreshing = MutableStateFlow(false)
    val isRefreshing: StateFlow<Boolean> = _isRefreshing

    private val _feedbackState = MutableStateFlow<FeedbackUiState>(FeedbackUiState.Idle)
    val feedbackState: StateFlow<FeedbackUiState> = _feedbackState

    init {
        loadRecommendations()
    }

    /** Loads active (cached) recommendations from backend. */
    fun loadRecommendations() {
        viewModelScope.launch {
            if (SubscriptionViewModel.getCachedSubscription()?.has_premium != true) {
                _state.value = Resource.Error("Premium Öneriler", isPremiumRequired = true)
                return@launch
            }
            _state.value = Resource.Loading()
            _state.value = repository.getRecommendations()
        }
    }

    /**
     * Pull-to-refresh: asks backend to generate fresh recommendations.
     * Respects privacy_mode and wellness_insights_consent checks server-side.
     */
    fun refresh() {
        viewModelScope.launch {
            if (SubscriptionViewModel.getCachedSubscription()?.has_premium != true) {
                _state.value = Resource.Error("Premium Öneriler", isPremiumRequired = true)
                return@launch
            }
            _isRefreshing.value = true
            when (val result = repository.refreshRecommendations()) {
                is Resource.Success -> {
                    // After refresh, reload active recs to get full list
                    _state.value = Resource.Success(result.data?.recommendations ?: emptyList())
                }
                is Resource.Error -> {
                    _state.value = Resource.Error(result.message ?: "Öneriler yenilenemedi.", isPremiumRequired = result.isPremiumRequired)
                }
                is Resource.Loading -> { /* no-op */ }
            }
            _isRefreshing.value = false
        }
    }

    /**
     * Submits user feedback for a recommendation.
     *
     * @param recId  The recommendation ID
     * @param feedback  "helpful" | "not_helpful" | "dismissed"
     */
    fun submitFeedback(recId: String, feedback: String) {
        viewModelScope.launch {
            _feedbackState.value = FeedbackUiState.Loading
            when (repository.submitFeedback(recId, feedback)) {
                is Resource.Success -> {
                    _feedbackState.value = FeedbackUiState.Success(recId, feedback)
                    // Optimistically remove/update from local state
                    _updateLocalStatus(recId, feedback)
                }
                is Resource.Error -> {
                    _feedbackState.value = FeedbackUiState.Error("Geri bildirim gönderilemedi.")
                }
                is Resource.Loading -> { /* no-op */ }
            }
        }
    }

    /** Resets feedback state to idle (e.g. after snackbar shown). */
    fun resetFeedbackState() {
        _feedbackState.value = FeedbackUiState.Idle
    }

    /**
     * Optimistically updates local recommendation list after feedback.
     * "dismissed" removes the rec from the active list immediately.
     */
    private fun _updateLocalStatus(recId: String, feedback: String) {
        val current = (_state.value as? Resource.Success)?.data ?: return
        val updated = if (feedback == "dismissed") {
            current.filter { it.id != recId }
        } else {
            current.map { rec ->
                if (rec.id == recId) rec.copy(status = "completed") else rec
            }
        }
        _state.value = Resource.Success(updated)
    }
}

/** Sealed state for feedback submission UI. */
sealed class FeedbackUiState {
    object Idle : FeedbackUiState()
    object Loading : FeedbackUiState()
    data class Success(val recId: String, val feedback: String) : FeedbackUiState()
    data class Error(val message: String) : FeedbackUiState()
}
