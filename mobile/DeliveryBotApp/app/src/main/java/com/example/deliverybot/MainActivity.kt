package com.example.deliverybot

import android.annotation.SuppressLint
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Bundle
import android.util.Log
import android.view.GestureDetector
import android.view.MotionEvent
import android.view.View
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Button
import android.widget.EditText
import android.widget.FrameLayout
import android.widget.ImageButton
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.cardview.widget.CardView
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import com.example.deliverybot.net.RosBridgeClient

// Import your other activities
// (Ensure these classes exist: MapActivity, OrdersActivity, ChatActivity, SettingsActivity, ChatbotActivity, CameraActivity)
// If manual control is basically the "Chat" activity or new one, map accordingly.

object Prefs {
    private const val PREFS_FILE = "app"
    private const val IP_KEY = "ip"
    private const val DEFAULT_IP = "ws://10.42.0.1:9090"

    fun saveIp(ctx: Context, ip: String) {
        ctx.getSharedPreferences(PREFS_FILE, Context.MODE_PRIVATE).edit()
            .putString(IP_KEY, ip).apply()
    }

    fun getIp(ctx: Context): String =
        ctx.getSharedPreferences(PREFS_FILE, Context.MODE_PRIVATE)
            .getString(IP_KEY, DEFAULT_IP) ?: DEFAULT_IP
}

class MainActivity : AppCompatActivity() {

    // UI Elements
    private lateinit var btnConnect: ImageButton
    private lateinit var btnSettings: ImageButton
    private lateinit var statusText: TextView
    
    // Hero Section
    private lateinit var heroContainer: FrameLayout
    private lateinit var webViewCamera: WebView
    private lateinit var webViewDashboard: WebView
    
    // Grid Cards
    private lateinit var cardMap: View
    private lateinit var cardDashboard: View
    private lateinit var cardChatbot: View
    private lateinit var cardManual: View
    
    // Bottom Action
    private lateinit var btnCreateOrder: Button

    private val NOTIFICATION_CHANNEL_ID = "delivery_bot_channel"
    private val CAMERA_PERMISSION_REQUEST_CODE = 100
    private val POST_NOTIFICATIONS_REQUEST_CODE = 101
    
    // State
    private var isDashboardVisible = false
    private var robotIp = "10.42.0.1" // Extracted from WS URL for HTTP calls
    
    // Gesture Detector for Swipes
    private lateinit var gestureDetector: GestureDetector

    @SuppressLint("SetJavaScriptEnabled", "ClickableViewAccessibility")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        
        // Force Dark Mode
        androidx.appcompat.app.AppCompatDelegate.setDefaultNightMode(androidx.appcompat.app.AppCompatDelegate.MODE_NIGHT_YES)
        setContentView(R.layout.activity_main)

        // Initialize UI
        btnConnect = findViewById(R.id.btnConnect)
        btnSettings = findViewById(R.id.btnSettings)
        statusText = findViewById(R.id.statusText)
        
        heroContainer = findViewById(R.id.heroContainer)
        webViewCamera = findViewById(R.id.webViewCamera)
        webViewDashboard = findViewById(R.id.webViewDashboard)
        
        cardMap = findViewById(R.id.cardMap)
        cardDashboard = findViewById(R.id.cardDashboard)
        cardChatbot = findViewById(R.id.cardChatbot)
        cardManual = findViewById(R.id.cardManual)
        
        btnCreateOrder = findViewById(R.id.btnCreateOrder)

        // Extract IP base
        val savedWs = Prefs.getIp(this)
        robotIp = extractIp(savedWs)
        updateStatusText(false)

        // Setup WebViews
        setupWebViews()
        
