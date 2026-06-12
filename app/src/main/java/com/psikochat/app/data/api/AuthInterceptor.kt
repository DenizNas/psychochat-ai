package com.psikochat.app.data.api
import android.util.Log
import com.psikochat.app.data.local.TokenManager
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import okhttp3.Interceptor
import okhttp3.Protocol
import okhttp3.Response
import okhttp3.ResponseBody.Companion.toResponseBody

/**
 * AuthInterceptor: Her API isteğine Authorization: Bearer <token> header'ı ekler.
 *
 * ÖNEMLİ: 401/403 response alındığında tokenı TEMIZLEMEZ.
 * Token temizleme işlemi yalnızca explicit logout veya /logout endpoint
 * çağrısı sonrası yapılır. Bu sayede geçici sunucu hataları kullanıcıyı
 * çıkış yaptırmaz ve session persistence sağlanır.
 */
class AuthInterceptor(private val tokenManager: TokenManager) : Interceptor {
    companion object {
        private const val TAG = "AuthInterceptor"
    }

    override fun intercept(chain: Interceptor.Chain): Response {
        val token = runBlocking { tokenManager.getToken().first() }
        val originalRequest = chain.request()
        val path = originalRequest.url.encodedPath

        val isAuthEndpoint = path.contains("/login") || path.contains("/register")

        // Token yoksa ve auth endpoint değilse 401 döndür (network call yapmadan)
        if (token.isNullOrEmpty() && !isAuthEndpoint) {
            Log.w(TAG, "AUTH_INTERCEPTOR | Token yok, endpoint: $path — 401 döndürülüyor")
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
            Log.d(TAG, "AUTH_INTERCEPTOR | Bearer token eklendi, endpoint: $path")
        }

        val response = chain.proceed(requestBuilder.build())

        // NOT: 401/403 aldığımızda tokenı silmiyoruz!
        // Geçici backend hataları veya belirli endpoint'lerin 403 dönmesi
        // (örn. premium içerik engeli) kullanıcıyı zorla çıkış yaptırmamalı.
        // Logout işlemi yalnızca kullanıcının explicit "Çıkış Yap" butonuna
        // basması ile AuthViewModel.logout() üzerinden yapılır.
        if (response.code == 401 || response.code == 403) {
            Log.w(TAG, "AUTH_INTERCEPTOR | ${response.code} response alındı, endpoint: $path — token korunuyor")
        }

        return response
    }
}
