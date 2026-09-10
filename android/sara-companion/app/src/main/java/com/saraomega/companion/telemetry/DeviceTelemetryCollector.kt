package com.saraomega.companion.telemetry

import android.app.ActivityManager
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.os.BatteryManager
import android.os.Build
import android.os.Environment
import android.os.StatFs
import android.os.SystemClock
import com.saraomega.companion.BuildConfig
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonPrimitive

class DeviceTelemetryCollector(private val context: Context) {
    fun collect(): Map<String, JsonElement> {
        val out = linkedMapOf<String, JsonElement>()
        val battery = context.registerReceiver(null, IntentFilter(Intent.ACTION_BATTERY_CHANGED))
        battery?.let {
            val level = it.getIntExtra(BatteryManager.EXTRA_LEVEL, -1)
            val scale = it.getIntExtra(BatteryManager.EXTRA_SCALE, -1)
            if (level >= 0 && scale > 0) out["battery_percent"] = JsonPrimitive((level * 100) / scale)
            val status = it.getIntExtra(BatteryManager.EXTRA_STATUS, -1)
            if (status >= 0) out["charging"] = JsonPrimitive(status == BatteryManager.BATTERY_STATUS_CHARGING || status == BatteryManager.BATTERY_STATUS_FULL)
            val plugged = it.getIntExtra(BatteryManager.EXTRA_PLUGGED, -1)
            if (plugged >= 0) out["charging_source"] = JsonPrimitive(plugged)
            val temp = it.getIntExtra(BatteryManager.EXTRA_TEMPERATURE, Int.MIN_VALUE)
            if (temp != Int.MIN_VALUE) out["battery_temperature_c"] = JsonPrimitive(temp / 10.0)
        }
        val stat = StatFs(Environment.getDataDirectory().absolutePath)
        out["storage_free_bytes"] = JsonPrimitive(stat.availableBytes)
        out["storage_total_bytes"] = JsonPrimitive(stat.totalBytes)
        val am = context.getSystemService(ActivityManager::class.java)
        val mi = ActivityManager.MemoryInfo(); am.getMemoryInfo(mi)
        out["memory_avail_bytes"] = JsonPrimitive(mi.availMem)
        val cm = context.getSystemService(ConnectivityManager::class.java)
        val network = cm.activeNetwork
        val caps = network?.let { cm.getNetworkCapabilities(it) }
        out["network_connected"] = JsonPrimitive(caps?.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET) == true)
        if (caps != null) {
            val type = when {
                caps.hasTransport(NetworkCapabilities.TRANSPORT_WIFI) -> "wifi"
                caps.hasTransport(NetworkCapabilities.TRANSPORT_CELLULAR) -> "cellular"
                caps.hasTransport(NetworkCapabilities.TRANSPORT_ETHERNET) -> "ethernet"
                else -> "other"
            }
            out["network_type"] = JsonPrimitive(type)
        }
        out["uptime_seconds"] = JsonPrimitive(SystemClock.elapsedRealtime() / 1000)
        out["heartbeat"] = JsonPrimitive(true)
        out["android_version"] = JsonPrimitive(Build.VERSION.RELEASE)
        out["manufacturer"] = JsonPrimitive(Build.MANUFACTURER)
        out["model"] = JsonPrimitive(Build.MODEL)
        out["app_version"] = JsonPrimitive(BuildConfig.VERSION_NAME)
        return out
    }
}
