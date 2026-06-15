package com.psikochat.app.data.repository

import com.psikochat.app.data.api.PsikoApi
import com.psikochat.app.data.local.dao.AppointmentDao
import com.psikochat.app.data.local.entity.CachedAppointment
import com.psikochat.app.data.model.AppointmentDto
import com.psikochat.app.data.model.CreateAppointmentRequest
import com.psikochat.app.data.model.PsychologistDto
import com.psikochat.app.data.model.Resource
import kotlinx.coroutines.flow.Flow
import java.io.IOException

class AppointmentRepository(
    private val api: PsikoApi,
    private val appointmentDao: AppointmentDao,
    private val context: android.content.Context
) {

    fun getNextUpcomingAppointment(): Flow<CachedAppointment?> {
        return appointmentDao.getNextUpcomingAppointment()
    }

    fun getAllAppointments(): Flow<List<CachedAppointment>> {
        return appointmentDao.getAllAppointments()
    }

    suspend fun getApprovedPsychologists(): Resource<List<PsychologistDto>> {
        return try {
            val list = api.getPsychologists()
            Resource.Success(list)
        } catch (e: Exception) {
            Resource.Error(e.message ?: "Psikolog listesi yüklenemedi")
        }
    }

    suspend fun createAppointment(psychologistUsername: String, date: String, time: String): Resource<AppointmentDto> {
        return try {
            val appt = api.createAppointment(CreateAppointmentRequest(psychologistUsername, date, time))
            try {
                val cached = CachedAppointment(
                    id = appt.id,
                    psychologistName = appt.psychologistName ?: psychologistUsername,
                    psychologistSpecialty = appt.psychologistSpecialty ?: "",
                    appointmentDate = appt.appointmentDate,
                    appointmentTime = appt.appointmentTime,
                    status = appt.status,
                    createdAt = appt.createdAt ?: ""
                )
                appointmentDao.insertAppointment(cached)
                com.psikochat.app.ui.notification.NotificationScheduler.scheduleAppointmentReminder(context, cached)
            } catch (e: Exception) {
                // Ignore Room cache write issues
            }
            Resource.Success(appt)
        } catch (e: Exception) {
            Resource.Error(e.message ?: "Randevu oluşturulamadı. Lütfen bağlantınızı kontrol edin.")
        }
    }

    suspend fun fetchAppointmentsFromBackend(): Resource<List<AppointmentDto>> {
        return try {
            val list = api.getAppointments()
            try {
                for (appt in list) {
                    val cached = CachedAppointment(
                        id = appt.id,
                        psychologistName = appt.psychologistName ?: (appt.patientName ?: "Danışan"),
                        psychologistSpecialty = appt.psychologistSpecialty ?: "",
                        appointmentDate = appt.appointmentDate,
                        appointmentTime = appt.appointmentTime,
                        status = appt.status,
                        createdAt = appt.createdAt ?: ""
                    )
                    appointmentDao.insertAppointment(cached)
                    if (cached.status == "scheduled") {
                        com.psikochat.app.ui.notification.NotificationScheduler.scheduleAppointmentReminder(context, cached)
                    } else {
                        com.psikochat.app.ui.notification.NotificationScheduler.cancelAppointmentReminder(context, cached.id)
                    }
                }
            } catch (e: Exception) {
                // Ignore cache update issues
            }
            Resource.Success(list)
        } catch (e: Exception) {
            Resource.Error(e.message ?: "Randevular güncellenemedi.")
        }
    }

    suspend fun cancelAppointment(appointmentId: Int): Resource<Boolean> {
        return try {
            api.cancelAppointment(appointmentId)
            try {
                appointmentDao.updateAppointmentStatus(appointmentId, "cancelled")
                com.psikochat.app.ui.notification.NotificationScheduler.cancelAppointmentReminder(context, appointmentId)
            } catch (e: Exception) {
                // Ignore cache update issues
            }
            Resource.Success(true)
        } catch (e: Exception) {
            Resource.Error(e.message ?: "Randevu iptal edilemedi.")
        }
    }
}
