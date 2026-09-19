package com.saraomega.companion.network

import com.saraomega.companion.BuildConfig
import com.saraomega.companion.model.*
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import java.util.concurrent.TimeUnit

class SaraApi(
    private val client: OkHttpClient = OkHttpClient.Builder()
        .connectTimeout(8, TimeUnit.SECONDS)
        .readTimeout(12, TimeUnit.SECONDS)
        .writeTimeout(12, TimeUnit.SECONDS)
        .build(),
) {
    private val json = Json { ignoreUnknownKeys = true; explicitNulls = false }
    private val mediaType = "application/json".toMediaType()
    private val base = BuildConfig.SARA_BASE_URL.trimEnd('/')

    fun claimPairing(claim: PairingClaim): PairingClaimResponse {
        val req = Request.Builder().url("$base/iot/pairing/claim")
            .post(json.encodeToString(claim).toRequestBody(mediaType)).build()
        client.newCall(req).execute().use { r ->
            if (!r.isSuccessful) throw IllegalStateException("pairing_rejected:${r.code}")
            return json.decodeFromString(r.body?.string() ?: error("empty_pairing_response"))
        }
    }

    fun sendTelemetry(credentials: DeviceCredentials, envelope: TelemetryEnvelope) {
        val req = Request.Builder().url("$base/iot/telemetry")
            .header("X-SARA-Device-Secret", credentials.deviceSecret)
            .header("X-SARA-IoT-Transport", "https")
            .post(json.encodeToString(envelope).toRequestBody(mediaType)).build()
        client.newCall(req).execute().use { r ->
            if (r.code == 401 || r.code == 403) throw SecurityException("device_authentication_rejected")
            if (!r.isSuccessful) throw IllegalStateException("telemetry_http_${r.code}")
        }
    }

    fun pendingCommands(credentials: DeviceCredentials): List<PendingCommand> {
        val req = Request.Builder().url("$base/iot/device/commands/pending")
            .header("X-SARA-Device-Id", credentials.deviceId)
            .header("X-SARA-Device-Secret", credentials.deviceSecret)
            .get().build()
        client.newCall(req).execute().use { r ->
            if (r.code == 401 || r.code == 403) throw SecurityException("device_authentication_rejected")
            if (!r.isSuccessful) throw IllegalStateException("command_poll_http_${r.code}")
            return json.decodeFromString<PendingCommandsResponse>(r.body?.string() ?: "{}").commands
        }
    }

    fun acknowledge(credentials: DeviceCredentials, commandId: String, ack: CommandAck) {
        val req = Request.Builder().url("$base/iot/device/commands/$commandId/ack")
            .header("X-SARA-Device-Id", credentials.deviceId)
            .header("X-SARA-Device-Secret", credentials.deviceSecret)
            .post(json.encodeToString(ack).toRequestBody(mediaType)).build()
        client.newCall(req).execute().use { r ->
            if (r.code == 401 || r.code == 403) throw SecurityException("device_authentication_rejected")
            if (!r.isSuccessful) throw IllegalStateException("command_ack_http_${r.code}")
        }
    }
}
