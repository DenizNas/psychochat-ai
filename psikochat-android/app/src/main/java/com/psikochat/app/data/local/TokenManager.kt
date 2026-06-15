package com.psikochat.app.data.local
import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.core.booleanPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map

val Context.dataStore: DataStore<Preferences> by preferencesDataStore(name = "settings")

class TokenManager(private val context: Context) {
    companion object {
        val TOKEN_KEY = stringPreferencesKey("jwt_token")
        val USERNAME_KEY = stringPreferencesKey("username")
        val EMAIL_KEY = stringPreferencesKey("email")
        val FULL_NAME_KEY = stringPreferencesKey("full_name")
        val ROLE_KEY = stringPreferencesKey("role")
        val ONBOARDING_COMPLETED_KEY = booleanPreferencesKey("onboarding_completed")
        val THEME_KEY = stringPreferencesKey("theme_preference")
        val APPOINTMENTS_REMINDER_KEY = booleanPreferencesKey("notifications_appointments_reminder")
        val DAILY_CHECKIN_KEY = booleanPreferencesKey("notifications_daily_checkin")
        val DAILY_CHECKIN_TIME_KEY = stringPreferencesKey("notifications_daily_checkin_time")
        val WEEKLY_RECAP_KEY = booleanPreferencesKey("notifications_weekly_recap")
        val WEEKLY_RECAP_DAY_KEY = stringPreferencesKey("notifications_weekly_recap_day")
        val WEEKLY_RECAP_TIME_KEY = stringPreferencesKey("notifications_weekly_recap_time")
        val PROFILE_PHOTO_URL_KEY = stringPreferencesKey("profile_photo_url")
    }
    
    fun getToken(): Flow<String?> = context.dataStore.data.map { it[TOKEN_KEY] }
    fun getProfilePhotoUrl(): Flow<String?> = context.dataStore.data.map { it[PROFILE_PHOTO_URL_KEY] }
    
    suspend fun saveProfilePhotoUrl(url: String) {
        context.dataStore.edit { preferences ->
            preferences[PROFILE_PHOTO_URL_KEY] = url
        }
    }
    fun getUsername(): Flow<String> =
    context.dataStore.data.map { it[USERNAME_KEY] ?: "Kullanıcı" }
    
    fun getEmail(): Flow<String?> = context.dataStore.data.map { it[EMAIL_KEY] }
    fun getFullName(): Flow<String?> = context.dataStore.data.map { it[FULL_NAME_KEY] }
    fun getRole(): Flow<String?> = context.dataStore.data.map { it[ROLE_KEY] }
    
    suspend fun saveRole(role: String) {
        context.dataStore.edit { preferences ->
            preferences[ROLE_KEY] = role
        }
    }
    
    fun isOnboardingCompleted(): Flow<Boolean> = context.dataStore.data.map { it[ONBOARDING_COMPLETED_KEY] ?: true }
    
    suspend fun setOnboardingCompleted(completed: Boolean) {
        context.dataStore.edit { preferences ->
            preferences[ONBOARDING_COMPLETED_KEY] = completed
        }
    }
    
    fun getThemePreference(): Flow<String> = context.dataStore.data.map { it[THEME_KEY] ?: "system" }
    
    suspend fun saveThemePreference(theme: String) {
        context.dataStore.edit { preferences ->
            preferences[THEME_KEY] = theme
        }
    }

    fun getAppointmentsReminderEnabled(): Flow<Boolean> = context.dataStore.data.map { it[APPOINTMENTS_REMINDER_KEY] ?: true }
    suspend fun saveAppointmentsReminderEnabled(enabled: Boolean) {
        context.dataStore.edit { preferences ->
            preferences[APPOINTMENTS_REMINDER_KEY] = enabled
        }
    }

    fun getDailyCheckInEnabled(): Flow<Boolean> = context.dataStore.data.map { it[DAILY_CHECKIN_KEY] ?: true }
    suspend fun saveDailyCheckInEnabled(enabled: Boolean) {
        context.dataStore.edit { preferences ->
            preferences[DAILY_CHECKIN_KEY] = enabled
        }
    }

    fun getDailyCheckInTime(): Flow<String> = context.dataStore.data.map { it[DAILY_CHECKIN_TIME_KEY] ?: "20:00" }
    suspend fun saveDailyCheckInTime(time: String) {
        context.dataStore.edit { preferences ->
            preferences[DAILY_CHECKIN_TIME_KEY] = time
        }
    }

    fun getWeeklyRecapEnabled(): Flow<Boolean> = context.dataStore.data.map { it[WEEKLY_RECAP_KEY] ?: true }
    suspend fun saveWeeklyRecapEnabled(enabled: Boolean) {
        context.dataStore.edit { preferences ->
            preferences[WEEKLY_RECAP_KEY] = enabled
        }
    }

    fun getWeeklyRecapDay(): Flow<String> = context.dataStore.data.map { it[WEEKLY_RECAP_DAY_KEY] ?: "SUNDAY" }
    suspend fun saveWeeklyRecapDay(day: String) {
        context.dataStore.edit { preferences ->
            preferences[WEEKLY_RECAP_DAY_KEY] = day
        }
    }

    fun getWeeklyRecapTime(): Flow<String> = context.dataStore.data.map { it[WEEKLY_RECAP_TIME_KEY] ?: "19:00" }
    suspend fun saveWeeklyRecapTime(time: String) {
        context.dataStore.edit { preferences ->
            preferences[WEEKLY_RECAP_TIME_KEY] = time
        }
    }
    
    suspend fun saveAuthData(token: String, username: String, email: String? = null, fullName: String? = null, role: String? = "user") {
        context.dataStore.edit { preferences ->
            preferences[TOKEN_KEY] = token
            preferences[USERNAME_KEY] = username
            if (email != null) preferences[EMAIL_KEY] = email
            if (fullName != null) preferences[FULL_NAME_KEY] = fullName
            if (role != null) preferences[ROLE_KEY] = role
        }
    }
    
    suspend fun clearAuthData() {
        context.dataStore.edit { preferences ->
            preferences.remove(TOKEN_KEY)
            preferences.remove(USERNAME_KEY)
            preferences.remove(EMAIL_KEY)
            preferences.remove(FULL_NAME_KEY)
            preferences.remove(ROLE_KEY)
            preferences.remove(ONBOARDING_COMPLETED_KEY)
            preferences.remove(THEME_KEY)
            preferences.remove(APPOINTMENTS_REMINDER_KEY)
            preferences.remove(DAILY_CHECKIN_KEY)
            preferences.remove(DAILY_CHECKIN_TIME_KEY)
            preferences.remove(WEEKLY_RECAP_KEY)
            preferences.remove(WEEKLY_RECAP_DAY_KEY)
            preferences.remove(WEEKLY_RECAP_TIME_KEY)
            preferences.remove(PROFILE_PHOTO_URL_KEY)
        }
        try {
            AppDatabase.getInstance(context).clearAllTables()
        } catch (e: Exception) {
            // Shield exceptions
        }
    }
    
    
}