        // Setup Gestures
        gestureDetector = GestureDetector(this, object : GestureDetector.SimpleOnGestureListener() {
            override fun onFling(e1: MotionEvent?, e2: MotionEvent, velocityX: Float, velocityY: Float): Boolean {
                if (e1 == null) return false
                val diffX = e2.x - e1.x
                if (Math.abs(diffX) > 100 && Math.abs(velocityX) > 100) {
                    if (diffX > 0) {
                        // Swipe Right -> Show Camera
                        showDashboard(false)
                    } else {
                        // Swipe Left -> Show Dashboard
                        showDashboard(true)
                    }
                    return true
                }
                return false
            }
        })
        
        // Attach Gesture to Hero Container
        heroContainer.setOnTouchListener { _, event -> 
            gestureDetector.onTouchEvent(event)
            true 
        }

        // --- BUTTON LISTENERS ---

        btnConnect.setOnClickListener {
            connectToRobot()
        }

        btnSettings.setOnClickListener {
            startActivity(Intent(this, SettingsActivity::class.java))
        }

        // GRID ACTIONS
        cardMap.setOnClickListener {
             if (ContextCompat.checkSelfPermission(this, android.Manifest.permission.CAMERA)
                != PackageManager.PERMISSION_GRANTED) {
                ActivityCompat.requestPermissions(this,
                    arrayOf(android.Manifest.permission.CAMERA), CAMERA_PERMISSION_REQUEST_CODE)
            } else {
                startActivity(Intent(this, MapActivity::class.java))
            }
        }

        cardDashboard.setOnClickListener {
            // Toggle Dashboard in Hero View or open Full Activity?
            // User said: "When swipe... show dashboard". 
            // Button can just force show it.
            showDashboard(!isDashboardVisible)
        }

        cardChatbot.setOnClickListener {
             // Assuming ChatbotActivity exists
             startActivity(Intent(this, ChatbotActivity::class.java))
        }

        cardManual.setOnClickListener {
            // Manual Control -> likely ChatActivity or Joystick
            startActivity(Intent(this, ChatActivity::class.java))
        }
        
        btnCreateOrder.setOnClickListener {
            startActivity(Intent(this, AddressActivity::class.java)) // or OrdersActivity
        }

        // Notifications
        createNotificationChannel()
        setupNotifications()
        
