package com.psikochat.app.data.api
import com.psikochat.app.data.local.TokenManager
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import okhttp3.Interceptor
import okhttp3.Protocol
import okhttp3.Response
import okhttp3.ResponseBody.Companion.toResponseBody

class AuthInterceptor(private val tokenManager: TokenManager) : Interceptor {
    override fun intercept(chain: Interceptor.Chain): Response {
        val token = runBlocking { tokenManager.getToken().first() }
        val originalRequest = chain.request()
        
        val isAuthEndpoint = originalRequest.url.encodedPath.contains("login") || originalRequest.url.encodedPath.contains("register")
        if (token.isNullOrEmpty() && !isAuthEndpoint) {
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
        }
        
        val response = chain.proceed(requestBuilder.build())
        
        if (response.code == 401 || response.code == 403) {
            runBlocking { tokenManager.clearAuthData() }
        }
        
        return response
    }
}
