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
import com.example.deliverybot.net.RosBridgeClient

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

    private lateinit var ipEdit: EditText
    private lateinit var btnSave: Button

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

        // bind IP input and Save button (activity_main.xml)
        ipEdit = findViewById(R.id.ipEdit)
        btnSave = findViewById(R.id.btnSave)

        btnSave.setOnClickListener {
            val ipRaw = ipEdit.text.toString().trim().ifBlank { "10.42.0.1" }
            // build websocket URL; use ws://host:port (no /rosbridge)
            val url = when {
                ipRaw.startsWith("ws://") || ipRaw.startsWith("wss://") -> {
                    // if user provided scheme and port, keep it; if they omitted port add :9090
                    if (ipRaw.contains(":")) ipRaw else "$ipRaw:9090"
                }
                ipRaw.contains(":") -> "ws://$ipRaw" // user provided ip:port
                else -> "ws://$ipRaw:9090"
            }
            RosBridgeClient.connect(url)
            Toast.makeText(this, "Connecting to $url", Toast.LENGTH_SHORT).show()
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
