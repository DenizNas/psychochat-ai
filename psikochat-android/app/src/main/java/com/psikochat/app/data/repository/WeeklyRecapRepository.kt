package com.psikochat.app.data.repository

import com.psikochat.app.data.api.PsikoApi
import com.psikochat.app.data.model.Resource
import com.psikochat.app.data.model.WeeklySummaryResponse
import retrofit2.HttpException
import java.io.IOException

class WeeklyRecapRepository(private val api: PsikoApi) {
    suspend fun getWeeklySummary(): Resource<WeeklySummaryResponse> {
        return try {
            val response = api.getWeeklySummary()
            Resource.Success(response)
        } catch (e: HttpException) {
            Resource.Error(e.message ?: "Haftalık özet alınamadı.")
        } catch (e: IOException) {
            Resource.Error("Sunucuya bağlanılamadı. İnternet bağlantınızı kontrol edin.")
        } catch (e: Exception) {
            Resource.Error(e.message ?: "Haftalık özet alınamadı.")
        }
    }
}
