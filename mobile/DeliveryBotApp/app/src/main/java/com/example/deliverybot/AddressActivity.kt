package com.example.deliverybot

import android.os.Bundle
import android.util.Log
import android.view.View
import android.widget.*
import androidx.appcompat.app.AppCompatActivity
import com.example.deliverybot.net.RosBridgeClient

class AddressActivity : AppCompatActivity() {
    private val TAG = "DeliveryBot/Address"

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        try {
            setContentView(R.layout.activity_address)
        } catch (t: Throwable) {
            Log.e(TAG, "setContentView failed", t)
            Toast.makeText(this, "UI error", Toast.LENGTH_SHORT).show()
            finish()
            return
        }

        val rg = findViewById<RadioGroup?>(R.id.rgLocations)
        val etOther = findViewById<EditText?>(R.id.etOther)
        val btnConfirm = findViewById<Button?>(R.id.btnConfirmAddress)

        if (rg == null || etOther == null || btnConfirm == null) {
            Log.e(TAG, "One or more views not found (rg=$rg, etOther=$etOther, btnConfirm=$btnConfirm)")
            Toast.makeText(this, "App UI missing — cannot continue", Toast.LENGTH_SHORT).show()
            finish()
            return
        }

        rg.setOnCheckedChangeListener { _, checkedId ->
            etOther.visibility = if (checkedId == R.id.rbOther) View.VISIBLE else View.GONE
        }

        btnConfirm.setOnClickListener {
            val selectedText = when (rg.checkedRadioButtonId) {
                R.id.rbLibrary -> "Library"
                R.id.rbLab -> "Lab"
                R.id.rbLobby -> "Lobby"
                R.id.rbCafeteria -> "Cafeteria"
                R.id.rbOther -> etOther.text.toString().ifBlank { "Other" }
                else -> "Unknown"
            }

            try {
                RosBridgeClient.publish("/app/address", selectedText)
                Toast.makeText(this, "Address sent: $selectedText", Toast.LENGTH_SHORT).show()
            } catch (t: Throwable) {
                Log.e(TAG, "Failed to publish address", t)
                Toast.makeText(this, "Failed to send address", Toast.LENGTH_SHORT).show()
            }
            finish()
        }
    }
}
