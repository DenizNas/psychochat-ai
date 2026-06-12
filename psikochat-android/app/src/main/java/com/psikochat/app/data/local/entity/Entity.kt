package com.psikochat.app.data.local.entity

import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "cached_chat_messages")
data class CachedChatMessage(
    @PrimaryKey(autoGenerate = true) val id: Int = 0,
    val userId: String,
    val role: String, // "user" or "assistant"
    val text: String,
    val timestamp: String,
    val localId: String? = null, // unique local UUID to correlate with pending messages
    val state: String = "synced",
    val conversationId: String = ""
)

@Entity(tableName = "pending_chat_messages")
data class PendingChatMessage(
    @PrimaryKey val localId: String, // UUID
    val userId: String,
    val text: String,
    val language: String,
    val timestamp: String,
    val state: String = "pending", // "pending", "synced", "failed"
    val errorMessage: String? = null,
    val idempotencyKey: String,
    val conversationId: String = ""
)

@Entity(tableName = "cached_mood_journals")
data class CachedMoodJournal(
    @PrimaryKey val id: Int, // maps to the backend journal_id
    val userId: String,
    val mood: String,
    val intensity: Int,
    val note: String?,
    val createdAt: String,
    val source: String
)

@Entity(tableName = "pending_mood_journals")
data class PendingMoodJournal(
    @PrimaryKey val localId: String, // UUID
    val userId: String,
    val action: String, // "CREATE" or "DELETE"
    val moodJournalId: Int? = null, // required for DELETE
    val mood: String? = null, // required for CREATE
    val intensity: Int? = null, // required for CREATE
    val note: String? = null, // required for CREATE
    val timestamp: String,
    val state: String = "pending", // "pending", "synced", "failed"
    val errorMessage: String? = null,
    val idempotencyKey: String
)

@Entity(tableName = "cached_dashboard")
data class CachedDashboard(
    @PrimaryKey val userId: String,
    val dashboardJson: String,
    val lastUpdated: String
)

@Entity(tableName = "cached_reports")
data class CachedReport(
    @PrimaryKey(autoGenerate = true) val id: Int = 0,
    val userId: String,
    val period: String,
    val days: Int,
    val reportJson: String,
    val lastUpdated: String
)

@Entity(tableName = "sync_events")
data class SyncEventEntity(
    @PrimaryKey(autoGenerate = true) val id: Int = 0,
    val eventType: String, // "chat", "mood_create", "mood_delete", "consent"
    val status: String, // "queued", "success", "failed"
    val message: String? = null,
    val timestamp: String
)
