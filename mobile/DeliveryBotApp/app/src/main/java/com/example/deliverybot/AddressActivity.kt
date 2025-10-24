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
    // UI (QR)
    private lateinit var qrImageView: ImageView
    private lateinit var qrPlaceholder: TextView
    private lateinit var btnGenerateQR: Button
    private lateinit var btnShareWhatsApp: Button
    private lateinit var tvStatus: TextView

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_address)

        val rg = findViewById<RadioGroup>(R.id.rgLocations)
        val etOther = findViewById<EditText>(R.id.etOther)
        val btnConfirm = findViewById<Button>(R.id.btnConfirmAddress)
        tvStatus = findViewById(R.id.tvStatus)

        // QR UI
        qrImageView = findViewById(R.id.qrImage)
        qrPlaceholder = findViewById(R.id.qrPlaceholder)
        btnGenerateQR = findViewById(R.id.btnGenerateQR)
        btnShareWhatsApp = findViewById(R.id.btnShareWhatsApp)
        // start disabled until appropriate
        btnGenerateQR.isEnabled = false
        btnShareWhatsApp.isEnabled = false

        rg.setOnCheckedChangeListener { _, checkedId ->
            etOther.visibility = if (checkedId == R.id.rbOther) View.VISIBLE else View.GONE
        }

        // Subscribe to robot feedback (optional)
        try {
            RosBridgeClient.subscribe("/app/goal_status") { msg ->
                runOnUiThread { tvStatus.text = "Robot: $msg" }
            }
        } catch (t: Throwable) {
            Log.e(TAG, "subscribe failed", t)
        }

        btnConfirm.setOnClickListener {
            val selectedText = when (rg.checkedRadioButtonId) {
                R.id.rbLibrary -> "Library"
                R.id.rbLab -> "Lab"
                R.id.rbLobby -> "Lobby"
                R.id.rbCafeteria -> "Cafeteria"
                R.id.rbOther -> etOther.text.toString().ifBlank { "Other" }
                else -> ""
            }

            if (selectedText.isBlank()) {
                Toast.makeText(this, "Please select a valid location", Toast.LENGTH_SHORT).show()
                return@setOnClickListener
            }

            // store selected for QR generation request
            selectedAddress = selectedText
            btnGenerateQR.isEnabled = true

            // If we already have a generated QR for this destination, display it immediately
            val existing = generatedQrByAddress[selectedText]
            if (existing != null) {
                generatedQrPath = existing
                try {
                    val bmp = BitmapFactory.decodeFile(existing)
                    if (bmp != null) {
                        runOnUiThread {
                            qrPlaceholder.visibility = View.GONE
                            qrImageView.setImageBitmap(bmp)
                            btnShareWhatsApp.isEnabled = true
                            Toast.makeText(this, "Using previously generated QR for $selectedText", Toast.LENGTH_SHORT).show()
                        }
                    }
                } catch (_: Exception) { /* ignore - will request again if needed */ }
            }

            if (!RosBridgeClient.isConnected()) {
                showAlert("Not connected", "Not connected to robot. Press Save / Connect first.")
                return@setOnClickListener
            }

            try {
                RosBridgeClient.publish("/app/goal_name", selectedText)
                tvStatus.text = "Sent: $selectedText"
                Toast.makeText(this, "Sent to robot: $selectedText", Toast.LENGTH_SHORT).show()
            } catch (t: Throwable) {
                Log.e(TAG, "publish failed", t)
                showAlert("Send failed", "Failed to send goal to robot.")
            }
        }

        // Generate QR button -> request ROS node to create and publish /app/qr/image
        btnGenerateQR.setOnClickListener {
            val addr = selectedAddress
            if (addr.isNullOrBlank()) {
                showAlert("No address", "Please confirm an address before generating a QR code.")
                return@setOnClickListener
            }

            // If QR already generated for this destination, reuse it (do not request new)
            generatedQrByAddress[addr]?.let { existingPath ->
                // reload and display
                val bmp = try { BitmapFactory.decodeFile(existingPath) } catch (_: Exception) { null }
                if (bmp != null) {
                    runOnUiThread {
                        qrPlaceholder.visibility = View.GONE
                        qrImageView.setImageBitmap(bmp)
                        btnShareWhatsApp.isEnabled = true
                        Toast.makeText(this, "QR already generated for $addr (locked).", Toast.LENGTH_SHORT).show()
                    }
                    return@setOnClickListener
                }
                // if file missing/failing to decode, fallthrough and request generation
            }

            if (!RosBridgeClient.isConnected()) {
                showAlert("Not connected", "Press Save / Connect first to connect to the robot.")
                return@setOnClickListener
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

        // Subscribe to receive generated QR (robust parsing of rosbridge wrapper or direct JSON)
        try {
            RosBridgeClient.subscribe("/app/qr/image") { raw ->
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
                        runOnUiThread { Toast.makeText(this, "Received QR response but no image found", Toast.LENGTH_SHORT).show() }
                        return@subscribe
                    }

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
                    }

                    runOnUiThread {
                        qrPlaceholder.visibility = View.GONE
                        qrImageView.setImageBitmap(bmp)
                        btnShareWhatsApp.isEnabled = true
                        Toast.makeText(this, "QR received and displayed", Toast.LENGTH_SHORT).show()
                    }
                } catch (e: Exception) {
                    Log.e(TAG, "Failed to handle /app/qr/image: ${e.message}", e)
                    runOnUiThread { showAlert("QR Error", "Failed to process QR image.") }
                }
            }
        } catch (t: Throwable) {
            Log.e(TAG, "subscribe /app/qr/image failed", t)
        }

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

            // collect authorities actually declared (for diagnostic message)
            try {
                val pi = packageManager.getPackageInfo(packageName, PackageManager.GET_PROVIDERS)
                val providers = pi.providers
                if (providers != null) {
                    for (p in providers) {
                        p.authority?.let { availableAuthorities.add(it) }
                    }
                }
            } catch (e: Exception) {
                Log.w(TAG, "Could not query installed providers: ${e.message}")
            }

            if (uri == null) {
                val diag = if (availableAuthorities.isNotEmpty()) {
                    "Available authorities: ${availableAuthorities.joinToString(", ")}"
                } else {
                    "No provider authorities detected in package."
                }
                Log.e(TAG, "FileProvider failed, lastEx=${lastEx?.message}", lastEx)
                showAlert("Share failed", "Failed to get file URI: ${lastEx?.message ?: "unknown"}\n\n$diag")
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
            } finally {
                // Revoke permissions after longer delay (give chosen app time to access the file)
                try {
                    window.decorView.postDelayed({
                        try { revokeUriPermission(uri, Intent.FLAG_GRANT_READ_URI_PERMISSION) } catch (_: Exception) {}
                    }, 60000) // 60s
                } catch (_: Exception) {}
            }
        }
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
}
