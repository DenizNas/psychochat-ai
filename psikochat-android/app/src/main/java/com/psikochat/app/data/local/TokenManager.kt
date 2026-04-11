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
    companion object { val TOKEN_KEY = stringPreferencesKey("jwt_token") }
    fun getToken(): Flow<String?> = context.dataStore.data.map { it[TOKEN_KEY] }
    suspend fun saveToken(token: String) { context.dataStore.edit { it[TOKEN_KEY] = token } }
    suspend fun clearToken() { context.dataStore.edit { it.remove(TOKEN_KEY) } }
}
