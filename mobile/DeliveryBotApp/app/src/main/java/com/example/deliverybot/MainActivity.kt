package com.example.deliverybot

// Imports for core Android components
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Bundle
import android.util.Log
import android.view.View
import android.widget.Button
import android.widget.EditText
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity

// Imports for permission handling
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat

// Imports for other activities and RosBridge client
import com.example.deliverybot.OrdersActivity
import com.example.deliverybot.ChatActivity
import com.example.deliverybot.CameraActivity
import com.example.deliverybot.net.RosBridgeClient


/**
 * Helper object for saving and retrieving IP configuration.
 */
object Prefs {
    private const val PREFS_FILE = "app"
    private const val IP_KEY = "ip"
    // REVERTED: Changed default IP back to the standard team IP (10.42.0.1).
    // This IP must be used for sharing the code to avoid issues for other team members.
    private const val DEFAULT_IP = "ws://10.42.0.1:9090"

    fun saveIp(ctx: Context, ip: String) {
        ctx.getSharedPreferences(PREFS_FILE, Context.MODE_PRIVATE).edit()
            .putString(IP_KEY, ip).apply()
    }

    fun getIp(ctx: Context): String =
        ctx.getSharedPreferences(PREFS_FILE, Context.MODE_PRIVATE)
            .getString(IP_KEY, DEFAULT_IP) ?: DEFAULT_IP
}

/**
 * The main activity of the application, serving as the dashboard for navigation
 * and connection setup.
 */
class MainActivity : AppCompatActivity() {

    // UI buttons declared here
    private lateinit var btnOpenMap: Button
    private lateinit var btnOpenCamera: Button
    private lateinit var btnOpenChat: Button
    private lateinit var btnAddress: Button
    private lateinit var btnOrderHistory: Button
    private lateinit var btnSettings: Button
    private lateinit var btnChatbot: Button

    // RTSP default URL for camera streaming (can be overridden)
    private var rtspUrl: String = "rtsp://127.0.0.1:8554/stream"

    private lateinit var ipEdit: EditText
    private lateinit var btnSave: Button

    private val NOTIFICATION_CHANNEL_ID = "delivery_bot_channel"
    private val CAMERA_PERMISSION_REQUEST_CODE = 100
    private val POST_NOTIFICATIONS_REQUEST_CODE = 101

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // Apply Dark Mode preference
        val prefs = getSharedPreferences("app_prefs", Context.MODE_PRIVATE)
        val isDarkMode = prefs.getBoolean("dark_mode", true)
        if (isDarkMode) {
            androidx.appcompat.app.AppCompatDelegate.setDefaultNightMode(androidx.appcompat.app.AppCompatDelegate.MODE_NIGHT_YES)
        } else {
            androidx.appcompat.app.AppCompatDelegate.setDefaultNightMode(androidx.appcompat.app.AppCompatDelegate.MODE_NIGHT_NO)
        }

        setContentView(R.layout.activity_main)

        createNotificationChannel()

        /* WIRE_CHAT_ORDERS: Programmatically find and set listeners for chat/orders buttons */
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

        // Bind IP input and Save button
        ipEdit = findViewById(R.id.ipEdit)
        btnSave = findViewById(R.id.btnSave)

        // Load saved IP and display it
        ipEdit.setText(Prefs.getIp(this))

