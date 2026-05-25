package com.psikochat.app.data.local

import android.content.Context
import androidx.room.Database
import androidx.room.Room
import androidx.room.RoomDatabase
import com.psikochat.app.data.local.dao.*
import com.psikochat.app.data.local.entity.*

@Database(
    entities = [
        CachedChatMessage::class,
        PendingChatMessage::class,
        CachedMoodJournal::class,
        PendingMoodJournal::class,
        CachedDashboard::class,
        CachedReport::class,
        SyncEventEntity::class
    ],
    version = 1,
    exportSchema = false
)
abstract class AppDatabase : RoomDatabase() {

    abstract fun chatDao(): ChatDao
    abstract fun moodJournalDao(): MoodJournalDao
    abstract fun dashboardDao(): DashboardDao
    abstract fun reportDao(): ReportDao
    abstract fun syncEventDao(): SyncEventDao

    companion object {
        @Volatile
        private var INSTANCE: AppDatabase? = null

        fun getInstance(context: Context): AppDatabase {
            return INSTANCE ?: synchronized(this) {
                val instance = Room.databaseBuilder(
                    context.applicationContext,
                    AppDatabase::class.java,
                    "psikochat_offline_db"
                )
                .fallbackToDestructiveMigration() // safe for local caching, prevents crashes during updates
                .build()
                INSTANCE = instance
                instance
            }
        }
    }
}
