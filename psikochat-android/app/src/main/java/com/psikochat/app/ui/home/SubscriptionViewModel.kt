package com.psikochat.app.ui.home

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.psikochat.app.data.model.Resource
import com.psikochat.app.data.model.SubscriptionStatusDto
import com.psikochat.app.data.repository.SubscriptionRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

class SubscriptionViewModel(
    private val repository: SubscriptionRepository
) : ViewModel() {

    companion object {
        @Volatile
        private var cachedSubscription: SubscriptionStatusDto? = null

        fun clearCache() {
            cachedSubscription = null
        }

        fun getCachedSubscription(): SubscriptionStatusDto? = cachedSubscription
    }

    private val _currentSubscription = MutableStateFlow<SubscriptionStatusDto?>(cachedSubscription)
    val currentSubscription: StateFlow<SubscriptionStatusDto?> = _currentSubscription.asStateFlow()

    private val _isPremium = MutableStateFlow(cachedSubscription?.has_premium ?: false)
    val isPremium: StateFlow<Boolean> = _isPremium.asStateFlow()

    private val _isProfessionalSupport = MutableStateFlow(
        cachedSubscription?.plan_name?.equals("professional_support", ignoreCase = true) ?: false
    )
    val isProfessionalSupport: StateFlow<Boolean> = _isProfessionalSupport.asStateFlow()

    private val _isLoading = MutableStateFlow(false)
    val isLoading: StateFlow<Boolean> = _isLoading.asStateFlow()

    private val _errorMessage = MutableStateFlow<String?>(null)
    val errorMessage: StateFlow<String?> = _errorMessage.asStateFlow()

    init {
        if (cachedSubscription == null) {
            refreshSubscription()
        }
    }

    fun refreshSubscription() {
        viewModelScope.launch {
            _isLoading.value = true
            _errorMessage.value = null
            when (val result = repository.getMySubscription()) {
                is Resource.Success -> {
                    val sub = result.data
                    cachedSubscription = sub
                    _currentSubscription.value = sub
                    _isPremium.value = sub?.has_premium ?: false
                    _isProfessionalSupport.value = sub?.plan_name?.equals("professional_support", ignoreCase = true) ?: false
                }
                is Resource.Error -> {
                    _errorMessage.value = result.message
                    // If we have cached subscription, we keep it; if not, we default to free
                }
                is Resource.Loading -> { /* no-op */ }
            }
            _isLoading.value = false
        }
    }
}
