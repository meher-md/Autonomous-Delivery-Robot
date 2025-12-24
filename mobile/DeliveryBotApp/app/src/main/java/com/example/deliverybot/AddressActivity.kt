package com.example.deliverybot

import android.app.AlertDialog
import android.content.ActivityNotFoundException
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.BitmapFactory
import android.net.Uri
import android.util.Base64
import androidx.core.content.FileProvider
import java.io.File
import android.os.Bundle
import android.util.Log
import android.view.View
import android.widget.*
import androidx.appcompat.app.AppCompatActivity
import com.example.deliverybot.net.RosBridgeClient

class AddressActivity : AppCompatActivity() {
    private val TAG = "DeliveryBot/Address"
    private var selectedAddress: String? = null
    private var generatedQrPath: String? = null
    // map to lock QR per destination
    private val generatedQrByAddress: MutableMap<String, String> = mutableMapOf()

    // Callbacks for ROS subscriptions
    private var statusCallback: ((String) -> Unit)? = null
    private var qrCallback: ((String) -> Unit)? = null

    // UI
    private lateinit var rgLocations: RadioGroup
    private lateinit var btnPlaceOrder: Button
    private lateinit var btnOrderHistory: Button
    private lateinit var btnEditDestinations: ImageButton
    private lateinit var qrImageView: ImageView
    private lateinit var qrPlaceholder: TextView
    private lateinit var btnShareWhatsApp: Button
    private lateinit var tvStatus: TextView

