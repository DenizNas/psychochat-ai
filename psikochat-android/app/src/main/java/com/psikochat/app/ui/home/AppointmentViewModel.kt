package com.psikochat.app.ui.home

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import com.psikochat.app.data.local.entity.CachedAppointment
import com.psikochat.app.data.model.AppointmentDto
import com.psikochat.app.data.model.PsychologistDto
import com.psikochat.app.data.model.Resource
import com.psikochat.app.data.repository.AppointmentRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch

class AppointmentViewModel(private val repository: AppointmentRepository) : ViewModel() {

    val nextAppointment: StateFlow<CachedAppointment?> = repository.getNextUpcomingAppointment()
        .stateIn(
            scope = viewModelScope,
            started = SharingStarted.WhileSubscribed(5000),
            initialValue = null
        )

    val allAppointments: StateFlow<List<CachedAppointment>> = repository.getAllAppointments()
        .stateIn(
            scope = viewModelScope,
            started = SharingStarted.WhileSubscribed(5000),
            initialValue = emptyList()
        )

    private val _psychologistsState = MutableStateFlow<Resource<List<PsychologistDto>>>(Resource.Loading())
    val psychologistsState: StateFlow<Resource<List<PsychologistDto>>> = _psychologistsState.asStateFlow()

    private val _bookAppointmentState = MutableStateFlow<Resource<AppointmentDto>?>(null)
    val bookAppointmentState: StateFlow<Resource<AppointmentDto>?> = _bookAppointmentState.asStateFlow()

    private val _fetchState = MutableStateFlow<Resource<List<AppointmentDto>>?>(null)
    val fetchState: StateFlow<Resource<List<AppointmentDto>>?> = _fetchState.asStateFlow()

    init {
        loadApprovedPsychologists()
        loadAppointments()
    }

    fun loadApprovedPsychologists() {
        viewModelScope.launch {
            _psychologistsState.value = Resource.Loading()
            _psychologistsState.value = repository.getApprovedPsychologists()
        }
    }

    fun loadAppointments() {
        viewModelScope.launch {
            _fetchState.value = Resource.Loading()
            _fetchState.value = repository.fetchAppointmentsFromBackend()
        }
    }

    fun bookAppointment(psychologistUsername: String, date: String, time: String) {
        viewModelScope.launch {
            _bookAppointmentState.value = Resource.Loading()
            val result = repository.createAppointment(psychologistUsername, date, time)
            _bookAppointmentState.value = result
            if (result is Resource.Success) {
                loadAppointments()
            }
        }
    }

    fun clearBookAppointmentState() {
        _bookAppointmentState.value = null
    }

    fun cancelAppointment(id: Int) {
        viewModelScope.launch {
            val result = repository.cancelAppointment(id)
            if (result is Resource.Success) {
                loadAppointments()
            }
        }
    }
}

class AppointmentViewModelFactory(private val repository: AppointmentRepository) : ViewModelProvider.Factory {
    @Suppress("UNCHECKED_CAST")
    override fun <T : ViewModel> create(modelClass: Class<T>): T {
        if (modelClass.isAssignableFrom(AppointmentViewModel::class.java)) {
            return AppointmentViewModel(repository) as T
        }
        throw IllegalArgumentException("Unknown ViewModel class")
    }
}
