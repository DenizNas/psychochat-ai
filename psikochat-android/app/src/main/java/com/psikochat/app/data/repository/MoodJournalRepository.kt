package com.psikochat.app.data.repository

import com.psikochat.app.data.api.PsikoApi
import com.psikochat.app.data.model.Resource
import com.psikochat.app.data.model.CreateMoodJournalRequest
import com.psikochat.app.data.model.MoodJournalEntry
import com.psikochat.app.data.local.dao.MoodJournalDao
import com.psikochat.app.data.local.entity.CachedMoodJournal
import com.psikochat.app.data.local.entity.PendingMoodJournal
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map
import retrofit2.HttpException
import java.io.IOException
import java.text.SimpleDateFormat
import java.util.*
import org.json.JSONObject

class MoodJournalRepository(
    private val api: PsikoApi,
    private val moodJournalDao: MoodJournalDao
) {

    /**
     * Exposes a reactive flow of cached mood journals mapped to API model objects.
     */
    fun getCachedMoodJournals(userId: String): Flow<List<MoodJournalEntry>> {
        return moodJournalDao.getCachedMoodJournals(userId).map { cachedList ->
            cachedList.map {
                MoodJournalEntry(
                    id = it.id,
                    userId = it.userId,
                    mood = it.mood,
                    intensity = it.intensity,
                    note = it.note,
                    createdAt = it.createdAt,
                    updatedAt = it.createdAt,
                    source = it.source
                )
            }
        }
    }

    /**
     * Refreshes the local cache with the latest mood journals from the server.
     */
    suspend fun refreshMoodJournals(userId: String, days: Int): Resource<List<MoodJournalEntry>> {
        return try {
            val response = api.getMoodJournals(days)
            moodJournalDao.clearCachedMoodJournals(userId)
            val dbEntities = response.map {
                CachedMoodJournal(
                    id = it.id,
                    userId = userId,
                    mood = it.mood,
                    intensity = it.intensity,
                    note = it.note,
                    createdAt = it.createdAt,
                    source = it.source
                )
            }
            moodJournalDao.insertCachedMoodJournals(dbEntities)
            Resource.Success(response)
        } catch (e: Exception) {
            parseError(e, "Mood geçmişi yüklenemedi")
        }
    }

    /**
     * Resilient mood journal creation.
     * Inserts locally immediately. Flushes to backend if online, otherwise queues pending.
     */
    suspend fun createMoodJournalResilient(
        userId: String,
        mood: String,
        intensity: Int,
        note: String?,
        isOnline: Boolean
    ): Resource<MoodJournalEntry> {
        val localId = UUID.randomUUID().toString()
        val idempotencyKey = UUID.randomUUID().toString()
        val timestamp = SimpleDateFormat("yyyy-MM-dd HH:mm:ss", Locale.getDefault()).format(Date())
        // Optimistic ID (negative hashcode to easily distinguish from server IDs)
        val tempServerId = -Math.abs(localId.hashCode())

        // 1. Optimistic insertion in cache
        val localCachedEntry = CachedMoodJournal(
            id = tempServerId,
            userId = userId,
            mood = mood,
            intensity = intensity,
            note = note,
            createdAt = timestamp,
            source = "offline"
        )
        moodJournalDao.insertCachedMoodJournal(localCachedEntry)

        if (isOnline) {
            return try {
                val request = CreateMoodJournalRequest(mood, intensity, note)
                val response = api.createMoodJournal(request, idempotencyKey)

                // Delete the optimistic negative cached entry and replace with synced entry
                moodJournalDao.deleteCachedMoodJournal(tempServerId)
                moodJournalDao.insertCachedMoodJournal(
                    CachedMoodJournal(
                        id = response.id,
                        userId = userId,
                        mood = response.mood,
                        intensity = response.intensity,
                        note = response.note,
                        createdAt = response.createdAt,
                        source = response.source
                    )
                )
                Resource.Success(response)
            } catch (e: Exception) {
                if (e is IOException) {
                    // Queue for background sync
                    val pending = PendingMoodJournal(
                        localId = localId,
                        userId = userId,
                        action = "CREATE",
                        mood = mood,
                        intensity = intensity,
                        note = note,
                        timestamp = timestamp,
                        idempotencyKey = idempotencyKey
                    )
                    moodJournalDao.insertPendingMoodJournal(pending)
                    Resource.Error("Sunucuya bağlanılamadı. Günlük çevrimdışı kaydedildi.")
                } else {
                    // Fatal validation failure: remove from optimistic cache
                    moodJournalDao.deleteCachedMoodJournal(tempServerId)
                    parseError(e, "Mood günlüğü kaydedilemedi")
                }
            }
        } else {
            // Queue immediately
            val pending = PendingMoodJournal(
                localId = localId,
                userId = userId,
                action = "CREATE",
                mood = mood,
                intensity = intensity,
                note = note,
                timestamp = timestamp,
                idempotencyKey = idempotencyKey
            )
            moodJournalDao.insertPendingMoodJournal(pending)
            return Resource.Error("Çevrimdışı kaydedildi. Bağlantı geldiğinde otomatik gönderilecektir.")
        }
    }

    /**
     * Resilient mood journal deletion.
     * Wipes from cache immediately.
     * Cancels pending creations before network attempts to prevent redundant flushes.
     */
    suspend fun deleteMoodJournalResilient(
        userId: String,
        journalId: Int,
        isOnline: Boolean
    ): Resource<String> {
        // 1. Check if it's an unsynced local pending log
        if (journalId < 0) {
            val pendingLogs = moodJournalDao.getPendingMoodJournals(userId)
            val matchingPending = pendingLogs.firstOrNull { -Math.abs(it.localId.hashCode()) == journalId }
            if (matchingPending != null) {
                // Remove optimistic cache and the pending queue entry immediately (cancellation)
                moodJournalDao.deleteCachedMoodJournal(journalId)
                moodJournalDao.deletePendingMoodJournal(matchingPending.localId)
                return Resource.Success("Kayıt başarıyla silindi (çevrimdışı iptal edildi)")
            }
        }

        // 2. Otherwise it's a real server journal entry
        moodJournalDao.deleteCachedMoodJournal(journalId)

        if (isOnline) {
            return try {
                val response = api.deleteMoodJournal(journalId)
                Resource.Success(response["detail"] ?: "Kayıt başarıyla silindi")
            } catch (e: Exception) {
                if (e is IOException) {
                    val pending = PendingMoodJournal(
                        localId = UUID.randomUUID().toString(),
                        userId = userId,
                        action = "DELETE",
                        moodJournalId = journalId,
                        timestamp = SimpleDateFormat("yyyy-MM-dd HH:mm:ss", Locale.getDefault()).format(Date()),
                        idempotencyKey = UUID.randomUUID().toString()
                    )
                    moodJournalDao.insertPendingMoodJournal(pending)
                    Resource.Success("Çevrimdışı silindi. Bağlantı kurulduğunda sunucudan kaldırılacaktır.")
                } else {
                    parseError(e, "Kayıt silinemedi")
                }
            }
        } else {
            val pending = PendingMoodJournal(
                localId = UUID.randomUUID().toString(),
                userId = userId,
                action = "DELETE",
                moodJournalId = journalId,
                timestamp = SimpleDateFormat("yyyy-MM-dd HH:mm:ss", Locale.getDefault()).format(Date()),
                idempotencyKey = UUID.randomUUID().toString()
            )
            moodJournalDao.insertPendingMoodJournal(pending)
            return Resource.Success("Çevrimdışı silindi. Bağlantı kurulduğunda sunucudan kaldırılacaktır.")
        }
    }

    private fun <T> parseError(e: Exception, defaultMessage: String): Resource<T> {
        return when (e) {
            is HttpException -> {
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
            is IOException -> Resource.Error("Sunucuya bağlanılamadı. İnternet bağlantınızı kontrol edin.")
            else -> Resource.Error(e.message ?: defaultMessage)
        }
    }
}
