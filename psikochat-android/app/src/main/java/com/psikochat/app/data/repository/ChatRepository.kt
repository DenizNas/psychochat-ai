package com.psikochat.app.data.repository

import android.util.Log
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
     * Exposes a reactive flow of cached messages filtered by conversationId mapped to UI HistoryItems.
     */
    fun getCachedHistory(userId: String, conversationId: String): Flow<List<HistoryItem>> {
        return chatDao.getCachedMessages(userId, conversationId).map { cachedList ->
            cachedList.map {
                HistoryItem(
                    id = it.id,
                    role = it.role,
                    text = it.text,
                    timestamp = it.timestamp,
                    state = it.state,
                    conversationId = it.conversationId
                )
            }
        }
    }

    /**
     * Exposes all cached messages mapped to UI HistoryItems (for ChatHistoryScreen).
     */
    fun getAllCachedHistory(userId: String): Flow<List<HistoryItem>> {
        return chatDao.getAllCachedMessages(userId).map { cachedList ->
            cachedList.map {
                HistoryItem(
                    id = it.id,
                    role = it.role,
                    text = it.text,
                    timestamp = it.timestamp,
                    state = it.state,
                    conversationId = it.conversationId
                )
            }
        }
    }

    private fun extractDateString(timestamp: String?): String {
        if (timestamp == null) return "Bugün"
        val formats = listOf(
            "yyyy-MM-dd'T'HH:mm:ss.SSS'Z'",
            "yyyy-MM-dd'T'HH:mm:ss.SSS",
            "yyyy-MM-dd'T'HH:mm:ss",
            "yyyy-MM-dd HH:mm:ss",
            "yyyy-MM-dd"
        )
        for (format in formats) {
            try {
                val sdf = SimpleDateFormat(format, Locale.getDefault())
                if (format.endsWith("'Z'")) {
                    sdf.timeZone = TimeZone.getTimeZone("UTC")
                }
                val date = sdf.parse(timestamp)
                if (date != null) {
                    val formatter = SimpleDateFormat("dd MMMM yyyy", Locale("tr", "TR"))
                    val dateString = formatter.format(date)
                    val todayString = formatter.format(Date())
                    return if (dateString == todayString) "Bugün" else dateString
                }
            } catch (e: Exception) {
                // try next format
            }
        }
        return "Bilinmeyen Tarih"
    }

    /**
     * Refreshes the local cache with the latest messages from the server.
     * Preserves any rows with state="pending" so offline-queued messages
     * are not wiped while waiting for OfflineSyncWorker to replay them.
     */
    suspend fun refreshHistory(userId: String): Resource<List<HistoryItem>> {
        return try {
            val res = api.getHistory()
            val existingList = chatDao.getAllCachedMessagesDirect(userId)
            // Delete only synced/failed rows — preserve pending ones so offline bubbles stay visible
            chatDao.clearNonPendingMessages(userId)
            val dbEntities = res.map { historyItem ->
                val matched = existingList.find { existing ->
                    existing.role == historyItem.role &&
                    existing.text == historyItem.text &&
                    (existing.timestamp.take(10) == historyItem.timestamp?.take(10))
                }
                val conversationId = matched?.conversationId ?: extractDateString(historyItem.timestamp)
                CachedChatMessage(
                    userId = userId,
                    role = historyItem.role,
                    text = historyItem.text,
                    timestamp = historyItem.timestamp ?: "",
                    state = "synced",
                    conversationId = conversationId
                )
            }
            chatDao.insertCachedMessages(dbEntities)
            Log.d("ChatRepository", "REFRESH_HISTORY | inserted ${dbEntities.size} rows | pending preserved")
            Resource.Success(res)
        } catch (e: Exception) {
            parseError(e, "Sohbet geçmişi yenilenemedi")
        }
    }

    /**
     * Saves a user message to the local Room cache immediately.
     */
    suspend fun saveUserMessageLocally(userId: String, text: String, state: String = "synced", conversationId: String): String {
        val localId = UUID.randomUUID().toString()
        val timestamp = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss", Locale.getDefault()).format(Date())
        val userCachedMsg = CachedChatMessage(
            userId = userId,
            role = "user",
            text = text,
            timestamp = timestamp,
            localId = localId,
            state = state,
            conversationId = conversationId
        )
        val rowId = chatDao.insertCachedMessage(userCachedMsg)
        Log.d("ChatRepository", "SAVE_LOCAL | role=user | state=$state | localId=${localId.take(8)} | rowId=$rowId")
        return localId
    }

    /**
     * Saves an assistant message to the local Room cache immediately.
     */
    suspend fun saveAssistantMessageLocally(userId: String, text: String, conversationId: String) {
        val timestamp = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss", Locale.getDefault()).format(Date())
        val assistantCachedMsg = CachedChatMessage(
            userId = userId,
            role = "assistant",
            text = text,
            timestamp = timestamp,
            state = "synced",
            conversationId = conversationId
        )
        chatDao.insertCachedMessage(assistantCachedMsg)
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
        isOnline: Boolean,
        isFallback: Boolean = false,
        fallbackLocalId: String? = null,
        conversationId: String
    ): Resource<ChatResponse> {
        val localId = fallbackLocalId ?: UUID.randomUUID().toString()
        val idempotencyKey = UUID.randomUUID().toString()
        val timestamp = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss", Locale.getDefault()).format(Date())

        var localRowId = -1L
        val userCachedMsg = CachedChatMessage(
            userId = userId,
            role = "user",
            text = text,
            timestamp = timestamp,
            localId = localId,
            state = "pending",
            conversationId = conversationId
        )
        if (!isFallback) {
            // Save locally as pending first (Optimistic insertion)
            // Capture the auto-generated row id so all subsequent updates target the same row.
            localRowId = chatDao.insertCachedMessage(userCachedMsg)
            Log.d("ChatRepository", "RESILIENT | inserted optimistic row | localId=${localId.take(8)} | rowId=$localRowId")
        } else {
            Log.d("ChatRepository", "RESILIENT | isFallback=true | localId=${localId.take(8)} | skipping insert")
        }

        if (isOnline) {
            return try {
                val res = api.sendMessage(
                    ChatRequest(text = text, language = language, conversationId = conversationId),
                    idempotencyKey
                )
                
                // Update local cached user message state to synced
                if (isFallback) {
                    chatDao.updateCachedMessageStateByLocalId(localId, "synced")
                } else {
                    // Use @Update which matches on primary key — no duplicate row created
                    chatDao.updateCachedMessage(userCachedMsg.copy(id = localRowId.toInt(), state = "synced"))
                }

                // Insert assistant response directly into cache
                chatDao.insertCachedMessage(
                    CachedChatMessage(
                        userId = userId,
                        role = "assistant",
                        text = res.response,
                        timestamp = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss", Locale.getDefault()).format(Date()),
                        state = "synced",
                        conversationId = conversationId
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
                        idempotencyKey = idempotencyKey,
                        conversationId = conversationId
                    )
                    chatDao.insertPendingMessage(pendingMsg)
                    
                    // Mark cache as queued offline
                    if (isFallback) {
                        chatDao.updateCachedMessageStateByLocalId(localId, "pending")
                    } else {
                        // Row already exists with id=localRowId; update state only — no re-insert
                        chatDao.updateCachedMessage(userCachedMsg.copy(id = localRowId.toInt(), state = "pending"))
                    }
                    Resource.Error("Sunucuya bağlanılamadı. Çevrimdışı kuyruğa eklendi.")
                } else {
                    // Critical validation failure (e.g. 400 Bad Request): mark as failed
                    if (isFallback) {
                        chatDao.updateCachedMessageStateByLocalId(localId, "failed")
                    } else {
                        chatDao.updateCachedMessage(userCachedMsg.copy(id = localRowId.toInt(), state = "failed"))
                    }
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
                idempotencyKey = idempotencyKey,
                conversationId = conversationId
            )
            chatDao.insertPendingMessage(pendingMsg)
            if (isFallback) {
                chatDao.updateCachedMessageStateByLocalId(localId, "pending")
            } else {
                // Row was inserted as "pending" — update to confirm state is correct with real id
                chatDao.updateCachedMessage(userCachedMsg.copy(id = localRowId.toInt(), state = "pending"))
            }
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
                        when {
                            json.has("message") -> json.getString("message")
                            json.has("detail") -> json.getString("detail")
                            else -> defaultMessage
                        }
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
