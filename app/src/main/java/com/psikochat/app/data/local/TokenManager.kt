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

/**
 * TokenManager: JWT token ve kullanıcı adını DataStore üzerinde kalıcı olarak saklar.
 *
 * Session Persistence Kuralları:
 * - [saveAuthData]: Login veya register+auto-login başarılı olunca çağrılır.
 * - [clearAuthData]: YALNIZCA kullanıcı açık "Çıkış Yap" butonuna basınca çağrılır.
 *
 * UYARI — clearAuthData() şu yerlerden ÇAĞRILMAMALIDIR:
 *   - API 401/403 response'u alınınca (AuthInterceptor)
 *   - Navigation/back button işlemleri sırasında
 *   - Geçici ağ hatalarında
 *
 * DataStore verileri uygulama uninstall edilene kadar kalıcıdır.
 */
class TokenManager(private val context: Context) {
    companion object {
        val TOKEN_KEY = stringPreferencesKey("jwt_token")
        val USERNAME_KEY = stringPreferencesKey("username")
        val THEME_KEY = stringPreferencesKey("theme_preference")
        val ROLE_KEY = stringPreferencesKey("role")
    }
    
    fun getToken(): Flow<String?> = context.dataStore.data.map { it[TOKEN_KEY] }
    fun getUsername(): Flow<String> =
    context.dataStore.data.map { it[USERNAME_KEY] ?: "Kullanıcı" }
    fun getTheme(): Flow<String> = context.dataStore.data.map { it[THEME_KEY] ?: "system" }
    fun getRole(): Flow<String> = context.dataStore.data.map { it[ROLE_KEY] ?: "user" }
    
    suspend fun saveTheme(theme: String) {
        context.dataStore.edit { preferences ->
            preferences[THEME_KEY] = theme
        }
    }
    
    /** Token, kullanıcı adı ve rolü DataStore'a kaydeder. Login/register+auto-login sonrası çağrılır. */
    suspend fun saveAuthData(token: String, username: String, role: String?) {
        context.dataStore.edit { preferences ->
            preferences[TOKEN_KEY] = token
            preferences[USERNAME_KEY] = username
            preferences[ROLE_KEY] = role ?: "user"
        }
    }
    
    /**
     * Auth verilerini ve yerel cache'i temizler.
     * YALNIZCA kullanıcı logout yaptığında (AuthViewModel.logout()) çağrılmalıdır.
     */
    suspend fun clearAuthData() {
        context.dataStore.edit { preferences ->
            preferences.remove(TOKEN_KEY)
            preferences.remove(USERNAME_KEY)
            preferences.remove(ROLE_KEY)
        }
        try {
            AppDatabase.getInstance(context).clearAllTables()
        } catch (e: Exception) {
            // Shield exceptions — yerel cache temizleme kritik değil
        }
    }
    
}
