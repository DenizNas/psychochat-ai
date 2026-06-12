package com.psikochat.app.ui.home

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.psikochat.app.data.model.*
import com.psikochat.app.data.repository.SubscriptionRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

class PaymentMethodsViewModel(
    private val repository: SubscriptionRepository
) : ViewModel() {

    private val _plans = MutableStateFlow<List<SubscriptionPlanDto>>(emptyList())
    val plans: StateFlow<List<SubscriptionPlanDto>> = _plans.asStateFlow()

    private val _currentSubscription = MutableStateFlow<SubscriptionStatusDto?>(null)
    val currentSubscription: StateFlow<SubscriptionStatusDto?> = _currentSubscription.asStateFlow()

    private val _paymentHistory = MutableStateFlow<List<PaymentHistoryDto>>(emptyList())
    val paymentHistory: StateFlow<List<PaymentHistoryDto>> = _paymentHistory.asStateFlow()

    private val _isLoading = MutableStateFlow(false)
    val isLoading: StateFlow<Boolean> = _isLoading.asStateFlow()

    private val _errorMessage = MutableStateFlow<String?>(null)
    val errorMessage: StateFlow<String?> = _errorMessage.asStateFlow()

    private val _checkoutUrlToOpen = MutableStateFlow<String?>(null)
    val checkoutUrlToOpen: StateFlow<String?> = _checkoutUrlToOpen.asStateFlow()

    private val _paymentReturnMessage = MutableStateFlow<String?>(null)
    val paymentReturnMessage: StateFlow<String?> = _paymentReturnMessage.asStateFlow()

    init {
        loadPaymentData()
    }

    fun loadPaymentData() {
        viewModelScope.launch {
            _isLoading.value = true
            _errorMessage.value = null
            
            val plansResult = repository.getPlans()
            val subResult = repository.getMySubscription()
            val historyResult = repository.getPaymentHistory()

            if (plansResult is Resource.Error) {
                _errorMessage.value = plansResult.message
            } else if (subResult is Resource.Error) {
                _errorMessage.value = subResult.message
            } else if (historyResult is Resource.Error) {
                _errorMessage.value = historyResult.message
            }

            if (plansResult is Resource.Success) {
                _plans.value = plansResult.data ?: emptyList()
            }
            if (subResult is Resource.Success) {
                _currentSubscription.value = subResult.data
            }
            if (historyResult is Resource.Success) {
                _paymentHistory.value = historyResult.data ?: emptyList()
            }

            _isLoading.value = false
        }
    }

    fun startCheckout(planId: String) {
        viewModelScope.launch {
            _isLoading.value = true
            _errorMessage.value = null
            when (val result = repository.startCheckout(planId)) {
                is Resource.Success -> {
                    _checkoutUrlToOpen.value = result.data?.checkout_url
                }
                is Resource.Error -> {
                    _errorMessage.value = result.message
                }
                is Resource.Loading -> { /* no-op */ }
            }
            _isLoading.value = false
        }
    }

    fun clearCheckoutUrl() {
        _checkoutUrlToOpen.value = null
    }

    fun setPaymentReturnMessage(message: String?) {
        _paymentReturnMessage.value = message
    }

    fun refreshAfterPaymentReturn() {
        viewModelScope.launch {
            _isLoading.value = true
            _errorMessage.value = null
            _checkoutUrlToOpen.value = null
            _paymentReturnMessage.value = "Ödeme sonucu kontrol ediliyor..."
            
            val plansResult = repository.getPlans()
            val subResult = repository.getMySubscription()
            val historyResult = repository.getPaymentHistory()

            if (plansResult is Resource.Error) {
                _errorMessage.value = plansResult.message
            } else if (subResult is Resource.Error) {
                _errorMessage.value = subResult.message
            } else if (historyResult is Resource.Error) {
                _errorMessage.value = historyResult.message
            }

            if (plansResult is Resource.Success) {
                _plans.value = plansResult.data ?: emptyList()
            }
            if (subResult is Resource.Success) {
                val sub = subResult.data
                _currentSubscription.value = sub
                
                if (sub?.has_premium == true) {
                    _paymentReturnMessage.value = "Premium üyeliğin aktif görünüyor."
                } else {
                    _paymentReturnMessage.value = "Ödeme sonucu henüz doğrulanmadı. Birkaç saniye sonra tekrar deneyebilirsin."
                }
            } else {
                _paymentReturnMessage.value = "Ödeme durumu güncellenemedi. Lütfen daha sonra tekrar deneyin."
            }
            
            if (historyResult is Resource.Success) {
                _paymentHistory.value = historyResult.data ?: emptyList()
            }

            _isLoading.value = false
        }
    }
}
