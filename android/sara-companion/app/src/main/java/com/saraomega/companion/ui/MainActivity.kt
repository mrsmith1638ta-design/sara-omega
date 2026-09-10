package com.saraomega.companion.ui

import android.os.Bundle
import androidx.activity.viewModels
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.lifecycleScope
import androidx.lifecycle.repeatOnLifecycle
import com.saraomega.companion.databinding.ActivityMainBinding
import kotlinx.coroutines.launch

class MainActivity : AppCompatActivity() {
    private lateinit var binding: ActivityMainBinding
    private val vm: MainViewModel by viewModels()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        binding.pairButton.setOnClickListener { vm.pair(binding.pairCode.text?.toString().orEmpty()) }
        binding.sendButton.setOnClickListener { vm.sendNow() }
        binding.checkButton.setOnClickListener { vm.sendNow() }
        binding.unpairButton.setOnClickListener {
            AlertDialog.Builder(this)
                .setTitle("Unpair this device?")
                .setMessage("This removes the local SARA credential. It does not silently change your phone settings.")
                .setNegativeButton("Cancel", null)
                .setPositiveButton("Unpair") { _, _ -> vm.unpair() }
                .show()
        }

        lifecycleScope.launch {
            repeatOnLifecycle(Lifecycle.State.STARTED) {
                vm.state.collect { state -> render(state) }
            }
        }
    }

    private fun render(state: MainUiState) {
        binding.statusValue.text = state.status
        binding.deviceValue.text = state.deviceId ?: "Not assigned"
        binding.lastActionValue.text = state.lastAction
        binding.scheduleValue.text = state.scheduleText
        binding.pairCode.isEnabled = !state.paired
        binding.pairButton.isEnabled = !state.paired
        binding.sendButton.isEnabled = state.paired
        binding.checkButton.isEnabled = state.paired
        binding.unpairButton.isEnabled = state.paired
        if (state.paired) binding.pairCode.text?.clear()
    }
}
