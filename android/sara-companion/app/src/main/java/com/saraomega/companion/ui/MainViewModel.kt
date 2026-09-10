package com.saraomega.companion.ui

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.saraomega.companion.commands.CommandWorker
import com.saraomega.companion.network.SaraApi
import com.saraomega.companion.pairing.PairingRepository
import com.saraomega.companion.pairing.PairingState
import com.saraomega.companion.security.KeystoreCredentialStore
import com.saraomega.companion.telemetry.TelemetryWorker
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch

class MainViewModel(app: Application) : AndroidViewModel(app) {
    private val credentials = KeystoreCredentialStore(app)
    private val pairing = PairingRepository(SaraApi(), credentials)
    private val _state = MutableStateFlow(stateFromPairing(pairing.current()))
    val state: StateFlow<MainUiState> = _state

    private fun stateFromPairing(state: PairingState): MainUiState = when (state) {
        PairingState.Unpaired -> MainUiState()
        PairingState.Pairing -> MainUiState(status = "Pairing with SARA…")
        is PairingState.Paired -> MainUiState(paired = true, status = "Paired", deviceId = state.deviceId)
        is PairingState.Error -> MainUiState(status = state.message)
    }

    fun pair(code: String) {
        _state.value = stateFromPairing(PairingState.Pairing)
        viewModelScope.launch(Dispatchers.IO) {
            val result = pairing.claim(code)
            _state.value = stateFromPairing(result)
            if (result is PairingState.Paired) {
                TelemetryWorker.schedule(getApplication())
                CommandWorker.schedule(getApplication())
                TelemetryWorker.sendNow(getApplication())
            }
        }
    }

    fun sendNow() {
        if (!_state.value.paired) return
        TelemetryWorker.sendNow(getApplication())
        _state.value = _state.value.copy(lastAction = "Telemetry queued")
    }

    fun unpair() {
        TelemetryWorker.cancel(getApplication())
        CommandWorker.cancel(getApplication())
        pairing.unpair()
        _state.value = MainUiState(lastAction = "Local pairing removed")
    }
}
