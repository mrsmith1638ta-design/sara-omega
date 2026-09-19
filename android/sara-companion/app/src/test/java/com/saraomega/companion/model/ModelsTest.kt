package com.saraomega.companion.model

import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonPrimitive
import org.junit.Assert.assertTrue
import org.junit.Test

class ModelsTest {
    @Test
    fun telemetryEnvelopeSerializesServerFieldNames() {
        val envelope = TelemetryEnvelope(
            deviceId = "android-123",
            messageId = "msg-12345678",
            eventTimestamp = "2026-09-07T23:00:00Z",
            metrics = mapOf("battery_percent" to JsonPrimitive(80)),
        )
        val encoded = Json.encodeToString(envelope)
        assertTrue(encoded.contains("\"device_id\""))
        assertTrue(encoded.contains("\"message_id\""))
        assertTrue(encoded.contains("\"battery_percent\""))
    }
}