        // Auto-connect on start if desired?
        // connectToRobot() 
    }
    
    @SuppressLint("SetJavaScriptEnabled")
    private fun setupWebViews() {
        // Camera (MJPEG Stream is usually handled by raw Socket or dedicated View, 
        // but WebView can render MJPEG stream URL if supported, or simple image refresh)
        // Ideally use a specialized MjpegView, but User asked for WebView structure.
        // Let's assume we load the browser-friendly stream URL.
        webViewCamera.settings.javaScriptEnabled = true
        webViewCamera.settings.loadWithOverviewMode = true
        webViewCamera.settings.useWideViewPort = true
        webViewCamera.webViewClient = WebViewClient()
        // Default URL (can be updated on connect)
        // loading...
        
        // Dashboard (Streamlit)
        webViewDashboard.settings.javaScriptEnabled = true
        webViewDashboard.settings.domStorageEnabled = true
        webViewDashboard.webViewClient = WebViewClient()
    }
    
    private fun loadHeroContent() {
        // Load Camera
        val camUrl = "http://$robotIp:8000/stream.mjpg" // Example MJPEG server
        // OR use the RTSP url passed to VLC? 
        // For simplicity in WebView, we need HTTP MJPEG. 
        // If not available, we might need the custom Native Camera View. 
        // Let's try loading the stream URL or a placeholder.
        // NOTE: Standard Android WebView doesn't support RTSP. 
        // We will assume 'web_video_server' is running on port 8080 or similar.
        val webVideoUrl = "http://$robotIp:8080/stream?topic=/camera/image_raw&type=ros_compressed"
        webViewCamera.loadUrl(webVideoUrl)
        
        // Load Dashboard
        val dashboardUrl = "http://$robotIp:8501"
        webViewDashboard.loadUrl(dashboardUrl)
    }
    
    private fun showDashboard(show: Boolean) {
        isDashboardVisible = show
        if (show) {
            webViewCamera.visibility = View.GONE
            webViewDashboard.visibility = View.VISIBLE
            findViewById<TextView>(R.id.heroTitle).text = "Dashboard (Swipe ➝ Camera)"
        } else {
            webViewDashboard.visibility = View.GONE
            webViewCamera.visibility = View.VISIBLE
             findViewById<TextView>(R.id.heroTitle).text = "Dashboard (Swipe ➝ Camera)"
        }
    }
    
    private fun extractIp(wsUrl: String): String {
        // ws://10.42.0.1:9090 -> 10.42.0.1
        return wsUrl.replace("ws://", "").replace("wss://", "").split(":")[0]
    }

    private fun updateStatusText(connected: Boolean) {
        runOnUiThread {
            // val statusIcon = if (connected) "🟢" else "🔴"
            // val statusWord = if (connected) "Online" else "Offline"
            // statusText.text = "$statusIcon $statusWord | $robotIp"
            
            // As per latest request:
            val statusIcon = if (connected) "🟢" else "🔴"
            val statusWord = if (connected) "Online" else "Offline"
            statusText.text = "$statusIcon $statusWord | $robotIp"
            
            // Tint Connect button
            val color = if (connected) R.color.status_online else R.color.status_offline
            btnConnect.setColorFilter(ContextCompat.getColor(this, color))
        }
    }

    private fun connectToRobot() {
        // Get IP from Prefs
        val wsUrl = Prefs.getIp(this)
        robotIp = extractIp(wsUrl)
        
        Toast.makeText(this, "Connecting to $wsUrl...", Toast.LENGTH_SHORT).show()
        
        // Connect logic
        RosBridgeClient.connect(wsUrl)
        
        // Listeners
        RosBridgeClient.addConnectionListener(object : (Boolean) -> Unit {
            override fun invoke(connected: Boolean) {
                updateStatusText(connected)
                if (connected) {
                    runOnUiThread {
                        Toast.makeText(this@MainActivity, "Connected! 🚀", Toast.LENGTH_SHORT).show()
                        loadHeroContent() // Start streams
                        RosBridgeClient.removeConnectionListener(this)
                    }
                } else {
                     // FAILED!
                     runOnUiThread {
                        Toast.makeText(this@MainActivity, "Connection failed. Scanning...", Toast.LENGTH_SHORT).show()
                        // Move to Scan Activity
                        RosBridgeClient.removeConnectionListener(this)
                        startActivity(Intent(this@MainActivity, ScanActivity::class.java))
                     }
                }
            }
        })
        
        // Timeout handler
        android.os.Handler(android.os.Looper.getMainLooper()).postDelayed({
             if (!RosBridgeClient.isConnected()) {
                 Toast.makeText(this, "Timeout. Scanning...", Toast.LENGTH_SHORT).show()
                 startActivity(Intent(this, ScanActivity::class.java))
             }
        }, 3000)
    }

    // ... (Keep existing notification and permission logic) ...
    
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
        try {
            RosBridgeClient.subscribe("/app/goal_status") { msg ->
                if (shouldNotify()) {
                    val lower = msg.lowercase()
                    if (lower.contains("arrived") || lower.contains("goal reached") || lower.contains("succeeded")) {
                        showNotification("Robot Update", "The robot has arrived! 🏁")
                    }
                }
            }
        } catch (_: Throwable) {
            Log.w("MainActivity", "Failed to subscribe to goal status topic")
        }
    }
    
    private fun shouldNotify(): Boolean {
        val prefs = getSharedPreferences("app_prefs", Context.MODE_PRIVATE)
        return prefs.getBoolean("notifications_enabled", true)
    }

    private fun showNotification(title: String, content: String) {
        runOnUiThread {
            Toast.makeText(this, "$title: $content", Toast.LENGTH_SHORT).show()
            
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
        RosBridgeClient.removeConnectionListener(connectionListener)
    }

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
                    openMapActivity()
                } else {
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

    private fun openMapActivity() {
        val intent = Intent(this, MapActivity::class.java)
        startActivity(intent)
    }
}