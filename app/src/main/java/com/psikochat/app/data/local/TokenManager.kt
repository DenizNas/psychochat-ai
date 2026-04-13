package com.psikochat.app.data.local
import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map

val Context.dataStore: DataStore<Preferences> by preferencesDataStore(name = "settings")

class TokenManager(private val context: Context) {
    companion object {
        val TOKEN_KEY = stringPreferencesKey("jwt_token")
        val USERNAME_KEY = stringPreferencesKey("username")
    }
    
    fun getToken(): Flow<String?> = context.dataStore.data.map { it[TOKEN_KEY] }
    fun getUsername(): Flow<String?> = context.dataStore.data.map { it[USERNAME_KEY] ?: "Kullanıcı" }
    
    suspend fun saveAuthData(token: String, username: String) {
        context.dataStore.edit { preferences ->
            preferences[TOKEN_KEY] = token
            preferences[USERNAME_KEY] = username
        }
    }
    
    suspend fun clearAuthData() {
        context.dataStore.edit { preferences ->
            preferences.remove(TOKEN_KEY)
            preferences.remove(USERNAME_KEY)
        }
    }
    
    suspend fun saveToken(token: String) { context.dataStore.edit { it[TOKEN_KEY] = token } }
    suspend fun clearToken() { context.dataStore.edit { it.remove(TOKEN_KEY) } }
}
