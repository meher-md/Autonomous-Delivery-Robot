package com.example.deliverybot

import android.content.Intent
import android.os.Bundle
import android.widget.Button
import android.widget.EditText
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity

class OrdersActivity : AppCompatActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_orders)

        val orderId = findViewById<EditText>(R.id.etOrderId)
        val customer = findViewById<EditText>(R.id.etCustomer)
        val address = findViewById<EditText>(R.id.etAddress)
        val phone = findViewById<EditText>(R.id.etPhone)
        val note = findViewById<EditText>(R.id.etNote)

        findViewById<Button>(R.id.btnCreateLocal).setOnClickListener {
            Toast.makeText(this, "Saved locally ✔", Toast.LENGTH_SHORT).show()
        }

        findViewById<Button>(R.id.btnRequestQr).setOnClickListener {
            Toast.makeText(this, "Requesting QR from robot…", Toast.LENGTH_SHORT).show()
        }

        findViewById<Button>(R.id.btnShare).setOnClickListener {
            val text = "Order ${orderId.text} - ${customer.text}\n${address.text}\n${phone.text}\n${note.text}"
            val intent = Intent(Intent.ACTION_SEND).apply {
                type = "text/plain"
                putExtra(Intent.EXTRA_TEXT, text)
                setPackage("com.whatsapp")
            }
            startActivity(Intent.createChooser(intent, "Share"))
        }
    }
}