        // Save IP and attempt to connect to ROS bridge
        btnSave.setOnClickListener {
            // REVERTED: Fallback IP set back to the team standard (10.42.0.1)
            val ipRaw = ipEdit.text.toString().trim().ifBlank { "10.42.0.1:9090" }
            Prefs.saveIp(this, ipRaw)

            // Construct WebSocket URL
            val url = when {
                ipRaw.startsWith("ws://") -> {
                   val s = ipRaw.replace("ws://", "wss://")
                   if (s.contains(":")) s else "$s:9090"
                }
                ipRaw.startsWith("wss://") -> {
                    if (ipRaw.contains(":")) ipRaw else "$ipRaw:9090"
                }
                ipRaw.contains(":") -> "wss://$ipRaw"
                else -> "wss://$ipRaw:9090"
            }

            // Show connecting progress dialog
            val progress = android.app.ProgressDialog(this).apply {
                setMessage("Connecting to ROS Bridge...")
                setCancelable(false)
                show()
            }

            val wasConnected = RosBridgeClient.isConnected()
            var ignoreDisconnect = wasConnected

            var isHandled = false
            // Connection listener logic
            val listener = object : (Boolean) -> Unit {
                override fun invoke(connected: Boolean) {
                    if (isHandled) return

                    if (!connected && ignoreDisconnect) {
                        ignoreDisconnect = false
                        return
                    }

                    isHandled = true
                    runOnUiThread {
                        try { progress.dismiss() } catch(_: Throwable){}
                        RosBridgeClient.removeConnectionListener(this)
                        if (connected) {
                            Toast.makeText(this@MainActivity, "Connected to ROS: $url", Toast.LENGTH_SHORT).show()
                        } else {
                            Toast.makeText(this@MainActivity, "Connection failed. Scanning...", Toast.LENGTH_SHORT).show()
                            startActivity(Intent(this@MainActivity, ScanActivity::class.java))
                        }
                    }
                }
            }
            RosBridgeClient.addConnectionListener(listener)
            RosBridgeClient.connect(url)

            // Connection timeout handler
            android.os.Handler(android.os.Looper.getMainLooper()).postDelayed({
                if (!isHandled) {
                    isHandled = true
                    try { progress.dismiss() } catch(_: Throwable){}
                    RosBridgeClient.removeConnectionListener(listener)
                    Toast.makeText(this, "Connection timed out. Please check ROS Bridge.", Toast.LENGTH_SHORT).show()
                    startActivity(Intent(this, ScanActivity::class.java))
                }
            }, 5000) // Increased timeout to 5 seconds
        }

        // Bind navigation buttons
        btnOpenMap    = findViewById(R.id.btnMap)
        btnOpenCamera = findViewById(R.id.btnCamera)
        btnOpenChat   = findViewById(R.id.btnChat)
        btnAddress    = findViewById(R.id.btnAddress)
        btnOrderHistory = findViewById(R.id.btnOrderHistory)
        btnSettings = findViewById(R.id.btnSettings)
        btnChatbot = findViewById(R.id.btnChatbot)

        // CLICK HANDLERS

