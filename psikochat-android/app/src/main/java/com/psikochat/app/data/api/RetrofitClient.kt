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
    
    val BASE_URL: String = run {
        val configuredUrl = BuildConfig.BASE_URL
        if (configuredUrl.contains("staging-api.psikochat.com") || configuredUrl.contains("api.psikochat.com")) {
            if (configuredUrl.endsWith("/")) configuredUrl else "$configuredUrl/"
        } else {
            val isEmulator = android.os.Build.FINGERPRINT.startsWith("generic")
                    || android.os.Build.FINGERPRINT.startsWith("unknown")
                    || android.os.Build.MODEL.contains("google_sdk")
                    || android.os.Build.MODEL.contains("Emulator")
                    || android.os.Build.MODEL.contains("Android SDK built for x86")
                    || android.os.Build.MANUFACTURER.contains("Genymotion")
                    || android.os.Build.PRODUCT.contains("sdk_google")
                    || android.os.Build.PRODUCT.contains("google_sdk")
                    || android.os.Build.PRODUCT.contains("sdk")
                    || android.os.Build.PRODUCT.contains("sdk_x86")
                    || android.os.Build.PRODUCT.contains("vbox86p")
                    || android.os.Build.PRODUCT.contains("emulator")
                    || android.os.Build.PRODUCT.contains("simulator")
            
            if (isEmulator) {
                "http://10.0.2.2:8000/"
            } else {
                "http://10.200.38.150:8000/"
            }
        }
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
