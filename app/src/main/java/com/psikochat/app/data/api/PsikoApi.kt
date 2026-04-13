package com.psikochat.app.data.api
import com.psikochat.app.data.model.*
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST

interface PsikoApi {
    @POST("/login")
    suspend fun login(@Body request: AuthRequest): AuthResponse
    
    @POST("/register")
    suspend fun register(@Body request: AuthRequest): RegisterResponse

    @POST("/predict")
    suspend fun sendMessage(@Body request: ChatRequest): ChatResponse

    @GET("/history")
    suspend fun getHistory(): List<HistoryItem>
}
