package com.psikochat.app.ui.home

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.psikochat.app.data.model.ProfileResponse
import com.psikochat.app.data.model.Resource
import com.psikochat.app.data.model.UpdateProfileRequest
import com.psikochat.app.data.repository.ProfileRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch

class ProfileViewModel(private val repository: ProfileRepository) : ViewModel() {

    private val _profileState = MutableStateFlow<Resource<ProfileResponse>>(Resource.Loading())
    val profileState: StateFlow<Resource<ProfileResponse>> = _profileState

    private val _updateState = MutableStateFlow<Resource<ProfileResponse>?>(null)
    val updateState: StateFlow<Resource<ProfileResponse>?> = _updateState

    init {
        loadProfile()
    }

    fun loadProfile() {
        viewModelScope.launch {
            _profileState.value = Resource.Loading()
            _profileState.value = repository.getProfile()
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
                _profileState.value = result
            }
        }
    }

    fun uploadPhoto(filePart: okhttp3.MultipartBody.Part) {
        viewModelScope.launch {
            _updateState.value = Resource.Loading()
            val result = repository.uploadProfilePhoto(filePart)
            _updateState.value = result
            if (result is Resource.Success) {
                _profileState.value = result
            }
        }
    }

    fun clearUpdateState() {
        _updateState.value = null
    }
}
