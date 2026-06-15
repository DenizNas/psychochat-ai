package com.psikochat.app.ui.home

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.psikochat.app.data.local.TokenManager
import com.psikochat.app.data.model.ProfileResponse
import com.psikochat.app.data.model.Resource
import com.psikochat.app.data.model.UpdateProfileRequest
import com.psikochat.app.data.repository.ProfileRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch

class ProfileViewModel(
    private val repository: ProfileRepository,
    private val tokenManager: TokenManager
) : ViewModel() {

    companion object {
        private var cachedProfile: ProfileResponse? = null
        private var photoUpdateTimestamp: Long? = null

        fun clearCache() {
            cachedProfile = null
            photoUpdateTimestamp = null
        }
    }

    private fun applyCacheBuster(profile: ProfileResponse?): ProfileResponse? {
        if (profile == null) return null
        val timestamp = photoUpdateTimestamp ?: return profile
        val rawUrl = profile.profilePhotoUrl
        if (rawUrl.isNullOrBlank()) return profile
        
        val separator = if (rawUrl.contains("?")) "&" else "?"
        val bustedUrl = "$rawUrl${separator}v=$timestamp"
        return profile.copy(profilePhotoUrl = bustedUrl)
    }

    private val _profileState = MutableStateFlow<Resource<ProfileResponse>>(
        applyCacheBuster(cachedProfile)?.let { Resource.Success(it) } ?: Resource.Loading()
    )
    val profileState: StateFlow<Resource<ProfileResponse>> = _profileState

    private val _updateState = MutableStateFlow<Resource<ProfileResponse>?>(null)
    val updateState: StateFlow<Resource<ProfileResponse>?> = _updateState

    init {
        viewModelScope.launch {
            try {
                val localUrl = tokenManager.getProfilePhotoUrl().first()
                if (!localUrl.isNullOrBlank()) {
                    val current = cachedProfile
                    if (current == null) {
                        val dummy = ProfileResponse(
                            username = tokenManager.getUsername().first(),
                            displayName = tokenManager.getFullName().first(),
                            bio = null,
                            profilePhotoUrl = localUrl,
                            preferredLanguage = "tr",
                            responseStyle = "supportive",
                            themePreference = "system",
                            notificationsEnabled = true,
                            privacyMode = false,
                            answerLengthPreference = "medium",
                            createdAt = "",
                            updatedAt = ""
                        )
                        cachedProfile = dummy
                        _profileState.value = Resource.Loading(applyCacheBuster(dummy))
                    } else if (current.profilePhotoUrl.isNullOrBlank()) {
                        val updated = current.copy(profilePhotoUrl = localUrl)
                        cachedProfile = updated
                        _profileState.value = Resource.Loading(applyCacheBuster(updated))
                    }
                }
            } catch (e: Exception) {
                // Ignore errors reading local cache during initialization
            }
            loadProfile()
        }
    }

    fun loadProfile() {
        viewModelScope.launch {
            _profileState.value = Resource.Loading(applyCacheBuster(cachedProfile))
            val result = repository.getProfile()
            if (result is Resource.Success) {
                val data = result.data
                if (data != null) {
                    val finalPhotoUrl = if (data.profilePhotoUrl.isNullOrBlank()) {
                        cachedProfile?.profilePhotoUrl ?: tokenManager.getProfilePhotoUrl().first()
                    } else {
                        data.profilePhotoUrl
                    }
                    val updatedData = data.copy(profilePhotoUrl = finalPhotoUrl)
                    if (!finalPhotoUrl.isNullOrBlank()) {
                        val canonicalUrl = finalPhotoUrl.substringBefore("?").substringBefore("&")
                        tokenManager.saveProfilePhotoUrl(canonicalUrl)
                    }
                    val processed = applyCacheBuster(updatedData)
                    cachedProfile = processed
                    _profileState.value = Resource.Success(processed!!)
                    tokenManager.saveThemePreference(data.themePreference)
                }
            } else {
                val cached = cachedProfile
                if (cached != null) {
                    _profileState.value = Resource.Error(result.message ?: "Profil bilgileri alınamadı", cached)
                } else {
                    _profileState.value = result
                }
            }
        }
    }

    fun updateProfile(
        displayName: String? = null,
        bio: String? = null,
        language: String? = null,
        style: String? = null,
        theme: String? = null,
        notifications: Boolean? = null,
        privacy: Boolean? = null,
        answerLength: String? = null
    ) {
        viewModelScope.launch {
            _updateState.value = Resource.Loading()
            val request = UpdateProfileRequest(
                displayName = displayName,
                bio = bio,
                preferredLanguage = language,
                responseStyle = style,
                themePreference = theme,
                notificationsEnabled = notifications,
                privacyMode = privacy,
                answerLengthPreference = answerLength
            )
            val result = repository.updateProfile(request)
            _updateState.value = result
            if (result is Resource.Success) {
                val data = result.data
                if (data != null) {
                    val finalPhotoUrl = if (data.profilePhotoUrl.isNullOrBlank()) {
                        cachedProfile?.profilePhotoUrl ?: tokenManager.getProfilePhotoUrl().first()
                    } else {
                        data.profilePhotoUrl
                    }
                    val updatedData = data.copy(profilePhotoUrl = finalPhotoUrl)
                    if (!finalPhotoUrl.isNullOrBlank()) {
                        val canonicalUrl = finalPhotoUrl.substringBefore("?").substringBefore("&")
                        tokenManager.saveProfilePhotoUrl(canonicalUrl)
                    }
                    val processed = applyCacheBuster(updatedData)
                    cachedProfile = processed
                    _profileState.value = Resource.Success(processed!!)
                    tokenManager.saveThemePreference(data.themePreference)
                }
            }
        }
    }

    fun uploadPhoto(filePart: okhttp3.MultipartBody.Part) {
        viewModelScope.launch {
            _updateState.value = Resource.Loading()
            val result = repository.uploadProfilePhoto(filePart)
            _updateState.value = result
            if (result is Resource.Success) {
                val data = result.data
                if (data != null) {
                    photoUpdateTimestamp = System.currentTimeMillis()
                    val finalPhotoUrl = data.profilePhotoUrl
                    if (!finalPhotoUrl.isNullOrBlank()) {
                        val canonicalUrl = finalPhotoUrl.substringBefore("?").substringBefore("&")
                        tokenManager.saveProfilePhotoUrl(canonicalUrl)
                    }
                    val processed = applyCacheBuster(data)
                    cachedProfile = processed
                    _profileState.value = Resource.Success(processed!!)
                }
            }
        }
    }

    fun clearUpdateState() {
        _updateState.value = null
    }
}
