package com.saraomega.companion.pairing

import android.os.Build
import com.saraomega.companion.commands.CommandCapabilities
import com.saraomega.companion.model.PairingClaim
import com.saraomega.companion.network.SaraApi
import com.saraomega.companion.security.KeystoreCredentialStore

sealed interface PairingState {
    data object Unpaired : PairingState
    data object Pairing : PairingState
    data class Paired(val deviceId: String) : PairingState
    data class Error(val message: String) : PairingState
}

class PairingRepository(
    private val api: SaraApi,
    private val credentials: KeystoreCredentialStore,
) {
    fun current(): PairingState = credentials.load()?.let { PairingState.Paired(it.deviceId) } ?: PairingState.Unpaired

    fun claim(code: String): PairingState {
        val normalized = code.trim().uppercase()
        if (normalized.length < 16) return PairingState.Error("Enter the pairing code shown by SARA")
        return try {
            val response = api.claimPairing(
                PairingClaim(
                    code = normalized,
                    name = "${Build.MANUFACTURER} ${Build.MODEL}",
                    model = Build.MODEL,
                    manufacturer = Build.MANUFACTURER,
                    androidVersion = Build.VERSION.RELEASE,
                    capabilities = CommandCapabilities.ALLOWED,
                    metrics = setOf(
                        "battery_percent", "charging", "charging_source", "battery_temperature_c",
                        "storage_free_bytes", "storage_total_bytes", "memory_avail_bytes",
                        "network_connected", "network_type", "uptime_seconds", "heartbeat",
                        "android_version", "manufacturer", "model", "app_version"
                    ),
                )
            )
            credentials.save(response.deviceId, response.deviceSecret)
            PairingState.Paired(response.deviceId)
        } catch (_: SecurityException) {
            PairingState.Error("SARA rejected this pairing attempt")
        } catch (_: Exception) {
            PairingState.Error("Could not pair with SARA. Check your connection and code.")
        }
    }

    fun unpair() {
        credentials.clear()
    }
}
