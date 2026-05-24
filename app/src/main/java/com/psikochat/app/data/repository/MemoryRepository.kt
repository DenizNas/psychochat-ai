package com.psikochat.app.data.repository

import com.psikochat.app.data.api.PsikoApi
import com.psikochat.app.data.model.UserMemory
import com.psikochat.app.data.model.MemoryConsolidationResponse
import com.psikochat.app.data.model.Resource
import retrofit2.HttpException
import java.io.IOException
import org.json.JSONObject

class MemoryRepository(private val api: PsikoApi) {

    suspend fun getMemories(): Resource<List<UserMemory>> {
        return try {
            val response = api.getMemories()
            Resource.Success(response)
        } catch (e: Exception) {
            parseError(e, "Hatırlanan bilgiler listesi alınamadı.")
        }
    }

    suspend fun deleteMemory(memoryId: Int): Resource<Unit> {
        return try {
            api.deleteMemory(memoryId)
            Resource.Success(Unit)
        } catch (e: Exception) {
            parseError(e, "Hafıza kaydı silinemedi.")
        }
    }

    suspend fun refreshMemories(): Resource<MemoryConsolidationResponse> {
        return try {
            val response = api.refreshMemories()
            Resource.Success(response)
        } catch (e: Exception) {
            parseError(e, "Bellek konsolidasyonu çalıştırılamadı.")
        }
    }

    private fun <T> parseError(e: Exception, defaultMessage: String): Resource<T> {
        return when (e) {
            is HttpException -> {
                val errorBody = e.response()?.errorBody()?.string()
                val parsedMessage = try {
                    if (!errorBody.isNullOrBlank()) {
                        val json = JSONObject(errorBody)
                        if (json.has("detail")) json.getString("detail") else defaultMessage
                    } else defaultMessage
                } catch (ex: Exception) {
                    defaultMessage
                }
                Resource.Error(parsedMessage)
            }
            is IOException -> Resource.Error("Sunucuya bağlanılamadı. İnternet bağlantınızı kontrol edin.")
            else -> Resource.Error(e.message ?: defaultMessage)
        }
    }
}
