package com.psikochat.app.data.local.dao

import androidx.room.*
import com.psikochat.app.data.local.entity.*
import kotlinx.coroutines.flow.Flow

@Dao
interface ChatDao {
    @Query("SELECT * FROM cached_chat_messages WHERE userId = :userId ORDER BY id ASC")
    fun getCachedMessages(userId: String): Flow<List<CachedChatMessage>>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertCachedMessage(msg: CachedChatMessage): Long

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertCachedMessages(msgs: List<CachedChatMessage>)

    @Update
    suspend fun updateCachedMessage(message: CachedChatMessage)

    @Query("UPDATE cached_chat_messages SET state = :state WHERE localId = :localId")
    suspend fun updateCachedMessageStateByLocalId(localId: String, state: String)

    @Query("DELETE FROM cached_chat_messages WHERE userId = :userId")
    suspend fun clearCachedMessages(userId: String)

    /**
     * Deletes only rows with state != 'pending'.
     * Used by refreshHistory to preserve offline-queued user messages
     * while replacing server-synced rows with fresh data.
     */
    @Query("DELETE FROM cached_chat_messages WHERE userId = :userId AND state != 'pending'")
    suspend fun clearNonPendingMessages(userId: String)

    @Query("SELECT * FROM pending_chat_messages WHERE userId = :userId ORDER BY timestamp ASC")
    suspend fun getPendingMessages(userId: String): List<PendingChatMessage>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertPendingMessage(msg: PendingChatMessage)

    @Query("UPDATE pending_chat_messages SET state = :state, errorMessage = :errorMessage WHERE localId = :localId")
    suspend fun updatePendingMessageState(localId: String, state: String, errorMessage: String?)

    @Query("DELETE FROM pending_chat_messages WHERE localId = :localId")
    suspend fun deletePendingMessage(localId: String)

    @Query("DELETE FROM pending_chat_messages WHERE userId = :userId")
    suspend fun deletePendingMessages(userId: String)
}

@Dao
interface MoodJournalDao {
    @Query("SELECT * FROM cached_mood_journals WHERE userId = :userId ORDER BY createdAt DESC")
    fun getCachedMoodJournals(userId: String): Flow<List<CachedMoodJournal>>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertCachedMoodJournals(journals: List<CachedMoodJournal>)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertCachedMoodJournal(journal: CachedMoodJournal)

    @Query("DELETE FROM cached_mood_journals WHERE id = :id")
    suspend fun deleteCachedMoodJournal(id: Int)

    @Query("DELETE FROM cached_mood_journals WHERE userId = :userId")
    suspend fun clearCachedMoodJournals(userId: String)

    @Query("SELECT * FROM pending_mood_journals WHERE userId = :userId ORDER BY timestamp ASC")
    suspend fun getPendingMoodJournals(userId: String): List<PendingMoodJournal>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertPendingMoodJournal(pending: PendingMoodJournal)

    @Query("DELETE FROM pending_mood_journals WHERE localId = :localId")
    suspend fun deletePendingMoodJournal(localId: String)

    @Query("DELETE FROM pending_mood_journals WHERE userId = :userId")
    suspend fun deletePendingMoodJournals(userId: String)

    @Query("UPDATE pending_mood_journals SET state = :state, errorMessage = :errorMessage WHERE localId = :localId")
    suspend fun updatePendingMoodState(localId: String, state: String, errorMessage: String?)
}

@Dao
interface DashboardDao {
    @Query("SELECT * FROM cached_dashboard WHERE userId = :userId LIMIT 1")
    suspend fun getCachedDashboard(userId: String): CachedDashboard?

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertCachedDashboard(dashboard: CachedDashboard)

    @Query("DELETE FROM cached_dashboard WHERE userId = :userId")
    suspend fun clearCachedDashboard(userId: String)
}

@Dao
interface ReportDao {
    @Query("SELECT * FROM cached_reports WHERE userId = :userId AND period = :period AND days = :days LIMIT 1")
    suspend fun getCachedReport(userId: String, period: String, days: Int): CachedReport?

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertCachedReport(report: CachedReport)

    @Query("DELETE FROM cached_reports WHERE userId = :userId")
    suspend fun clearCachedReports(userId: String)
}

@Dao
interface SyncEventDao {
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertSyncEvent(event: SyncEventEntity)

    @Query("SELECT * FROM sync_events ORDER BY timestamp DESC")
    suspend fun getAllSyncEvents(): List<SyncEventEntity>

    @Query("DELETE FROM sync_events")
    suspend fun clearSyncEvents()
}
