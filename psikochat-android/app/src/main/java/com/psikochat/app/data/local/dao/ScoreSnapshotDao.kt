package com.psikochat.app.data.local.dao

import androidx.room.*
import com.psikochat.app.data.local.entity.ScoreSnapshot
import kotlinx.coroutines.flow.Flow

@Dao
interface ScoreSnapshotDao {

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertSnapshot(snapshot: ScoreSnapshot): Long

    @Query("SELECT * FROM score_snapshots ORDER BY date DESC LIMIT 1")
    suspend fun getLatestSnapshot(): ScoreSnapshot?

    @Query("SELECT * FROM score_snapshots ORDER BY date ASC")
    fun getAllSnapshots(): Flow<List<ScoreSnapshot>>

    @Query("SELECT * FROM score_snapshots ORDER BY date DESC LIMIT 7")
    fun getLast7Days(): Flow<List<ScoreSnapshot>>

    @Query("SELECT * FROM score_snapshots ORDER BY date DESC LIMIT 30")
    fun getLast30Days(): Flow<List<ScoreSnapshot>>

    @Query("SELECT EXISTS(SELECT 1 FROM score_snapshots WHERE date = :date LIMIT 1)")
    suspend fun existsForDate(date: String): Boolean
}
