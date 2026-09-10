package com.saraomega.companion.commands

object CommandCapabilities {
    val ALLOWED: Set<String> = setOf(
        "health.query",
        "battery.query",
        "storage.query",
        "network.query",
        "heartbeat.now",
        "telemetry.send_now",
    )
}
