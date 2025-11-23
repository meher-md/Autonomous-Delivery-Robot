package com.example.deliverybot
import com.example.deliverybot.OrdersActivity
import com.example.deliverybot.ChatActivity
import android.view.View
import com.example.deliverybot.CameraActivity

import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.util.Log
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
    private lateinit var btnOrderHistory: Button
    private lateinit var btnSettings: Button
    // RTSP default (can be overridden when launching camera)
    private var rtspUrl: String = "rtsp://127.0.0.1:8554/stream"

    private lateinit var ipEdit: EditText
    private lateinit var btnSave: Button

    private val NOTIFICATION_CHANNEL_ID = "delivery_bot_channel"

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        
        // Apply Dark Mode
        val prefs = getSharedPreferences("app_prefs", Context.MODE_PRIVATE)
        val isDarkMode = prefs.getBoolean("dark_mode", true)
        if (isDarkMode) {
            androidx.appcompat.app.AppCompatDelegate.setDefaultNightMode(androidx.appcompat.app.AppCompatDelegate.MODE_NIGHT_YES)
        } else {
            androidx.appcompat.app.AppCompatDelegate.setDefaultNightMode(androidx.appcompat.app.AppCompatDelegate.MODE_NIGHT_NO)
        }

        setContentView(R.layout.activity_main)

        createNotificationChannel()

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

        // Load saved IP
        ipEdit.setText(Prefs.getIp(this))

        btnSave.setOnClickListener {
            val ipRaw = ipEdit.text.toString().trim().ifBlank { "10.42.0.1" }
            // Save IP
            Prefs.saveIp(this, ipRaw)

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
        btnOrderHistory = findViewById(R.id.btnOrderHistory)
        btnSettings = findViewById(R.id.btnSettings)

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
        btnOrderHistory.setOnClickListener {
            startActivity(Intent(this, OrdersActivity::class.java))
        }
        btnSettings.setOnClickListener {
            startActivity(Intent(this, SettingsActivity::class.java))
        }

        // Setup Notifications
        setupNotifications()

        if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.TIRAMISU) {
            if (checkSelfPermission(android.Manifest.permission.POST_NOTIFICATIONS) != android.content.pm.PackageManager.PERMISSION_GRANTED) {
                requestPermissions(arrayOf(android.Manifest.permission.POST_NOTIFICATIONS), 101)
            }
        }
    }

    private val connectionListener: (Boolean) -> Unit = { connected ->
        if (shouldNotify()) {
            val msg = if (connected) "Connected to Robot 🤖" else "Disconnected from Robot ❌"
            showNotification("Connection Status", msg)
        }
    }

    private fun setupNotifications() {
        // Connection listener
        RosBridgeClient.addConnectionListener(connectionListener)

        // Robot Status listener (e.g. arrival)
        // ...

        // Robot Status listener (e.g. arrival)
        // We need to subscribe. Note: This might duplicate subscriptions if we are not careful, 
        // but RosBridgeClient handles multiple callbacks for same topic.
        try {
            RosBridgeClient.subscribe("/app/goal_status") { msg ->
                // Check if message implies arrival. 
                // Assuming msg is a string status. Adjust logic if it's JSON.
                // Example statuses: "Arrived", "Moving", "Idle"
                if (shouldNotify()) {
                    // Normalize message
                    val lower = msg.lowercase()
                    if (lower.contains("arrived") || lower.contains("goal reached") || lower.contains("succeeded")) {
                        showNotification("Robot Update", "The robot has arrived! 🏁")
                    }
                }
            }
        } catch (_: Throwable) {}
    }

    private fun shouldNotify(): Boolean {
        val prefs = getSharedPreferences("app_prefs", Context.MODE_PRIVATE)
        return prefs.getBoolean("notifications_enabled", true)
    }

    private fun showNotification(title: String, content: String) {
        runOnUiThread {
            // Use Toast for immediate feedback as well
            Toast.makeText(this, "$title: $content", Toast.LENGTH_SHORT).show()
            
            val builder = androidx.core.app.NotificationCompat.Builder(this, NOTIFICATION_CHANNEL_ID)
                .setSmallIcon(android.R.drawable.ic_dialog_info) // Fallback icon
                .setContentTitle(title)
                .setContentText(content)
                .setPriority(androidx.core.app.NotificationCompat.PRIORITY_DEFAULT)
                .setAutoCancel(true)

            with(androidx.core.app.NotificationManagerCompat.from(this)) {
                // notificationId is a unique int for each notification that you must define
                try {
                    notify(System.currentTimeMillis().toInt(), builder.build())
                } catch (e: SecurityException) {
                    // Handle missing permission if needed (Android 13+)
                    Log.e("MainActivity", "Notification permission missing")
                }
            }
        }
    }

    private fun createNotificationChannel() {
        if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.O) {
            val name = "DeliveryBot Notifications"
            val descriptionText = "Notifications for robot status"
            val importance = android.app.NotificationManager.IMPORTANCE_DEFAULT
            val channel = android.app.NotificationChannel(NOTIFICATION_CHANNEL_ID, name, importance).apply {
                description = descriptionText
            }
            val notificationManager: android.app.NotificationManager =
                getSystemService(Context.NOTIFICATION_SERVICE) as android.app.NotificationManager
            notificationManager.createNotificationChannel(channel)
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        RosBridgeClient.removeConnectionListener(connectionListener)
    }
}
