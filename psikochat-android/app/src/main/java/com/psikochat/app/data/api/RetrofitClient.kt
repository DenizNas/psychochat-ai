package com.psikochat.app.data.api

import android.util.Log
import com.psikochat.app.data.local.TokenManager
import com.psikochat.app.BuildConfig
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import java.util.concurrent.TimeUnit

object RetrofitClient {
    private const val TAG = "RetrofitClient"
    
    val BASE_URL = if (BuildConfig.BASE_URL.endsWith("/")) {
        BuildConfig.BASE_URL
    } else {
        "${BuildConfig.BASE_URL}/"
    }
    
    @Volatile
    private var cachedApi: PsikoApi? = null
    
    fun create(tokenManager: TokenManager): PsikoApi {
        Log.d(TAG, "create called. Active BASE_URL: $BASE_URL")
        return cachedApi ?: synchronized(this) {
            cachedApi ?: createInstance(tokenManager).also { cachedApi = it }
        }
    }
    
    private fun createInstance(tokenManager: TokenManager): PsikoApi {
        val logging = HttpLoggingInterceptor().apply {
            level = if (BuildConfig.DEBUG) {
                HttpLoggingInterceptor.Level.BODY
            } else {
                HttpLoggingInterceptor.Level.NONE
            }
        }
        val authInterceptor = AuthInterceptor(tokenManager)
        
        val client = OkHttpClient.Builder()
            .addInterceptor(authInterceptor)
            .addInterceptor(logging)
            .connectTimeout(30, TimeUnit.SECONDS)
            .readTimeout(60, TimeUnit.SECONDS)
            .build()
            
        return Retrofit.Builder()
            .baseUrl(BASE_URL)
            .client(client)
            .addConverterFactory(GsonConverterFactory.create())
            .build()
            .create(PsikoApi::class.java)
    }

    fun resolveProfilePhotoUrl(url: String?): String? {
        if (url.isNullOrBlank()) return null
        if (url.startsWith("http://") || url.startsWith("https://")) {
            return url
        }
        return if (url.startsWith("/")) {
            "${BASE_URL.removeSuffix("/")}$url"
        } else {
            "$BASE_URL$url"
        }
    }
}
