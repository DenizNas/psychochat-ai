package com.psikochat.app.data.model
import com.google.gson.annotations.SerializedName

data class LoginRequest(val username: String, val password: String)
data class RegisterRequest(val username: String, val password: String)
data class AuthResponse(val access_token: String, val token_type: String, val username: String)
data class RegisterResponse(val message: String)
data class ChatRequest(val text: String, val language: String = "tr")
data class ChatResponse(val emotion: String, val risk: String, val response: String, val emergency_contact: String?)
data class HistoryItem(val role: String, val text: String)

sealed class Resource<T>(val data: T? = null, val message: String? = null) {
    class Success<T>(data: T) : Resource<T>(data)
    class Error<T>(message: String, data: T? = null) : Resource<T>(data, message)
    class Loading<T> : Resource<T>()
}
