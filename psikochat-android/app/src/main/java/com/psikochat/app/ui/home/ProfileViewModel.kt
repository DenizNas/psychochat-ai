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
        loadProfile()
    }

    fun loadProfile() {
        viewModelScope.launch {
            _profileState.value = Resource.Loading(applyCacheBuster(cachedProfile))
            val result = repository.getProfile()
            if (result is Resource.Success) {
                val processed = applyCacheBuster(result.data)
                cachedProfile = processed
                _profileState.value = Resource.Success(processed!!)
                result.data?.themePreference?.let {
                    tokenManager.saveThemePreference(it)
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
                val processed = applyCacheBuster(result.data)
                cachedProfile = processed
                _profileState.value = Resource.Success(processed!!)
                result.data?.themePreference?.let {
                    tokenManager.saveThemePreference(it)
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
                photoUpdateTimestamp = System.currentTimeMillis()
                val processed = applyCacheBuster(result.data)
                cachedProfile = processed
                _profileState.value = Resource.Success(processed!!)
            }
        }
    }

    fun clearUpdateState() {
        _updateState.value = null
    }
}
