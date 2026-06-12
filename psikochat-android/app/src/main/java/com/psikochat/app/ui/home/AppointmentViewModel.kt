package com.psikochat.app.ui.home

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import com.psikochat.app.data.local.entity.CachedAppointment
import com.psikochat.app.data.repository.AppointmentRepository
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

// TODO: Replace local appointment storage with backend appointment API when available.
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

    fun bookAppointment(psychologistName: String, specialty: String, date: String, time: String) {
        viewModelScope.launch {
            val appointment = CachedAppointment(
                psychologistName = psychologistName,
                psychologistSpecialty = specialty,
                appointmentDate = date,
                appointmentTime = time,
                createdAt = SimpleDateFormat("yyyy-MM-dd HH:mm:ss", Locale.getDefault()).format(Date())
            )
            repository.insertAppointment(appointment)
        }
    }

    fun cancelAppointment(id: Int) {
        viewModelScope.launch {
            repository.cancelAppointment(id)
        }
    }
}

// TODO: Replace local appointment storage with backend appointment API when available.
class AppointmentViewModelFactory(private val repository: AppointmentRepository) : ViewModelProvider.Factory {
    @Suppress("UNCHECKED_CAST")
    override fun <T : ViewModel> create(modelClass: Class<T>): T {
        if (modelClass.isAssignableFrom(AppointmentViewModel::class.java)) {
            return AppointmentViewModel(repository) as T
        }
        throw IllegalArgumentException("Unknown ViewModel class")
    }
}
