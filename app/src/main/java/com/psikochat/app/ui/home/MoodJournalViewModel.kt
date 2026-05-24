package com.psikochat.app.ui.home

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.psikochat.app.data.model.Resource
import com.psikochat.app.data.model.MoodJournalEntry
import com.psikochat.app.data.repository.MoodJournalRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch

import com.psikochat.app.data.local.TokenManager
import com.psikochat.app.data.sync.SyncManager
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.launchIn
import kotlinx.coroutines.flow.onEach

class MoodJournalViewModel(
    private val repository: MoodJournalRepository,
    private val tokenManager: TokenManager,
    private val syncManager: SyncManager
) : ViewModel() {

    private val _journalListState = MutableStateFlow<Resource<List<MoodJournalEntry>>>(Resource.Loading())
    val journalListState: StateFlow<Resource<List<MoodJournalEntry>>> = _journalListState

    private val _creationState = MutableStateFlow<Resource<MoodJournalEntry>?>(null)
    val creationState: StateFlow<Resource<MoodJournalEntry>?> = _creationState

    init {
        loadJournals()
    }

    fun loadJournals(days: Int = 30) {
        viewModelScope.launch {
            _journalListState.value = Resource.Loading()
            val username = tokenManager.getUsername().first()

            // 1. Observe resilient local Room cache flow (instant updates)
            repository.getCachedMoodJournals(username)
                .onEach { list ->
                    _journalListState.value = Resource.Success(list)
                }
                .launchIn(viewModelScope)

            // 2. Background non-blocking network refresh to update local Room cache if online
            if (syncManager.isOnline.value) {
                repository.refreshMoodJournals(username, days)
            }
        }
    }

    fun createJournal(mood: String, intensity: Int, note: String?) {
        viewModelScope.launch {
            _creationState.value = Resource.Loading()
            val username = tokenManager.getUsername().first()
            val isOnline = syncManager.isOnline.value
            val result = repository.createMoodJournalResilient(username, mood, intensity, note, isOnline)
            _creationState.value = result
        }
    }

    fun deleteJournal(journalId: Int) {
        viewModelScope.launch {
            val username = tokenManager.getUsername().first()
            val isOnline = syncManager.isOnline.value
            repository.deleteMoodJournalResilient(username, journalId, isOnline)
        }
    }

    fun clearCreationState() {
        _creationState.value = null
    }
}
