package com.saraomega.companion.telemetry

import android.content.Context
import androidx.work.*
import com.saraomega.companion.network.SaraApi
import com.saraomega.companion.security.KeystoreCredentialStore
import java.util.concurrent.TimeUnit

class TelemetryWorker(appContext: Context, params: WorkerParameters) : Worker(appContext, params) {
    override fun doWork(): Result {
        val repo = TelemetryRepository(
            KeystoreCredentialStore(applicationContext),
            DeviceTelemetryCollector(applicationContext),
            SaraApi(),
        )
        val result = repo.sendNow()
        return if (result.isSuccess) Result.success() else if (result.exceptionOrNull() is SecurityException) Result.failure() else Result.retry()
    }

    companion object {
        const val PERIODIC_NAME = "sara-telemetry-periodic"
        const val MANUAL_NAME = "sara-telemetry-manual"

        fun schedule(context: Context) {
            val constraints = Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build()
            val request = PeriodicWorkRequestBuilder<TelemetryWorker>(15, TimeUnit.MINUTES)
                .setConstraints(constraints)
                .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 30, TimeUnit.SECONDS)
                .build()
            WorkManager.getInstance(context).enqueueUniquePeriodicWork(PERIODIC_NAME, ExistingPeriodicWorkPolicy.UPDATE, request)
        }

        fun sendNow(context: Context) {
            val request = OneTimeWorkRequestBuilder<TelemetryWorker>()
                .setConstraints(Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build())
                .build()
            WorkManager.getInstance(context).enqueueUniqueWork(MANUAL_NAME, ExistingWorkPolicy.REPLACE, request)
        }

        fun cancel(context: Context) {
            WorkManager.getInstance(context).cancelUniqueWork(PERIODIC_NAME)
            WorkManager.getInstance(context).cancelUniqueWork(MANUAL_NAME)
        }
    }
}
