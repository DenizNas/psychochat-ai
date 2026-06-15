package com.psikochat.app.data.repository

import com.psikochat.app.data.api.PsikoApi
import com.psikochat.app.data.model.*

class PsychologistAvailabilityRepository(private val api: PsikoApi) {

    suspend fun getMyAvailability(): Resource<List<AvailabilityDto>> {
        return try {
            val list = api.getMyAvailability()
            Resource.Success(list)
        } catch (e: Exception) {
            Resource.Error(e.message ?: "Müsaitlik saatleri yüklenemedi.")
        }
    }

    suspend fun createAvailability(dayOfWeek: Int, startTime: String, endTime: String, duration: Int): Resource<AvailabilityDto> {
        return try {
            val req = CreateAvailabilityRequest(dayOfWeek, startTime, endTime, duration)
            val av = api.createAvailability(req)
            Resource.Success(av)
        } catch (e: Exception) {
            Resource.Error(e.message ?: "Müsaitlik kaydı oluşturulamadı.")
        }
    }

    suspend fun updateAvailability(id: Int, dayOfWeek: Int?, startTime: String?, endTime: String?, duration: Int?, isActive: Boolean?): Resource<AvailabilityDto> {
        return try {
            val req = UpdateAvailabilityRequest(dayOfWeek, startTime, endTime, duration, isActive)
            val av = api.updateAvailability(id, req)
            Resource.Success(av)
        } catch (e: Exception) {
            Resource.Error(e.message ?: "Müsaitlik kaydı güncellenemedi.")
        }
    }

    suspend fun deleteAvailability(id: Int): Resource<Boolean> {
        return try {
            api.deleteAvailability(id)
            Resource.Success(true)
        } catch (e: Exception) {
            Resource.Error(e.message ?: "Müsaitlik kaydı silinemedi.")
        }
    }

    suspend fun getAvailableSlots(psychologistId: Int, date: String): Resource<AvailableSlotsResponse> {
        return try {
            val response = api.getAvailableSlots(psychologistId, date)
            Resource.Success(response)
        } catch (e: Exception) {
            Resource.Error(e.message ?: "Müsait saatler yüklenemedi.")
        }
    }
}
