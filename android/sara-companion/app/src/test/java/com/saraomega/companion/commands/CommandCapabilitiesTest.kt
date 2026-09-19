package com.saraomega.companion.commands

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Test

class CommandCapabilitiesTest {
    @Test
    fun onlyApprovedLowRiskCommandsAreExposed() {
        assertEquals(
            setOf("health.query", "battery.query", "storage.query", "network.query", "heartbeat.now", "telemetry.send_now"),
            CommandCapabilities.ALLOWED,
        )
        assertFalse("factory_reset" in CommandCapabilities.ALLOWED)
        assertFalse("shell.exec" in CommandCapabilities.ALLOWED)
    }
}
