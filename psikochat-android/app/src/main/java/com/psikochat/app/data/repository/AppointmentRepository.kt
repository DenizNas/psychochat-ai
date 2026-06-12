package com.psikochat.app.data.repository

import com.psikochat.app.data.local.dao.AppointmentDao
import com.psikochat.app.data.local.entity.CachedAppointment
import kotlinx.coroutines.flow.Flow

// TODO: Replace local appointment storage with backend appointment API when available.
class AppointmentRepository(private val appointmentDao: AppointmentDao) {

    fun getNextUpcomingAppointment(): Flow<CachedAppointment?> {
        return appointmentDao.getNextUpcomingAppointment()
    }

    fun getAllAppointments(): Flow<List<CachedAppointment>> {
        return appointmentDao.getAllAppointments()
    }

    suspend fun insertAppointment(appointment: CachedAppointment) {
        appointmentDao.insertAppointment(appointment)
    }

    suspend fun cancelAppointment(id: Int) {
        appointmentDao.updateAppointmentStatus(id, "cancelled")
    }
}