        // Check for CAMERA permission before opening MapActivity
        btnOpenMap.setOnClickListener {
            if (ContextCompat.checkSelfPermission(this, android.Manifest.permission.CAMERA)
                != PackageManager.PERMISSION_GRANTED) {
                // Permission not granted, request it
                ActivityCompat.requestPermissions(this,
                    arrayOf(android.Manifest.permission.CAMERA), CAMERA_PERMISSION_REQUEST_CODE)
            } else {
                // Permission already granted
                openMapActivity()
            }
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

        btnChatbot.setOnClickListener {
            startActivity(Intent(this, ChatbotActivity::class.java))
        }

        // Setup Notifications
        setupNotifications()

        // Request POST_NOTIFICATIONS permission on Android 13+ (TIRAMISU)
        if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.TIRAMISU) {
            if (checkSelfPermission(android.Manifest.permission.POST_NOTIFICATIONS)
                != android.content.pm.PackageManager.PERMISSION_GRANTED) {
                requestPermissions(
                    arrayOf(android.Manifest.permission.POST_NOTIFICATIONS),
                    POST_NOTIFICATIONS_REQUEST_CODE
                )
            }
        }
    }

    override fun onResume() {
        super.onResume()
        // Reload IP in the text field when activity resumes
        if (::ipEdit.isInitialized) {
            ipEdit.setText(Prefs.getIp(this))
        }
    }

    // Listener to handle ROS bridge connection status updates
    private val connectionListener: (Boolean) -> Unit = { connected ->
        if (shouldNotify()) {
            val msg = if (connected) "Connected to Robot 🤖" else "Disconnected from Robot ❌"
            showNotification("ROS Connection Status", msg)
        }
    }

    // Sets up listeners for robot status notifications
    private fun setupNotifications() {
        // Connection listener
        RosBridgeClient.addConnectionListener(connectionListener)

        // Robot Status listener (e.g. arrival)
        try {
            // Subscribe to the goal status topic
            RosBridgeClient.subscribe("/app/goal_status") { msg ->
                if (shouldNotify()) {
                    // Normalize message for checking
                    val lower = msg.lowercase()
                    if (lower.contains("arrived") ||
                        lower.contains("goal reached") ||
                        lower.contains("succeeded")) {
                        showNotification("Robot Update", "The robot has arrived! 🏁")
                    }
                }
            }
        } catch (_: Throwable) {
            Log.w("MainActivity", "Failed to subscribe to goal status topic")
        }
    }

    // Checks user preference for enabling notifications
    private fun shouldNotify(): Boolean {
        val prefs = getSharedPreferences("app_prefs", Context.MODE_PRIVATE)
        return prefs.getBoolean("notifications_enabled", true)
    }

    // Displays a notification and a toast message
    private fun showNotification(title: String, content: String) {
        runOnUiThread {
            // Use Toast for immediate feedback
            Toast.makeText(this, "$title: $content", Toast.LENGTH_SHORT).show()

            // Build and display the notification
            val builder = androidx.core.app.NotificationCompat.Builder(this, NOTIFICATION_CHANNEL_ID)
                .setSmallIcon(android.R.drawable.ic_dialog_info)
                .setContentTitle(title)
                .setContentText(content)
                .setPriority(androidx.core.app.NotificationCompat.PRIORITY_DEFAULT)
                .setAutoCancel(true)

            with(androidx.core.app.NotificationManagerCompat.from(this)) {
                try {
                    notify(System.currentTimeMillis().toInt(), builder.build())
                } catch (e: SecurityException) {
                    Log.e("MainActivity", "Notification permission missing: ${e.message}")
                }
            }
        }
    }

    // Creates the notification channel for Android 8.0 (Oreo) and above
    private fun createNotificationChannel() {
        if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.O) {
            val name = "DeliveryBot Notifications"
            val descriptionText = "Notifications for robot status updates"
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
        // Clean up connection listener on activity destruction
        RosBridgeClient.removeConnectionListener(connectionListener)
    }

    /**
     * Handles the result of permission requests (e.g., Camera).
     */
    override fun onRequestPermissionsResult(
        requestCode: Int,
        permissions: Array<out String>,
        grantResults: IntArray
    ) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)

        when (requestCode) {
            CAMERA_PERMISSION_REQUEST_CODE -> {
                if (grantResults.isNotEmpty() &&
                    grantResults[0] == PackageManager.PERMISSION_GRANTED) {
                    // Permission granted, proceed to open the map
                    openMapActivity()
                } else {
                    // Permission denied
                    Toast.makeText(
                        this,
                        "Camera permission is required to use the map.",
                        Toast.LENGTH_LONG
                    ).show()
                }
            }
            POST_NOTIFICATIONS_REQUEST_CODE -> {
                if (grantResults.isNotEmpty() &&
                    grantResults[0] == PackageManager.PERMISSION_GRANTED) {
                    Log.d("MainActivity", "Notification permission granted")
                } else {
                    Log.d("MainActivity", "Notification permission denied")
                }
            }
        }
    }

    /**
     * Starts the MapActivity using an explicit intent.
     */
    private fun openMapActivity() {
        val intent = Intent(this, MapActivity::class.java)
        startActivity(intent)
    }
}