package com.psikochat.app.data.local.entity

import androidx.room.Entity
import androidx.room.PrimaryKey

// TODO: Replace local appointment storage with backend appointment API when available.
@Entity(tableName = "cached_appointments")
data class CachedAppointment(
    @PrimaryKey(autoGenerate = true) val id: Int = 0,
    val psychologistName: String,
    val psychologistSpecialty: String,
    val appointmentDate: String, // e.g., "Bugün", "Yarın", or specific dates
    val appointmentTime: String, // e.g., "14:00"
    val status: String = "scheduled", // "scheduled", "cancelled"
    val createdAt: String
)
