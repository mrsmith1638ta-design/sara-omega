package com.saraomega.companion.ui

data class MainUiState(
    val paired: Boolean = false,
    val status: String = "Not paired",
    val deviceId: String? = null,
    val lastAction: String = "None yet",
    val scheduleText: String = "About every 15 minutes; Android may defer background work",
)
