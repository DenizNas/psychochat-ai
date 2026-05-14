package com.psikochat.app.data.model
import com.google.gson.annotations.SerializedName

data class LoginRequest(val username: String, val password: String)
data class RegisterRequest(val username: String, val password: String)
data class AuthResponse(val access_token: String, val token_type: String, val username: String)
data class RegisterResponse(val message: String)
data class ChatRequest(
    @SerializedName("text") val text: String, 
    @SerializedName("language") val language: String = "tr"
)
data class ChatResponse(
    @SerializedName("emotion") val emotion: String, 
    @SerializedName("risk") val risk: String, 
    @SerializedName("response") val response: String, 
    @SerializedName("emergency_contact") val emergencyContact: String?
)
data class HistoryItem(
    @SerializedName("id") val id: Int? = null,
    @SerializedName("role") val role: String, 
    @SerializedName("text") val text: String,
    @SerializedName("timestamp") val timestamp: String? = null
)

sealed class Resource<T>(val data: T? = null, val message: String? = null) {
    class Success<T>(data: T) : Resource<T>(data)
    class Error<T>(message: String, data: T? = null) : Resource<T>(data, message)
    class Loading<T> : Resource<T>()
}
