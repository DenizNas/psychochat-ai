package com.psikochat.app.data.repository
import com.psikochat.app.data.api.PsikoApi
import com.psikochat.app.data.model.ChatRequest
import com.psikochat.app.data.model.ChatResponse
import com.psikochat.app.data.model.HistoryItem
import com.psikochat.app.data.model.Resource

class ChatRepository(private val api: PsikoApi) {
    suspend fun getHistory(): Resource<List<HistoryItem>> {
        return try {
            val res = api.getHistory()
            Resource.Success(res)
        } catch (e: Exception) {
            Resource.Error(e.message ?: "Geçmiş yüklenemedi")
        }
    }
    
    suspend fun sendMessage(text: String): Resource<ChatResponse> {
        return try {
            val res = api.sendMessage(ChatRequest(text))
            Resource.Success(res)
        } catch (e: Exception) {
            Resource.Error(e.message ?: "Mesaj gönderilemedi")
        }
    }
}
