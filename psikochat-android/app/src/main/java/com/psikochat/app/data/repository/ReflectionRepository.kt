package com.psikochat.app.data.repository

import com.psikochat.app.data.api.PsikoApi
import com.psikochat.app.data.model.WellnessReportResponse
import com.psikochat.app.data.model.ReflectionResponse
import com.psikochat.app.data.model.Resource

class ReflectionRepository(private val api: PsikoApi) {

    suspend fun getWellnessReport(period: String, days: Int = 7): Resource<WellnessReportResponse> {
        return try {
            val response = api.getWellnessReport(period, days)
            Resource.Success(response)
        } catch (e: Exception) {
            Resource.Error(e.message ?: "Zihinsel wellness raporu yüklenemedi.")
        }
    }

    suspend fun getReflections(period: String): Resource<ReflectionResponse> {
        return try {
            val response = api.getReflections(period)
            Resource.Success(response)
        } catch (e: Exception) {
            Resource.Error(e.message ?: "Zihinsel refleksiyon özeti yüklenemedi.")
        }
    }
}
