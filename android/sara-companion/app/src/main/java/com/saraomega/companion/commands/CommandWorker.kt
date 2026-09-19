package com.saraomega.companion.commands

import android.content.Context
import androidx.work.*
import com.saraomega.companion.network.SaraApi
import com.saraomega.companion.security.KeystoreCredentialStore
import java.util.concurrent.TimeUnit

class CommandWorker(appContext: Context, params: WorkerParameters) : Worker(appContext, params) {
    override fun doWork(): Result {
        val result = CommandRepository(applicationContext, KeystoreCredentialStore(applicationContext), SaraApi()).pollAndExecute()
        return if (result.isSuccess) Result.success() else if (result.exceptionOrNull() is SecurityException) Result.failure() else Result.retry()
    }

    companion object {
        const val PERIODIC_NAME = "sara-command-poll"
        fun schedule(context: Context) {
            val request = PeriodicWorkRequestBuilder<CommandWorker>(15, TimeUnit.MINUTES)
                .setConstraints(Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build())
                .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 30, TimeUnit.SECONDS)
                .build()
            WorkManager.getInstance(context).enqueueUniquePeriodicWork(PERIODIC_NAME, ExistingPeriodicWorkPolicy.UPDATE, request)
        }
        fun cancel(context: Context) = WorkManager.getInstance(context).cancelUniqueWork(PERIODIC_NAME)
    }
}
