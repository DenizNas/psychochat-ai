package com.psikochat.app.data.api

import android.util.Log
import com.psikochat.app.data.local.TokenManager
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import okhttp3.Interceptor
import okhttp3.Protocol
import okhttp3.Response
import okhttp3.ResponseBody.Companion.toResponseBody

class AuthInterceptor(private val tokenManager: TokenManager) : Interceptor {
    companion object {
        private const val TAG = "AuthInterceptor"
    }

    override fun intercept(chain: Interceptor.Chain): Response {
        val token = runBlocking { tokenManager.getToken().first() }
        val originalRequest = chain.request()
        val path = originalRequest.url.encodedPath
        
        val isAuthEndpoint = path.contains("login") || path.contains("register")
        if (token.isNullOrEmpty() && !isAuthEndpoint) {
            Log.w(TAG, "Token yok, endpoint: $path — 401 döndürülüyor")
            return Response.Builder()
                .request(originalRequest)
                .protocol(Protocol.HTTP_1_1)
                .code(401)
                .message("Unauthorized")
                .body("".toResponseBody(null))
                .build()
        }

        val requestBuilder = originalRequest.newBuilder()
        if (!token.isNullOrEmpty()) {
            requestBuilder.addHeader("Authorization", "Bearer $token")
            Log.d(TAG, "Bearer token attached successfully to endpoint: $path")
        } else {
            Log.d(TAG, "No token attached (auth endpoint or onboarding): $path")
        }
        
        val response = chain.proceed(requestBuilder.build())
        
        if (response.code == 401 || response.code == 403) {
            Log.w(TAG, "HTTP status ${response.code} received on $path - token is NOT cleared to preserve session persistence.")
        }
        
        return response
    }
}
