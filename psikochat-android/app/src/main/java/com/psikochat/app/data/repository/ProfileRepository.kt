package com.psikochat.app.data.repository

import com.psikochat.app.data.api.PsikoApi
import com.psikochat.app.data.model.ProfileResponse
import com.psikochat.app.data.model.Resource
import com.psikochat.app.data.model.UpdateProfileRequest
import retrofit2.HttpException
import java.io.IOException
import org.json.JSONObject

class ProfileRepository(private val api: PsikoApi) {

    suspend fun getProfile(): Resource<ProfileResponse> {
        return try {
            val response = api.getProfile()
            Resource.Success(response)
        } catch (e: Exception) {
            parseError(e, "Profil bilgileri alınamadı")
        }
    }

    suspend fun updateProfile(request: UpdateProfileRequest): Resource<ProfileResponse> {
        return try {
            val response = api.updateProfile(request)
            Resource.Success(response)
        } catch (e: Exception) {
            parseError(e, "Profil güncellenemedi")
        }
    }

    suspend fun uploadProfilePhoto(filePart: okhttp3.MultipartBody.Part): Resource<ProfileResponse> {
        return try {
            val response = api.uploadProfilePhoto(filePart)
            Resource.Success(response)
        } catch (e: Exception) {
            parseError(e, "Fotoğraf yüklenemedi")
        }
    }

    private fun <T> parseError(e: Exception, defaultMessage: String): Resource<T> {
        return when (e) {
            is HttpException -> {
                val errorBody = e.response()?.errorBody()?.string()
                val parsedMessage = try {
                    if (!errorBody.isNullOrBlank()) {
                        val json = JSONObject(errorBody)
                        when {
                            json.has("message") -> json.getString("message")
                            json.has("detail") -> json.getString("detail")
                            else -> defaultMessage
                        }
                    } else defaultMessage
                } catch (ex: Exception) {
                    defaultMessage
                }
                Resource.Error(parsedMessage)
            }
            is IOException -> Resource.Error("Sunucuya bağlanılamadı. İnternet bağlantınızı kontrol edin.")
            else -> Resource.Error(e.message ?: defaultMessage)
        }
    }
}
