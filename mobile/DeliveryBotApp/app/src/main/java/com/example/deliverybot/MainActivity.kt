package com.example.deliverybot
import com.example.deliverybot.OrdersActivity
import com.example.deliverybot.ChatActivity
import android.view.View
import com.example.deliverybot.CameraActivity

import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.widget.Button
import android.widget.EditText
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity

object Prefs {
    fun saveIp(ctx: Context, ip: String) {
        ctx.getSharedPreferences("app", Context.MODE_PRIVATE).edit()
            .putString("ip", ip).apply()
    }
    fun getIp(ctx: Context): String =
        ctx.getSharedPreferences("app", Context.MODE_PRIVATE)
            .getString("ip", "10.42.0.1") ?: "10.42.0.1"
}

class MainActivity : AppCompatActivity() {

    // UI buttons added/declared here
    private lateinit var btnOpenMap: Button
    private lateinit var btnOpenCamera: Button
    private lateinit var btnOpenChat: Button
    private lateinit var btnAddress: Button
    private lateinit var btnPhone: Button
    // RTSP default (can be overridden when launching camera)
    private var rtspUrl: String = "rtsp://127.0.0.1:8554/stream"

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        /* WIRE_CHAT_ORDERS */
        try {
            val chatIds = intArrayOf(
                resources.getIdentifier("btnOpenChat", "id", packageName),
                resources.getIdentifier("openChatButton", "id", packageName),
                resources.getIdentifier("btnChat", "id", packageName)
            ).filter { it != 0 }
            for (id in chatIds) {
                (findViewById<View>(id) as? Button)?.setOnClickListener {
                    startActivity(Intent(this, ChatActivity::class.java))
                }
            }
            val orderIds = intArrayOf(
                resources.getIdentifier("btnOrders", "id", packageName),
                resources.getIdentifier("openOrdersButton", "id", packageName),
                resources.getIdentifier("btnOpenOrders", "id", packageName)
            ).filter { it != 0 }
            for (id in orderIds) {
                (findViewById<View>(id) as? Button)?.setOnClickListener {
                    startActivity(Intent(this, OrdersActivity::class.java))
                }
            }
        } catch (_: Throwable) {}
        /* /WIRE_CHAT_ORDERS */

        val ipEdit = findViewById<EditText>(R.id.ipEdit)
        ipEdit.setText(Prefs.getIp(this))

        findViewById<Button>(R.id.btnSave).setOnClickListener {
            val ip = ipEdit.text.toString().trim()
            Prefs.saveIp(this, ip)
            Toast.makeText(this, "Saved IP: $ip", Toast.LENGTH_SHORT).show()
        }

        // bind new buttons (and existing ones if not already bound)
        btnOpenMap    = findViewById(R.id.btnMap)
        btnOpenCamera = findViewById(R.id.btnCamera)
        btnOpenChat   = findViewById(R.id.btnChat)
        btnAddress    = findViewById(R.id.btnAddress)
        btnPhone      = findViewById(R.id.btnPhone)

        // click handlers
        btnOpenMap.setOnClickListener {
            startActivity(Intent(this, MapActivity::class.java))
        }
        btnOpenCamera.setOnClickListener {
            startActivity(Intent(this, CameraActivity::class.java).putExtra("rtspUrl", rtspUrl))
        }
        btnOpenChat.setOnClickListener {
            startActivity(Intent(this, ChatActivity::class.java))
        }
        btnAddress.setOnClickListener {
            startActivity(Intent(this, AddressActivity::class.java))
        }
        btnPhone.setOnClickListener {
            startActivity(Intent(this, PhoneActivity::class.java))
        }
    }
}
