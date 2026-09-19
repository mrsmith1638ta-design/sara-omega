package com.saraomega.companion.commands

import android.content.Context
import com.saraomega.companion.model.CommandAck
import com.saraomega.companion.model.PendingCommand
import com.saraomega.companion.network.SaraApi
import com.saraomega.companion.security.KeystoreCredentialStore
import com.saraomega.companion.telemetry.DeviceTelemetryCollector
import com.saraomega.companion.telemetry.TelemetryRepository
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonPrimitive

class CommandRepository(
    private val context: Context,
    private val credentials: KeystoreCredentialStore,
    private val api: SaraApi,
) {
    fun pollAndExecute(): Result<Int> {
        val creds = credentials.load() ?: return Result.failure(IllegalStateException("not_paired"))
        return runCatching {
            var handled = 0
            for (command in api.pendingCommands(creds).take(10)) {
                if (command.deviceId != creds.deviceId || command.action !in CommandCapabilities.ALLOWED) {
                    api.acknowledge(creds, command.commandId, CommandAck("REJECTED", mapOf("reason" to JsonPrimitive("capability_or_device_mismatch"))))
                    continue
                }
                val ack = execute(command)
                api.acknowledge(creds, command.commandId, ack)
                handled++
            }
            handled
        }
    }

    private fun execute(command: PendingCommand): CommandAck {
        return try {
            when (command.action) {
                "telemetry.send_now" -> {
                    val result = TelemetryRepository(credentials, DeviceTelemetryCollector(context), api).sendNow()
                    if (result.isSuccess) CommandAck("COMPLETED", mapOf("sent" to JsonPrimitive(true)))
                    else CommandAck("SUBMISSION_UNVERIFIED", mapOf("sent" to JsonPrimitive(false)))
                }
                "health.query", "battery.query", "storage.query", "network.query", "heartbeat.now" -> {
                    val metrics: Map<String, JsonElement> = DeviceTelemetryCollector(context).collect()
                    CommandAck("COMPLETED", mapOf("observed" to JsonPrimitive(true), "metric_count" to JsonPrimitive(metrics.size)))
                }
                else -> CommandAck("REJECTED", mapOf("reason" to JsonPrimitive("unsupported_command")))
            }
        } catch (_: Exception) {
            CommandAck("SUBMISSION_UNVERIFIED", mapOf("reason" to JsonPrimitive("local_execution_outcome_unknown")))
        }
    }
}
