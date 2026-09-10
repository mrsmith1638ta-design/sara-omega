package com.saraomega.companion.telemetry

import com.saraomega.companion.model.TelemetryEnvelope
import com.saraomega.companion.network.SaraApi
import com.saraomega.companion.security.KeystoreCredentialStore
import java.time.Instant
import java.util.UUID

class TelemetryRepository(
    private val credentials: KeystoreCredentialStore,
    private val collector: DeviceTelemetryCollector,
    private val api: SaraApi,
) {
    fun sendNow(): Result<Unit> {
        val creds = credentials.load() ?: return Result.failure(IllegalStateException("not_paired"))
        return runCatching {
            api.sendTelemetry(
                creds,
                TelemetryEnvelope(
                    deviceId = creds.deviceId,
                    messageId = "msg-${UUID.randomUUID()}",
                    eventTimestamp = Instant.now().toString(),
                    metrics = collector.collect(),
                )
            )
        }
    }
}
