package com.saraomega.companion.security

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import com.saraomega.companion.model.DeviceCredentials
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

class KeystoreCredentialStore(context: Context) {
    private val prefs = context.getSharedPreferences("sara_secure_state", Context.MODE_PRIVATE)
    private val alias = "sara_companion_device_key_v1"
    private val keyStore = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }

    private fun key(): SecretKey {
        val existing = keyStore.getKey(alias, null) as? SecretKey
        if (existing != null) return existing
        val generator = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore")
        generator.init(
            KeyGenParameterSpec.Builder(alias, KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .setKeySize(256)
                .build()
        )
        return generator.generateKey()
    }

    fun save(deviceId: String, deviceSecret: String) {
        require(deviceId.isNotBlank() && deviceSecret.length >= 24)
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.ENCRYPT_MODE, key())
        val encrypted = cipher.doFinal(deviceSecret.toByteArray(Charsets.UTF_8))
        prefs.edit()
            .putString("device_id", deviceId)
            .putString("secret_iv", Base64.encodeToString(cipher.iv, Base64.NO_WRAP))
            .putString("secret_ct", Base64.encodeToString(encrypted, Base64.NO_WRAP))
            .apply()
    }

    fun load(): DeviceCredentials? {
        val id = prefs.getString("device_id", null) ?: return null
        val iv = prefs.getString("secret_iv", null) ?: return null
        val ct = prefs.getString("secret_ct", null) ?: return null
        return try {
            val cipher = Cipher.getInstance("AES/GCM/NoPadding")
            cipher.init(Cipher.DECRYPT_MODE, key(), GCMParameterSpec(128, Base64.decode(iv, Base64.NO_WRAP)))
            val secret = String(cipher.doFinal(Base64.decode(ct, Base64.NO_WRAP)), Charsets.UTF_8)
            DeviceCredentials(id, secret)
        } catch (_: Exception) {
            null
        }
    }

    fun clear() {
        prefs.edit().clear().apply()
        if (keyStore.containsAlias(alias)) keyStore.deleteEntry(alias)
    }
}
