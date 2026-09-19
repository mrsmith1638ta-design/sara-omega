package com.saraomega.companion.model

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonElement

@Serializable
data class DeviceDescriptor(
    val name: String,
    val model: String,
    val manufacturer: String,
    @SerialName("android_version") val androidVersion: String,
    val capabilities: Set<String>,
    val metrics: Set<String>,
)

@Serializable
data class PairingClaim(
    val code: String,
    val name: String,
    val model: String,
    val manufacturer: String,
    @SerialName("android_version") val androidVersion: String,
    val capabilities: Set<String>,
    val metrics: Set<String>,
)

@Serializable
data class PairingClaimResponse(
    @SerialName("device_id") val deviceId: String,
    @SerialName("device_secret") val deviceSecret: String,
    @SerialName("server_base_url") val serverBaseUrl: String,
    @SerialName("accepted_commands") val acceptedCommands: Set<String>,
    @SerialName("accepted_metrics") val acceptedMetrics: Set<String>,
)

@Serializable
data class TelemetryEnvelope(
    @SerialName("device_id") val deviceId: String,
    @SerialName("message_id") val messageId: String,
    @SerialName("event_timestamp") val eventTimestamp: String,
    @SerialName("schema_version") val schemaVersion: String = "1",
    val topic: String = "telemetry",
    val metrics: Map<String, JsonElement>,
)

@Serializable
data class PendingCommand(
    @SerialName("command_id") val commandId: String,
    @SerialName("device_id") val deviceId: String,
    val action: String,
    val parameters: Map<String, JsonElement> = emptyMap(),
)

@Serializable
data class PendingCommandsResponse(val commands: List<PendingCommand> = emptyList())

@Serializable
data class CommandAck(
    val status: String,
    val result: Map<String, JsonElement> = emptyMap(),
)

@Serializable
data class CapabilityDocument(val commands: Set<String>)

data class DeviceCredentials(val deviceId: String, val deviceSecret: String)

enum class ConnectionState { UNPAIRED, PAIRING, PAIRED, OFFLINE, AUTH_ERROR, ERROR }
