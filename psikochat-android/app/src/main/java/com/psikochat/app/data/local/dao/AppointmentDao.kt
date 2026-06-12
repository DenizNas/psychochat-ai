package com.psikochat.app.data.local.dao

import androidx.room.*
import com.psikochat.app.data.local.entity.CachedAppointment
import kotlinx.coroutines.flow.Flow

// TODO: Replace local appointment storage with backend appointment API when available.
@Dao
interface AppointmentDao {
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertAppointment(appointment: CachedAppointment)

    @Query("SELECT * FROM cached_appointments WHERE status = 'scheduled' ORDER BY id DESC LIMIT 1")
    fun getNextUpcomingAppointment(): Flow<CachedAppointment?>

    @Query("SELECT * FROM cached_appointments ORDER BY id DESC")
    fun getAllAppointments(): Flow<List<CachedAppointment>>

    @Query("UPDATE cached_appointments SET status = :status WHERE id = :id")
    suspend fun updateAppointmentStatus(id: Int, status: String)
}
