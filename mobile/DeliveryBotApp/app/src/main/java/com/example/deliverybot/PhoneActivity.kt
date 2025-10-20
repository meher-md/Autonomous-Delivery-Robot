package com.example.deliverybot

import android.os.Bundle
import android.util.Log
import android.widget.Button
import android.widget.EditText
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import com.example.deliverybot.net.RosBridgeClient

class PhoneActivity : AppCompatActivity() {
    private val TAG = "DeliveryBot/Phone"

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        try {
            setContentView(R.layout.activity_phone)
        } catch (t: Throwable) {
            Log.e(TAG, "setContentView failed", t)
            Toast.makeText(this, "UI error", Toast.LENGTH_SHORT).show()
            finish()
            return
        }

        val etPhone = findViewById<EditText?>(R.id.etPhoneInput)
        val btnConfirm = findViewById<Button?>(R.id.btnConfirmPhone)

        if (etPhone == null || btnConfirm == null) {
            Log.e(TAG, "One or more views not found (etPhone=$etPhone, btnConfirm=$btnConfirm)")
            Toast.makeText(this, "App UI missing — cannot continue", Toast.LENGTH_SHORT).show()
            finish()
            return
        }

        btnConfirm.setOnClickListener {
            val phone = etPhone.text.toString().trim()
            if (phone.isBlank()) {
                Toast.makeText(this, "Enter phone number", Toast.LENGTH_SHORT).show()
                return@setOnClickListener
            }
            try {
                RosBridgeClient.publish("/app/phone", phone)
                Toast.makeText(this, "Phone sent: $phone", Toast.LENGTH_SHORT).show()
            } catch (t: Throwable) {
                Log.e(TAG, "Failed to publish phone", t)
                Toast.makeText(this, "Failed to send phone", Toast.LENGTH_SHORT).show()
            }
            finish()
        }
    }
}
