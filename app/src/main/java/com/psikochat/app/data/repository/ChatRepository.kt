package com.psikochat.app.data.repository

import com.psikochat.app.data.api.PsikoApi
import com.psikochat.app.data.model.ChatRequest
import com.psikochat.app.data.model.ChatResponse
import com.psikochat.app.data.model.HistoryItem
import com.psikochat.app.data.model.Resource
import com.psikochat.app.data.local.dao.ChatDao
import com.psikochat.app.data.local.entity.CachedChatMessage
import com.psikochat.app.data.local.entity.PendingChatMessage
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map
import retrofit2.HttpException
import java.io.IOException
import java.net.SocketTimeoutException
import java.text.SimpleDateFormat
import java.util.*
import org.json.JSONObject

class ChatRepository(
    private val api: PsikoApi,
    private val chatDao: ChatDao
) {

    /**
     * Exposes a reactive flow of cached messages mapped to UI HistoryItems.
     */
    fun getCachedHistory(userId: String): Flow<List<HistoryItem>> {
        return chatDao.getCachedMessages(userId).map { cachedList ->
            cachedList.map {
                HistoryItem(
                    id = it.id,
                    role = it.role,
                    text = it.text,
                    timestamp = it.timestamp,
                    state = it.state
                )
            }
        }
    }

    /**
     * Refreshes the local cache with the latest messages from the server.
     */
    suspend fun refreshHistory(userId: String): Resource<List<HistoryItem>> {
        return try {
            val res = api.getHistory()
            // Clear local cache for this user and replace with fresh data
            chatDao.clearCachedMessages(userId)
            val dbEntities = res.map {
                CachedChatMessage(
                    userId = userId,
                    role = it.role,
                    text = it.text,
                    timestamp = it.timestamp ?: "",
                    state = "synced"
                )
            }
            chatDao.insertCachedMessages(dbEntities)
            Resource.Success(res)
        } catch (e: Exception) {
            parseError(e, "Sohbet geçmişi yenilenemedi")
        }
    }

    /**
     * Resilient message sending gateway.
     * If online, attempts a direct REST post.
     * If offline or post fails due to connection, registers a local pending event for worker sync.
     */
    suspend fun sendMessageResilient(
        userId: String,
        text: String,
        language: String = "tr",
        isOnline: Boolean
    ): Resource<ChatResponse> {
        val localId = UUID.randomUUID().toString()
        val idempotencyKey = UUID.randomUUID().toString()
        val timestamp = SimpleDateFormat("yyyy-MM-dd HH:mm:ss", Locale.getDefault()).format(Date())

        // 1. Save locally as pending first (Optimistic insertion)
        val userCachedMsg = CachedChatMessage(
            userId = userId,
            role = "user",
            text = text,
            timestamp = timestamp,
            localId = localId,
            state = "pending"
        )
        chatDao.insertCachedMessage(userCachedMsg)

        if (isOnline) {
            return try {
                val res = api.sendMessage(
                    ChatRequest(text = text, language = language),
                    idempotencyKey
                )
                
                // Update local cached user message state to synced
                val syncedUserMsg = userCachedMsg.copy(state = "synced")
                chatDao.insertCachedMessage(syncedUserMsg)

                // Insert assistant response directly into cache
                chatDao.insertCachedMessage(
                    CachedChatMessage(
                        userId = userId,
                        role = "assistant",
                        text = res.response,
                        timestamp = SimpleDateFormat("yyyy-MM-dd HH:mm:ss", Locale.getDefault()).format(Date()),
                        state = "synced"
                    )
                )
                Resource.Success(res)
            } catch (e: Exception) {
                // Connection or gateway failure: enqueue message for background sync
                if (e is IOException || e is SocketTimeoutException) {
                    val pendingMsg = PendingChatMessage(
                        localId = localId,
                        userId = userId,
                        text = text,
                        language = language,
                        timestamp = timestamp,
                        state = "pending",
                        idempotencyKey = idempotencyKey
                    )
                    chatDao.insertPendingMessage(pendingMsg)
                    
                    // Mark cache as queued offline
                    chatDao.insertCachedMessage(userCachedMsg.copy(state = "pending"))
                    Resource.Error("Sunucuya bağlanılamadı. Çevrimdışı kuyruğa eklendi.")
                } else {
                    // Critical validation failure (e.g. 400 Bad Request): mark as failed
                    chatDao.insertCachedMessage(userCachedMsg.copy(state = "failed"))
                    parseError(e, "Mesaj gönderilemedi")
                }
            }
        } else {
            // Force offline queuing immediately
            val pendingMsg = PendingChatMessage(
                localId = localId,
                userId = userId,
                text = text,
                language = language,
                timestamp = timestamp,
                state = "pending",
                idempotencyKey = idempotencyKey
            )
            chatDao.insertPendingMessage(pendingMsg)
            return Resource.Error("Çevrimdışı kaydedildi. İnternet geldiğinde otomatik gönderilecektir.")
        }
    }

    private fun <T> parseError(e: Exception, defaultMessage: String): Resource<T> {
        return when (e) {
            is HttpException -> {
                if (e.code() == 401 || e.code() == 403) {
                    return Resource.Error("Oturumunuzun süresi doldu. Lütfen tekrar giriş yapın.")
                }
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
            is SocketTimeoutException -> Resource.Error("Yanıt alınamadı, lütfen tekrar deneyin")
            is IOException -> Resource.Error("Sunucuya bağlanılamadı. İnternet bağlantınızı kontrol edin.")
            else -> Resource.Error(e.message ?: defaultMessage)
        }
    }
}
