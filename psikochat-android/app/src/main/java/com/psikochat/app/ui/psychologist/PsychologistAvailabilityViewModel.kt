package com.psikochat.app.ui.psychologist

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import com.psikochat.app.data.model.*
import com.psikochat.app.data.repository.PsychologistAvailabilityRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

class PsychologistAvailabilityViewModel(
    private val repository: PsychologistAvailabilityRepository
) : ViewModel() {

    private val _availabilityState = MutableStateFlow<Resource<List<AvailabilityDto>>>(Resource.Loading())
    val availabilityState: StateFlow<Resource<List<AvailabilityDto>>> = _availabilityState.asStateFlow()

    private val _createState = MutableStateFlow<Resource<AvailabilityDto>?>(null)
    val createState: StateFlow<Resource<AvailabilityDto>?> = _createState.asStateFlow()

    private val _deleteState = MutableStateFlow<Resource<Boolean>?>(null)
    val deleteState: StateFlow<Resource<Boolean>?> = _deleteState.asStateFlow()

    private val _slotsState = MutableStateFlow<Resource<AvailableSlotsResponse>?>(null)
    val slotsState: StateFlow<Resource<AvailableSlotsResponse>?> = _slotsState.asStateFlow()

    init {
        loadAvailability()
    }

    fun loadAvailability() {
        viewModelScope.launch {
            _availabilityState.value = Resource.Loading()
            _availabilityState.value = repository.getMyAvailability()
        }
    }

    fun createAvailability(dayOfWeek: Int, startTime: String, endTime: String, duration: Int) {
        viewModelScope.launch {
            _createState.value = Resource.Loading()
            val result = repository.createAvailability(dayOfWeek, startTime, endTime, duration)
            _createState.value = result
            if (result is Resource.Success) {
                loadAvailability()
            }
        }
    }

    fun deleteAvailability(id: Int) {
        viewModelScope.launch {
            _deleteState.value = Resource.Loading()
            val result = repository.deleteAvailability(id)
            _deleteState.value = result
            if (result is Resource.Success) {
                loadAvailability()
            }
        }
    }

    fun clearMutations() {
        _createState.value = null
        _deleteState.value = null
    }

    fun loadAvailableSlots(psychologistId: Int, date: String) {
        viewModelScope.launch {
            _slotsState.value = Resource.Loading()
            _slotsState.value = repository.getAvailableSlots(psychologistId, date)
        }
    }

    fun clearSlots() {
        _slotsState.value = null
    }
}

class PsychologistAvailabilityViewModelFactory(
    private val repository: PsychologistAvailabilityRepository
) : ViewModelProvider.Factory {
    @Suppress("UNCHECKED_CAST")
    override fun <T : ViewModel> create(modelClass: Class<T>): T {
        if (modelClass.isAssignableFrom(PsychologistAvailabilityViewModel::class.java)) {
            return PsychologistAvailabilityViewModel(repository) as T
        }
        throw IllegalArgumentException("Unknown ViewModel class")
    }
}