    private val destinations = mutableListOf<String>()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_address)

        rgLocations = findViewById(R.id.rgLocations)
        btnPlaceOrder = findViewById(R.id.btnPlaceOrder)
        btnOrderHistory = findViewById(R.id.btnOrderHistory)
        btnEditDestinations = findViewById(R.id.btnEditDestinations)
        tvStatus = findViewById(R.id.tvStatus)

        // QR UI
        qrImageView = findViewById(R.id.qrImage)
        qrPlaceholder = findViewById(R.id.qrPlaceholder)
        btnShareWhatsApp = findViewById(R.id.btnShareWhatsApp)
        btnShareWhatsApp.isEnabled = false

        loadDestinations()
        refreshDestinations()

        btnEditDestinations.setOnClickListener {
            showEditDestinationsDialog()
        }

        // Subscribe to robot feedback (optional)
        try {
            statusCallback = { msg ->
                runOnUiThread { tvStatus.text = "Robot: $msg" }
            }
            RosBridgeClient.subscribe("/app/goal_status", statusCallback!!)
        } catch (t: Throwable) {
            Log.e(TAG, "subscribe failed", t)
        }

        btnPlaceOrder.setOnClickListener {
            val checkedId = rgLocations.checkedRadioButtonId
            if (checkedId == -1) {
                Toast.makeText(this, "Please select a destination", Toast.LENGTH_SHORT).show()
                return@setOnClickListener
            }

            val rb = findViewById<RadioButton>(checkedId)
            val destination = rb.text.toString()
            selectedAddress = destination

            if (!RosBridgeClient.isConnected()) {
                showAlert("Not connected", "Not connected to robot. Press Save / Connect first.")
                return@setOnClickListener
            }

            // 1. Publish Goal
            try {
                RosBridgeClient.publish("/app/goal_name", destination)
                tvStatus.text = "Sent: $destination"
                Toast.makeText(this, "Order placed for $destination", Toast.LENGTH_SHORT).show()
                saveOrderToHistory(destination)
            } catch (t: Throwable) {
                Log.e(TAG, "publish failed", t)
                showAlert("Send failed", "Failed to send goal to robot.")
                return@setOnClickListener
            }

            // 2. Generate QR (or reuse)
            generateQrFor(destination)
        }

        btnOrderHistory.setOnClickListener {
            startActivity(Intent(this, OrdersActivity::class.java))
        }

        setupQrSubscription()
        setupShareButton()
    }

    private fun loadDestinations() {
        val prefs = getSharedPreferences("app_prefs", MODE_PRIVATE)
        if (prefs.contains("saved_destinations")) {
            val set = prefs.getStringSet("saved_destinations", emptySet()) ?: emptySet()
            destinations.clear()
            destinations.addAll(set.sorted())
        } else {
            val oldCustom = prefs.getStringSet("custom_destinations", emptySet()) ?: emptySet()
            destinations.clear()
            destinations.addAll(listOf("Lobby", "Library", "Cafeteria", "Lab"))
            destinations.addAll(oldCustom)
            val unique = destinations.toSet().toList().sorted()
            destinations.clear()
            destinations.addAll(unique)
            saveDestinations()
        }
    }

    private fun saveDestinations() {
        val prefs = getSharedPreferences("app_prefs", MODE_PRIVATE)
        prefs.edit().putStringSet("saved_destinations", destinations.toSet()).apply()
    }

    private fun refreshDestinations() {
        rgLocations.removeAllViews()
        
        for (dest in destinations) {
            val rb = RadioButton(this)
            rb.text = dest
            rb.textSize = 18f
            rb.setTextColor(androidx.core.content.ContextCompat.getColor(this, R.color.text_primary))
            rb.buttonTintList = android.content.res.ColorStateList.valueOf(android.graphics.Color.parseColor("#C9B6FF"))
            val params = RadioGroup.LayoutParams(RadioGroup.LayoutParams.WRAP_CONTENT, RadioGroup.LayoutParams.WRAP_CONTENT)
            params.setMargins(0, 0, 0, 20)
            rb.layoutParams = params
            rgLocations.addView(rb)
        }
    }

    private fun showEditDestinationsDialog() {
        val builder = AlertDialog.Builder(this)
        builder.setTitle("Edit Destinations")

        val layout = LinearLayout(this)
        layout.orientation = LinearLayout.VERTICAL
        layout.setPadding(50, 50, 50, 50)

        val input = EditText(this)
        input.hint = "Add new destination"
        layout.addView(input)

        // List of destinations to remove
        val scrollView = ScrollView(this)
        val listLayout = LinearLayout(this)
        listLayout.orientation = LinearLayout.VERTICAL
        
        for (dest in destinations) {
            val row = LinearLayout(this)
            row.orientation = LinearLayout.HORIZONTAL
            
            val tv = TextView(this)
            tv.text = dest
            tv.textSize = 16f
            tv.setPadding(0, 20, 20, 20)
            
            val btnRemove = Button(this)
            btnRemove.text = "Remove"
            btnRemove.setOnClickListener {
                destinations.remove(dest)
                saveDestinations()
                refreshDestinations()
                Toast.makeText(this, "Removed $dest", Toast.LENGTH_SHORT).show()
            }
            
            row.addView(tv)
            row.addView(btnRemove)
            listLayout.addView(row)
        }
        scrollView.addView(listLayout)
        layout.addView(scrollView)

        builder.setView(layout)

        builder.setPositiveButton("Add") { _, _ ->
            val newDest = input.text.toString().trim()
            if (newDest.isNotBlank()) {
                if (destinations.contains(newDest)) {
                    Toast.makeText(this, "Destination already exists", Toast.LENGTH_SHORT).show()
                } else {
                    destinations.add(newDest)
                    saveDestinations()
                    refreshDestinations()
                    Toast.makeText(this, "Added $newDest", Toast.LENGTH_SHORT).show()
                }
            }
        }
        builder.setNegativeButton("Close", null)
        builder.show()
    }

    private fun generateQrFor(addr: String) {
        // If QR already generated for this destination, reuse it (do not request new)
        generatedQrByAddress[addr]?.let { existingPath ->
            val bmp = try { BitmapFactory.decodeFile(existingPath) } catch (_: Exception) { null }
            if (bmp != null) {
                runOnUiThread {
                    qrPlaceholder.visibility = View.GONE
                    qrImageView.setImageBitmap(bmp)
                    btnShareWhatsApp.isEnabled = true
                    Toast.makeText(this, "Using cached QR for $addr", Toast.LENGTH_SHORT).show()
                }
                return
            }
        }

        // request generation
        try {
            val req = org.json.JSONObject()
            req.put("address", addr)
            req.put("timestamp", System.currentTimeMillis())
            RosBridgeClient.publish("/app/qr/generate", req.toString())
            Toast.makeText(this, "QR generation requested...", Toast.LENGTH_SHORT).show()
        } catch (ex: Throwable) {
            Log.e(TAG, "QR request failed", ex)
            showAlert("Error", "Failed to request QR generation.")
        }
    }

    private fun setupQrSubscription() {
        // Subscribe to receive generated QR (robust parsing of rosbridge wrapper or direct JSON)
        try {
            qrCallback = { raw ->
                try {
                    // raw may be a rosbridge wrapper JSON (with 'msg'->'data') or the direct string produced by node
                    var b64 = ""
                    val top = org.json.JSONObject(raw)
                    // case: rosbridge wrapper with msg.data = "<json string>"
                    if (top.has("msg")) {
                        val msgObj = top.optJSONObject("msg")
                        if (msgObj != null && msgObj.has("data")) {
                            val inner = msgObj.optString("data", "")
                            // inner might be JSON with qr_b64_png or might be the direct JSON resp
                            val innerJson = try {
                                org.json.JSONObject(inner)
                            } catch (_: Exception) {
                                null
                            }
                            if (innerJson != null) {
                                b64 = innerJson.optString("qr_b64_png", "")
                            } else {
                                // maybe inner itself is base64 (unlikely) - fallback
                                b64 = inner
                            }
                        }
                    } else if (top.has("qr_b64_png")) {
                        b64 = top.optString("qr_b64_png", "")
                    } else if (top.has("data")) {
                        // some nodes publish { "data": "<json>" }
                        val maybe = top.optString("data", "")
                        val j = try { org.json.JSONObject(maybe) } catch (_: Exception){ null }
                        if (j != null) b64 = j.optString("qr_b64_png", "")
                    }

                    if (b64.isBlank()) {
                        Log.w(TAG, "No qr_b64_png found in message: $raw")
                    } else {
                        val bytes = Base64.decode(b64, Base64.DEFAULT)
                        val bmp = BitmapFactory.decodeByteArray(bytes, 0, bytes.size)

                        // try to extract an address from the incoming message so we can lock the QR to it
                        var payloadAddress: String? = null
                        try {
                            val topJson = org.json.JSONObject(raw)
                            val candidate = when {
                                topJson.has("msg") -> topJson.optJSONObject("msg")?.optString("data", null)
                                topJson.has("data") -> topJson.optString("data", null)
                                else -> raw
                            }
                            val candidateJson = try { if (candidate != null) org.json.JSONObject(candidate) else null } catch (_: Exception) { null }
                            if (candidateJson != null) {
                                // prefer payload.address or address fields if present
                                val payloadObj = candidateJson.optJSONObject("payload")
                                if (payloadObj != null) payloadAddress = payloadObj.optString("address", null)
                                if (payloadAddress == null && candidateJson.has("address")) payloadAddress = candidateJson.optString("address", null)
                            }
                        } catch (_: Exception) { /* ignore parsing failures */ }

                        // Save to external cache (prefer externalCacheDir so some choosers don't remove it)
                        val baseDir = externalCacheDir ?: cacheDir
                        val qrFile = File(baseDir, "qr_${System.currentTimeMillis()}.png")
                        qrFile.outputStream().use { out -> bmp.compress(android.graphics.Bitmap.CompressFormat.PNG, 100, out) }
                        generatedQrPath = qrFile.absolutePath

                        // Tie QR to destination (payloadAddress) if available, else to current selectedAddress
                        val key = payloadAddress ?: selectedAddress
                        if (key != null) {
                            generatedQrByAddress[key] = qrFile.absolutePath
                            // Update history with this QR path
                            updateOrderHistoryWithQr(key, qrFile.absolutePath)
                        }

                        runOnUiThread {
                            qrPlaceholder.visibility = View.GONE
                            qrImageView.setImageBitmap(bmp)
                            btnShareWhatsApp.isEnabled = true
                            Toast.makeText(this@AddressActivity, "QR received and displayed", Toast.LENGTH_SHORT).show()
                        }
                    }
                } catch (e: Exception) {
                    Log.e(TAG, "Failed to handle /app/qr/image: ${e.message}", e)
                    runOnUiThread { showAlert("QR Error", "Failed to process QR image.") }
                }
            }
            RosBridgeClient.subscribe("/app/qr/image", qrCallback!!)
        } catch (t: Throwable) {
            Log.e(TAG, "subscribe /app/qr/image failed", t)
        }
    }

    private fun setupShareButton() {
        // Share button: generic chooser (replaces WhatsApp-only logic)
        btnShareWhatsApp.setOnClickListener {
            val path = generatedQrPath
            if (path.isNullOrBlank()) {
                showAlert("No QR", "No QR code available to share. Generate one first.")
                return@setOnClickListener
            }
            val qrFile = File(path)
            if (!qrFile.exists()) {
                showAlert("Missing file", "QR file missing from cache.")
                return@setOnClickListener
            }

            // Try to determine a valid FileProvider authority declared in the manifest
            val discoveredAuth = findFileProviderAuthority()
            val authoritiesToTry = mutableListOf<String>()
            discoveredAuth?.let { authoritiesToTry.add(it) }
            authoritiesToTry.add("${packageName}.provider")
            authoritiesToTry.add("${packageName}.fileprovider")

            var uri: Uri? = null
            var lastEx: Exception? = null
            val availableAuthorities = mutableListOf<String>()

            for (auth in authoritiesToTry) {
                try {
                    uri = FileProvider.getUriForFile(this, auth, qrFile)
                    lastEx = null
                    Log.i(TAG, "FileProvider success with authority=$auth")
                    break
                } catch (ex: Exception) {
                    lastEx = ex
                    Log.w(TAG, "FileProvider.getUriForFile failed for authority=$auth: ${ex.message}")
                }
            }

            if (uri == null) {
                showAlert("Share failed", "Failed to get file URI: ${lastEx?.message ?: "unknown"}")
                return@setOnClickListener
            }

            // Build generic share intent
            val sendIntent = Intent(Intent.ACTION_SEND).apply {
                type = "image/png"
                putExtra(Intent.EXTRA_STREAM, uri)
                addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            }

            // Grant URI permission to all resolved handlers (safer on some OEMs)
            try {
                val pm = packageManager
                val res = pm.queryIntentActivities(sendIntent, PackageManager.MATCH_DEFAULT_ONLY)
                for (ri in res) {
                    try { grantUriPermission(ri.activityInfo.packageName, uri, Intent.FLAG_GRANT_READ_URI_PERMISSION) } catch (_: Exception) {}
                }
            } catch (ex: Exception) {
                Log.w(TAG, "Failed to grant uri permission to all handlers: ${ex.message}")
            }

            // Launch chooser so user can pick any app
            try {
                val chooser = Intent.createChooser(sendIntent, "Share QR")
                startActivity(chooser)
            } catch (ex: Exception) {
                Log.e(TAG, "Share failed", ex)
                showAlert("Share failed", "Failed to open share chooser: ${ex.message}")
            }
        }
    }

    private fun saveOrderToHistory(destination: String) {
        val prefs = getSharedPreferences("app_prefs", MODE_PRIVATE)
        val history = prefs.getString("order_history", "") ?: ""
        val timestamp = java.text.SimpleDateFormat("yyyy-MM-dd HH:mm:ss", java.util.Locale.getDefault()).format(java.util.Date())
        // Store QR path if available (it might be null if not generated yet, but usually we generate it right after)
        // Actually, we generate it asynchronously. So at this point it might be null.
        // However, we can try to find it in our map or just use empty string.
        // Better: We should probably save it when we generate it? 
        // But simpler: just save what we have. If we generate it later, we can't easily update the history string without parsing it all.
        // Let's just save the path if we have it. If not, we might miss it for this order.
        // Wait, the user flow is: Select Dest -> Place Order -> (Publish Goal & Save History & Request QR).
        // So at this exact moment, we don't have the QR path yet (it comes from callback).
        // But we do have logic to reuse existing QR.
        // Let's try to get it from the map.
        val qrPath = generatedQrByAddress[destination] ?: ""
        
        val newEntry = "$timestamp|$destination|$qrPath"
        val newHistory = if (history.isBlank()) newEntry else "$history;$newEntry"
        prefs.edit().putString("order_history", newHistory).apply()
    }

    private fun updateOrderHistoryWithQr(destination: String, path: String) {
        val prefs = getSharedPreferences("app_prefs", MODE_PRIVATE)
        val history = prefs.getString("order_history", "") ?: ""
        if (history.isBlank()) return

        // Split, find most recent entry for this destination that doesn't have a path yet (or just update the most recent one)
        // Format: time|dest|path
        val items = history.split(";").toMutableList()
        
        // Iterate backwards to find the latest order for this destination
        for (i in items.indices.reversed()) {
            val parts = items[i].split("|")
            if (parts.size >= 2) {
                val dest = parts[1]
                if (dest == destination) {
                    // Update this entry
                    val timestamp = parts[0]
                    // Reconstruct
                    val newEntry = "$timestamp|$dest|$path"
                    items[i] = newEntry
                    break // Only update the most recent one
                }
            }
        }
        
        // Save back
        val newHistory = items.joinToString(";")
        prefs.edit().putString("order_history", newHistory).apply()
    }

    // Helper: show a simple alert dialog
    private fun showAlert(title: String, message: String) {
        runOnUiThread {
            AlertDialog.Builder(this)
                .setTitle(title)
                .setMessage(message)
                .setPositiveButton("OK", null)
                .show()
        }
    }

    // helper: try to discover FileProvider authority declared in the manifest
    private fun findFileProviderAuthority(): String? {
        try {
            val pi = packageManager.getPackageInfo(packageName, PackageManager.GET_PROVIDERS)
            val providers = pi.providers ?: return null
            for (p in providers) {
                val provName = p.name ?: ""
                val auth = p.authority ?: continue
                // common FileProvider implementation class names contain "FileProvider"
                if (provName.contains("FileProvider", ignoreCase = true)) {
                    Log.i(TAG, "Detected provider authority=$auth name=$provName")
                    return auth
                }
            }
            // fallback: return first authority if nothing matches
            if (providers.isNotEmpty()) {
                return providers[0].authority
            }
        } catch (e: Exception) {
            Log.w(TAG, "findFileProviderAuthority failed: ${e.message}")
        }
        return null
    }

    override fun onDestroy() {
        super.onDestroy()
        statusCallback?.let { RosBridgeClient.unsubscribe("/app/goal_status", it) }
        qrCallback?.let { RosBridgeClient.unsubscribe("/app/qr/image", it) }
    }
}
