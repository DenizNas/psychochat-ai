package com.psikochat.app.data.local.entity

import androidx.room.Entity
import androidx.room.Index
import androidx.room.PrimaryKey

@Entity(
    tableName = "score_snapshots",
    indices = [Index(value = ["date"], unique = true)]
)
data class ScoreSnapshot(
    @PrimaryKey(autoGenerate = true) val id: Int = 0,
    val date: String, // YYYY-MM-DD
    val score: Int, // wellnessScore.score between 0 and 100
    val createdAt: Long
)
