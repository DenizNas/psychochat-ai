package com.psikochat.app.data.sync

import android.content.Context
import android.util.Log
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import com.psikochat.app.data.api.PsikoApi
import com.psikochat.app.data.api.RetrofitClient
import com.psikochat.app.data.local.AppDatabase
import com.psikochat.app.data.local.TokenManager
import com.psikochat.app.data.local.entity.CachedChatMessage
import com.psikochat.app.data.local.entity.CachedMoodJournal
import com.psikochat.app.data.local.entity.SyncEventEntity
import com.psikochat.app.data.model.ChatRequest
import com.psikochat.app.data.model.CreateMoodJournalRequest
import kotlinx.coroutines.flow.first
import retrofit2.HttpException
import java.io.IOException
import java.text.SimpleDateFormat
import java.util.*

class OfflineSyncWorker(
    context: Context,
    workerParams: WorkerParameters
) : CoroutineWorker(context, workerParams) {

    private val db = AppDatabase.getInstance(context)
    private val tokenManager = TokenManager(context)

    override suspend fun doWork(): Result {
        val token = tokenManager.getToken().first()
        val username = tokenManager.getUsername().first()
        
        if (token.isNullOrEmpty() || username.isNullOrEmpty()) {
            Log.d("OfflineSyncWorker", "SYNC_JOB | skipped | user not authenticated")
            return Result.success()
        }

        val api = RetrofitClient.create(tokenManager)
        val isoTimestamp = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss", Locale.getDefault()).format(Date())

        db.syncEventDao().insertSyncEvent(
            SyncEventEntity(eventType = "sync_all", status = "queued", timestamp = isoTimestamp)
        )

        Log.d("OfflineSyncWorker", "SYNC_JOB | started | user: $username")

        var hasNetworkFailure = false

        // 1. Process Pending Chat Messages
        val pendingChats = db.chatDao().getPendingMessages(username)
        for (chat in pendingChats) {
            try {
                Log.d("OfflineSyncWorker", "SYNC_JOB | chat pending | localId: ${chat.localId}")
                val response = api.sendMessage(
                    ChatRequest(text = chat.text, language = chat.language, conversationId = chat.conversationId),
                    chat.idempotencyKey
                )
                
                // Success: remove pending, update original user cached message state to synced, and save assistant response in cache
                db.chatDao().deletePendingMessage(chat.localId)
                db.chatDao().updateCachedMessageStateByLocalId(chat.localId, "synced")
                db.chatDao().insertCachedMessage(
                    CachedChatMessage(
                        userId = username,
                        role = "assistant",
                        text = response.response,
                        timestamp = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss", Locale.getDefault()).format(Date()),
                        state = "synced",
                        conversationId = chat.conversationId
                    )
                )
                
                db.syncEventDao().insertSyncEvent(
                    SyncEventEntity(
                        eventType = "chat",
                        status = "success",
                        message = "Chat message synced. localId: ${chat.localId}",
                        timestamp = isoTimestamp
                    )
                )
                Log.d("OfflineSyncWorker", "SYNC_JOB | chat success | localId: ${chat.localId}")
            } catch (e: IOException) {
                // Connection/Socket timeout: retry worker later
                hasNetworkFailure = true
                db.chatDao().updatePendingMessageState(chat.localId, "pending", e.message)
                Log.e("OfflineSyncWorker", "SYNC_JOB | chat failed network | localId: ${chat.localId}", e)
            } catch (e: HttpException) {
                // API validation or server error (e.g. 400 Bad Request): mark as failed so it won't block queue
                db.chatDao().updatePendingMessageState(chat.localId, "failed", e.message())
                db.syncEventDao().insertSyncEvent(
                    SyncEventEntity(
                        eventType = "chat",
                        status = "failed",
                        message = "Http error: ${e.code()}. localId: ${chat.localId}",
                        timestamp = isoTimestamp
                    )
                )
                Log.e("OfflineSyncWorker", "SYNC_JOB | chat failed server | localId: ${chat.localId} | code: ${e.code()}")
            }
        }

        // 2. Process Pending Mood Journals
        val pendingMoodJournals = db.moodJournalDao().getPendingMoodJournals(username)
        for (mood in pendingMoodJournals) {
            try {
                Log.d("OfflineSyncWorker", "SYNC_JOB | mood pending | localId: ${mood.localId} | action: ${mood.action}")
                if (mood.action == "CREATE") {
                    val response = api.createMoodJournal(
                        CreateMoodJournalRequest(
                            mood = mood.mood!!,
                            intensity = mood.intensity!!,
                            note = mood.note
                        ),
                        mood.idempotencyKey
                    )
                    
                    // Add returned entry into cached journals, delete pending
                    db.moodJournalDao().insertCachedMoodJournal(
                        CachedMoodJournal(
                            id = response.id,
                            userId = username,
                            mood = response.mood,
                            intensity = response.intensity,
                            note = response.note,
                            createdAt = response.createdAt,
                            source = response.source
                        )
                    )
                    db.moodJournalDao().deletePendingMoodJournal(mood.localId)
                } else if (mood.action == "DELETE") {
                    api.deleteMoodJournal(mood.moodJournalId!!)
                    
                    // Delete from local cache and local pending delete queue
                    db.moodJournalDao().deleteCachedMoodJournal(mood.moodJournalId)
                    db.moodJournalDao().deletePendingMoodJournal(mood.localId)
                }

                db.syncEventDao().insertSyncEvent(
                    SyncEventEntity(
                        eventType = "mood_${mood.action.lowercase()}",
                        status = "success",
                        message = "Mood log synced. localId: ${mood.localId}",
                        timestamp = isoTimestamp
                    )
                )
                Log.d("OfflineSyncWorker", "SYNC_JOB | mood success | localId: ${mood.localId}")
            } catch (e: IOException) {
                hasNetworkFailure = true
                db.moodJournalDao().updatePendingMoodState(mood.localId, "pending", e.message)
                Log.e("OfflineSyncWorker", "SYNC_JOB | mood failed network | localId: ${mood.localId}", e)
            } catch (e: HttpException) {
                // If deletion returns 404 (already deleted), treat as success
                if (mood.action == "DELETE" && e.code() == 404) {
                    db.moodJournalDao().deleteCachedMoodJournal(mood.moodJournalId!!)
                    db.moodJournalDao().deletePendingMoodJournal(mood.localId)
                } else {
                    db.moodJournalDao().updatePendingMoodState(mood.localId, "failed", e.message())
                    db.syncEventDao().insertSyncEvent(
                        SyncEventEntity(
                            eventType = "mood_${mood.action.lowercase()}",
                            status = "failed",
                            message = "Http error: ${e.code()}. localId: ${mood.localId}",
                            timestamp = isoTimestamp
                        )
                    )
                }
                Log.e("OfflineSyncWorker", "SYNC_JOB | mood failed server | localId: ${mood.localId} | code: ${e.code()}")
            }
        }

        return if (hasNetworkFailure) {
            Log.d("OfflineSyncWorker", "SYNC_JOB | finished | retrying later due to connection failures")
            Result.retry()
        } else {
            Log.d("OfflineSyncWorker", "SYNC_JOB | completed | all queues flushed")
            Result.success()
        }
    }
}
