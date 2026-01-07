package com.example.deliverybot

import android.app.AlertDialog
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.BitmapFactory
import android.graphics.Color
import android.net.Uri
import android.util.Base64
import androidx.core.content.FileProvider
import java.io.File
import android.os.Bundle
import android.text.Editable
import android.text.TextWatcher
import android.util.Log
import android.util.TypedValue
import android.view.Gravity
import android.view.View
import android.widget.*
import androidx.appcompat.app.AppCompatActivity
import com.example.deliverybot.net.RosBridgeClient
import org.json.JSONArray
import org.json.JSONObject

// Data classes for Maps and Locations
data class LocationData(val name: String, val category: String = "All")
data class MapData(val name: String, val locations: MutableList<LocationData> = mutableListOf())

class AddressActivity : AppCompatActivity() {
    private val TAG = "DeliveryBot/Address"
    private var selectedAddress: String? = null
    private var generatedQrPath: String? = null
    private val generatedQrByAddress: MutableMap<String, String> = mutableMapOf()

    // Callbacks for ROS subscriptions
    private var statusCallback: ((String) -> Unit)? = null
    private var qrCallback: ((String) -> Unit)? = null

    // UI - New elements
    private lateinit var spinnerMaps: Spinner
    private lateinit var etSearch: EditText
    private lateinit var containerDestinations: LinearLayout // Changed from GridLayout
    
    // UI - Legacy elements
    private lateinit var btnPlaceOrder: Button
    private lateinit var btnOrderHistory: Button
    private lateinit var btnEditDestinations: ImageButton
    private lateinit var qrImageView: ImageView
    private lateinit var qrPlaceholder: TextView
    private lateinit var btnShareWhatsApp: Button
    private lateinit var tvStatus: TextView

    // Data
    private val maps = mutableListOf<MapData>()
    private var currentMapIndex = 0
    private var selectedDestinationButton: Button? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_address)

        // Initialize new UI elements
        spinnerMaps = findViewById(R.id.spinnerMaps)
        etSearch = findViewById(R.id.etSearch)
        containerDestinations = findViewById(R.id.containerDestinations)
        
        // Initialize buttons
        btnPlaceOrder = findViewById(R.id.btnPlaceOrder)
        btnOrderHistory = findViewById(R.id.btnOrderHistory)
        btnEditDestinations = findViewById(R.id.btnEditDestinations)
        tvStatus = findViewById(R.id.tvStatus)

        // QR UI
        qrImageView = findViewById(R.id.qrImage)
        qrPlaceholder = findViewById(R.id.qrPlaceholder)
        btnShareWhatsApp = findViewById(R.id.btnShareWhatsApp)
        btnShareWhatsApp.isEnabled = false

        loadMapsData()
        setupSpinner()
        setupSearch()
        refreshDestinationsHorizontal()

        btnEditDestinations.setOnClickListener {
            showMapManagementDialog()
        }

        // Subscribe to robot feedback
        try {
            statusCallback = { msg ->
                runOnUiThread { tvStatus.text = "Robot: $msg" }
            }
            RosBridgeClient.subscribe("/app/goal_status", statusCallback!!)
        } catch (t: Throwable) {
            Log.e(TAG, "subscribe failed", t)
        }

        btnPlaceOrder.setOnClickListener {
            if (selectedAddress == null) {
                Toast.makeText(this, "Please select a destination", Toast.LENGTH_SHORT).show()
                return@setOnClickListener
            }

            if (!RosBridgeClient.isConnected()) {
                showAlert("Not connected", "Not connected to robot. Press Save / Connect first.")
                return@setOnClickListener
            }

            try {
                RosBridgeClient.publish("/app/goal_name", selectedAddress!!)
                tvStatus.text = "Sent: $selectedAddress"
                Toast.makeText(this, "Order placed for $selectedAddress", Toast.LENGTH_SHORT).show()
                saveOrderToHistory(selectedAddress!!)
            } catch (t: Throwable) {
                Log.e(TAG, "publish failed", t)
                showAlert("Send failed", "Failed to send goal to robot.")
                return@setOnClickListener
            }

            generateQrFor(selectedAddress!!)
        }

        btnOrderHistory.setOnClickListener {
            startActivity(Intent(this, OrdersActivity::class.java))
        }

        setupQrSubscription()
        setupShareButton()
    }

    private fun loadMapsData() {
        val prefs = getSharedPreferences("app_prefs", MODE_PRIVATE)
        val mapsJson = prefs.getString("maps_data", null)
        
        if (mapsJson != null) {
            try {
                val jsonArray = JSONArray(mapsJson)
                maps.clear()
                for (i in 0 until jsonArray.length()) {
                    val mapObj = jsonArray.getJSONObject(i)
                    val mapName = mapObj.getString("name")
                    val locationsArray = mapObj.getJSONArray("locations")
                    val locations = mutableListOf<LocationData>()
                    for (j in 0 until locationsArray.length()) {
                        val locObj = locationsArray.getJSONObject(j)
                        locations.add(LocationData(
                            locObj.getString("name"),
                            locObj.optString("category", "All")
                        ))
                    }
                    maps.add(MapData(mapName, locations))
                }
            } catch (e: Exception) {
                Log.e(TAG, "Failed to load maps data", e)
                loadDefaultMaps()
            }
        } else {
            loadDefaultMaps()
        }
    }

    private fun loadDefaultMaps() {
        maps.clear()
        val defaultMap = MapData("Main Building - Floor 1", mutableListOf(
            LocationData("Lab 101", "Labs"),
            LocationData("Hall A", "Halls"),
            LocationData("Cafeteria", "All"),
            LocationData("Office 4B", "Offices"),
            LocationData("Library", "All"),
            LocationData("Lab 203", "Labs")
        ))
        maps.add(defaultMap)
        maps.add(MapData("Library", mutableListOf(
            LocationData("Reading Room", "All"),
            LocationData("Computer Lab", "Labs")
        )))
        maps.add(MapData("Cafeteria Building", mutableListOf(
            LocationData("Main Hall", "Halls"),
            LocationData("Kitchen", "All")
        )))
        saveMapsData()
    }

    private fun saveMapsData() {
        val prefs = getSharedPreferences("app_prefs", MODE_PRIVATE)
        val jsonArray = JSONArray()
        for (map in maps) {
            val mapObj = JSONObject()
            mapObj.put("name", map.name)
            val locationsArray = JSONArray()
            for (loc in map.locations) {
                val locObj = JSONObject()
                locObj.put("name", loc.name)
                locObj.put("category", loc.category)
                locationsArray.put(locObj)
            }
            mapObj.put("locations", locationsArray)
            jsonArray.put(mapObj)
        }
        prefs.edit().putString("maps_data", jsonArray.toString()).apply()
    }

    private fun setupSpinner() {
        // Save current selection if valid
        val currentSelectionName = if (maps.isNotEmpty() && currentMapIndex < maps.size) maps[currentMapIndex].name else null

        val mapNames = maps.map { it.name }
        val adapter = ArrayAdapter(this, R.layout.spinner_item, mapNames)
        adapter.setDropDownViewResource(R.layout.spinner_dropdown_item)
        spinnerMaps.adapter = adapter
        
        // Restore selection
        if (currentSelectionName != null) {
            val newIndex = mapNames.indexOf(currentSelectionName)
            if (newIndex != -1) {
                spinnerMaps.setSelection(newIndex)
                currentMapIndex = newIndex
            }
        }
        
        spinnerMaps.onItemSelectedListener = object : AdapterView.OnItemSelectedListener {
            override fun onItemSelected(parent: AdapterView<*>?, view: View?, position: Int, id: Long) {
                currentMapIndex = position
                refreshDestinationsHorizontal()
            }
            override fun onNothingSelected(parent: AdapterView<*>?) {}
        }
    }

    private fun setupSearch() {
        etSearch.addTextChangedListener(object : TextWatcher {
            override fun beforeTextChanged(s: CharSequence?, start: Int, count: Int, after: Int) {}
            override fun onTextChanged(s: CharSequence?, start: Int, before: Int, count: Int) {}
            override fun afterTextChanged(s: Editable?) {
                refreshDestinationsHorizontal()
            }
        })
    }

    private fun refreshDestinationsHorizontal() {
        containerDestinations.removeAllViews()
        // Note: Don't clear selectedDestinationButton here to preserve state if possible, 
        // but for simplicity we reset if map changes or search happens
        selectedDestinationButton = null
        selectedAddress = null
        
        if (maps.isEmpty() || currentMapIndex >= maps.size) return
        
        val currentMap = maps[currentMapIndex]
        val searchQuery = etSearch.text.toString().lowercase()
        
        val filteredLocations = currentMap.locations.filter { loc ->
            val matchesSearch = searchQuery.isEmpty() || loc.name.lowercase().contains(searchQuery)
            matchesSearch
        }

        // Chunk into groups of 3 to create 3 rows (Vertical columns in a Horizontal container)
        val chunkedLocations = filteredLocations.chunked(3)

        for (chunk in chunkedLocations) {
            val columnLayout = LinearLayout(this)
            columnLayout.orientation = LinearLayout.VERTICAL
            val columnParams = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.WRAP_CONTENT,
                LinearLayout.LayoutParams.WRAP_CONTENT
            )
            columnParams.setMargins(4, 0, 4, 0) // Spacing between columns
            columnLayout.layoutParams = columnParams

            for (location in chunk) {
                val btn = Button(this)
                btn.text = location.name
                btn.setTextColor(Color.WHITE)
                btn.textSize = 14f
                btn.isAllCaps = false
                btn.background = resources.getDrawable(R.drawable.bg_destination_button, theme)
                
                // Bigger buttons
                val btnParams = LinearLayout.LayoutParams(
                    TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_DIP, 110f, resources.displayMetrics).toInt(),
                    TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_DIP, 80f, resources.displayMetrics).toInt()
                )
                btnParams.setMargins(0, 4, 0, 4) // Spacing between rows
                btn.layoutParams = btnParams
                
                btn.setOnClickListener {
                    if (selectedDestinationButton == btn) {
                        // Toggle OFF (Deselect)
                        btn.isSelected = false
                        btn.background = resources.getDrawable(R.drawable.bg_destination_button, theme)
                        selectedDestinationButton = null
                        selectedAddress = null
                    } else {
                        // Toggle ON (Select new)
                        selectedDestinationButton?.isSelected = false
                        selectedDestinationButton?.background = resources.getDrawable(R.drawable.bg_destination_button, theme)
                        
                        btn.isSelected = true
                        btn.background = resources.getDrawable(R.drawable.bg_destination_selected, theme)
                        selectedDestinationButton = btn
                        selectedAddress = location.name
                    }
                }
                
                columnLayout.addView(btn)
            }
            containerDestinations.addView(columnLayout)
        }
    }

    private fun showMapManagementDialog() {
        val dialogView = layoutInflater.inflate(R.layout.dialog_map_management, null)
        val dialog = AlertDialog.Builder(this)
            .setView(dialogView)
            .create()
        
        // Transparent background to show rounded corners if any, or full screen
        dialog.window?.setBackgroundDrawable(android.graphics.drawable.ColorDrawable(Color.TRANSPARENT))

        val mapsContainer = dialogView.findViewById<LinearLayout>(R.id.mapsContainer)
        val locationsContainer = dialogView.findViewById<LinearLayout>(R.id.locationsContainer)
        val btnAddMap = dialogView.findViewById<View>(R.id.btnAddMap)
        val btnAddLocation = dialogView.findViewById<View>(R.id.btnAddLocation)
        val btnClose = dialogView.findViewById<View>(R.id.btnCloseDialog)

        // Helper to refresh dialog lists
        fun refreshDialog() {
            mapsContainer.removeAllViews()
            locationsContainer.removeAllViews()

            // 1. Refresh Maps List
            for ((mapIndex, map) in maps.withIndex()) {
                val row = LinearLayout(this)
                row.orientation = LinearLayout.HORIZONTAL
                row.gravity = Gravity.CENTER_VERTICAL
                row.setPadding(0, 8, 0, 8)

                val tv = TextView(this)
                tv.text = map.name
                tv.setTextColor(Color.WHITE)
                tv.textSize = 14f
                tv.layoutParams = LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f)

                val btnEdit = ImageButton(this)
                btnEdit.setImageResource(android.R.drawable.ic_menu_edit)
                btnEdit.setBackgroundColor(Color.TRANSPARENT)
                btnEdit.setOnClickListener { 
                    showEditMapDialog(mapIndex) { refreshDialog() } // Callback
                }

                val btnDelete = ImageButton(this)
                btnDelete.setImageResource(android.R.drawable.ic_menu_delete)
                btnDelete.setBackgroundColor(Color.TRANSPARENT)
                btnDelete.setOnClickListener {
                    if (maps.size > 1) {
                        maps.removeAt(mapIndex)
                        if (currentMapIndex >= maps.size) currentMapIndex = 0
                        
                        // Wait, update global state immediately
                        saveMapsData()
                        setupSpinner() 
                        refreshDestinationsHorizontal()
                        
                        refreshDialog()
                        Toast.makeText(this, "Map deleted", Toast.LENGTH_SHORT).show()
                    } else {
                        Toast.makeText(this, "Cannot delete the last map", Toast.LENGTH_SHORT).show()
                    }
                }

                row.addView(tv)
                row.addView(btnEdit)
                row.addView(btnDelete)
                mapsContainer.addView(row)
            }

            // 2. Refresh Locations List (Current Map)
            if (maps.isNotEmpty() && currentMapIndex < maps.size) {
                 val currentMap = maps[currentMapIndex]
                 for ((locIndex, loc) in currentMap.locations.withIndex()) {
                    val row = LinearLayout(this)
                    row.orientation = LinearLayout.HORIZONTAL
                    row.gravity = Gravity.CENTER_VERTICAL
                    row.setPadding(0, 8, 0, 8)

                    val tv = TextView(this)
                    tv.text = loc.name
                    tv.setTextColor(Color.WHITE)
                    tv.textSize = 14f
                    tv.layoutParams = LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f)

                    val btnEdit = ImageButton(this)
                    btnEdit.setImageResource(android.R.drawable.ic_menu_edit)
                    btnEdit.setBackgroundColor(Color.TRANSPARENT)
                    btnEdit.setOnClickListener { 
                        showEditLocationDialog(currentMapIndex, locIndex) { refreshDialog() }
                    }

                    val btnDelete = ImageButton(this)
                    btnDelete.setImageResource(android.R.drawable.ic_menu_delete)
                    btnDelete.setBackgroundColor(Color.TRANSPARENT)
                    btnDelete.setOnClickListener {
                        currentMap.locations.removeAt(locIndex)
                        
                        saveMapsData()
                        refreshDestinationsHorizontal()
                        
                        refreshDialog()
                        Toast.makeText(this, "Location deleted", Toast.LENGTH_SHORT).show()
                    }

                    row.addView(tv)
                    row.addView(btnEdit)
                    row.addView(btnDelete)
                    locationsContainer.addView(row)
                 }
            }
        }

        // Initial populate
        refreshDialog()

        btnAddMap.setOnClickListener {
            showAddMapDialog { refreshDialog() }
        }

        btnAddLocation.setOnClickListener {
            showAddLocationDialog { refreshDialog() }
        }

        btnClose.setOnClickListener {
            dialog.dismiss()
        }

        dialog.show()
    }

    // Callbacks for real-time updates
    private fun showAddMapDialog(onComplete: () -> Unit) {
        val input = EditText(this)
        input.hint = "Map name"
        AlertDialog.Builder(this)
            .setTitle("Add New Map")
            .setView(input)
            .setPositiveButton("Add") { _, _ ->
                val name = input.text.toString().trim()
                if (name.isNotBlank()) {
                    maps.add(MapData(name))
                    saveMapsData()
                    setupSpinner()
                    refreshDestinationsHorizontal()
                    onComplete() // Refresh dialog list
                    Toast.makeText(this, "Map added", Toast.LENGTH_SHORT).show()
                }
            }
            .setNegativeButton("Cancel", null)
            .show()
    }

    private fun showEditMapDialog(mapIndex: Int, onComplete: () -> Unit) {
        val input = EditText(this)
        input.setText(maps[mapIndex].name)
        AlertDialog.Builder(this)
            .setTitle("Edit Map Name")
            .setView(input)
            .setPositiveButton("Save") { _, _ ->
                val name = input.text.toString().trim()
                if (name.isNotBlank()) {
                    maps[mapIndex] = maps[mapIndex].copy(name = name)
                    saveMapsData()
                    setupSpinner()
                    onComplete()
                    Toast.makeText(this, "Map updated", Toast.LENGTH_SHORT).show()
                }
            }
            .setNegativeButton("Cancel", null)
            .show()
    }

    private fun showAddLocationDialog(onComplete: () -> Unit) {
        if (maps.isEmpty()) return
        
        val layout = LinearLayout(this)
        layout.orientation = LinearLayout.VERTICAL
        layout.setPadding(40, 20, 40, 20)
        
        val inputName = EditText(this)
        inputName.hint = "Location name"
        layout.addView(inputName)

        val tvMapLabel = TextView(this)
        tvMapLabel.text = "Select Map:"
        tvMapLabel.setPadding(0, 20, 0, 10)
        layout.addView(tvMapLabel)

        val spinnerMap = Spinner(this)
        val mapNames = maps.map { it.name }
        val adapter = ArrayAdapter(this, android.R.layout.simple_spinner_dropdown_item, mapNames)
        spinnerMap.adapter = adapter
        spinnerMap.setSelection(currentMapIndex)
        layout.addView(spinnerMap)
        
        AlertDialog.Builder(this)
            .setTitle("Add New Location")
            .setView(layout)
            .setPositiveButton("Add") { _, _ ->
                val name = inputName.text.toString().trim()
                val targetMapIndex = spinnerMap.selectedItemPosition
                
                if (name.isNotBlank() && targetMapIndex >= 0 && targetMapIndex < maps.size) {
                    maps[targetMapIndex].locations.add(LocationData(name, "All"))
                    saveMapsData()
                    
                    // Only refresh homepage if we modified the currently viewed map
                    if (targetMapIndex == currentMapIndex) {
                        refreshDestinationsHorizontal()
                    }
                    
                    onComplete() // Refresh dialog list
                    Toast.makeText(this, "Location added to ${maps[targetMapIndex].name}", Toast.LENGTH_SHORT).show()
                }
            }
            .setNegativeButton("Cancel", null)
            .show()
    }

    private fun showEditLocationDialog(mapIndex: Int, locIndex: Int, onComplete: () -> Unit) {
        val loc = maps[mapIndex].locations[locIndex]
        
        val layout = LinearLayout(this)
        layout.orientation = LinearLayout.VERTICAL
        layout.setPadding(40, 20, 40, 20)
        
        val inputName = EditText(this)
        inputName.setText(loc.name)
        layout.addView(inputName)
        
        AlertDialog.Builder(this)
            .setTitle("Edit Location")
            .setView(layout)
            .setPositiveButton("Save") { _, _ ->
                val name = inputName.text.toString().trim()
                if (name.isNotBlank()) {
                    maps[mapIndex].locations[locIndex] = LocationData(name, "All")
                    saveMapsData()
                    refreshDestinationsHorizontal()
                    onComplete()
                    Toast.makeText(this, "Location updated", Toast.LENGTH_SHORT).show()
                }
            }
            .setNegativeButton("Cancel", null)
            .show()
    }

    private fun generateQrFor(addr: String) {
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
        try {
            qrCallback = { raw ->
                try {
                    var b64 = ""
                    val top = org.json.JSONObject(raw)
                    if (top.has("msg")) {
                        val msgObj = top.optJSONObject("msg")
                        if (msgObj != null && msgObj.has("data")) {
                            val inner = msgObj.optString("data", "")
                            val innerJson = try { org.json.JSONObject(inner) } catch (_: Exception) { null }
                            if (innerJson != null) {
                                b64 = innerJson.optString("qr_b64_png", "")
                            } else {
                                b64 = inner
                            }
                        }
                    } else if (top.has("qr_b64_png")) {
                        b64 = top.optString("qr_b64_png", "")
                    } else if (top.has("data")) {
                        val maybe = top.optString("data", "")
                        val j = try { org.json.JSONObject(maybe) } catch (_: Exception) { null }
                        if (j != null) b64 = j.optString("qr_b64_png", "")
                    }

                    if (b64.isBlank()) {
                        Log.w(TAG, "No qr_b64_png found in message: $raw")
                    } else {
                        val bytes = Base64.decode(b64, Base64.DEFAULT)
                        val bmp = BitmapFactory.decodeByteArray(bytes, 0, bytes.size)

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
                                val payloadObj = candidateJson.optJSONObject("payload")
                                if (payloadObj != null) payloadAddress = payloadObj.optString("address", null)
                                if (payloadAddress == null && candidateJson.has("address")) payloadAddress = candidateJson.optString("address", null)
                            }
                        } catch (_: Exception) {}

                        val baseDir = externalCacheDir ?: cacheDir
                        val qrFile = File(baseDir, "qr_${System.currentTimeMillis()}.png")
                        qrFile.outputStream().use { out -> bmp.compress(android.graphics.Bitmap.CompressFormat.PNG, 100, out) }
                        generatedQrPath = qrFile.absolutePath

                        val key = payloadAddress ?: selectedAddress
                        if (key != null) {
                            generatedQrByAddress[key] = qrFile.absolutePath
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

            val discoveredAuth = findFileProviderAuthority()
            val authoritiesToTry = mutableListOf<String>()
            discoveredAuth?.let { authoritiesToTry.add(it) }
            authoritiesToTry.add("${packageName}.provider")
            authoritiesToTry.add("${packageName}.fileprovider")

            var uri: Uri? = null
            var lastEx: Exception? = null

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

            val sendIntent = Intent(Intent.ACTION_SEND).apply {
                type = "image/png"
                putExtra(Intent.EXTRA_STREAM, uri)
                addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            }

            try {
                val pm = packageManager
                val res = pm.queryIntentActivities(sendIntent, PackageManager.MATCH_DEFAULT_ONLY)
                for (ri in res) {
                    try { grantUriPermission(ri.activityInfo.packageName, uri, Intent.FLAG_GRANT_READ_URI_PERMISSION) } catch (_: Exception) {}
                }
            } catch (ex: Exception) {
                Log.w(TAG, "Failed to grant uri permission to all handlers: ${ex.message}")
            }

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
        val qrPath = generatedQrByAddress[destination] ?: ""
        val newEntry = "$timestamp|$destination|$qrPath"
        val newHistory = if (history.isBlank()) newEntry else "$history;$newEntry"
        prefs.edit().putString("order_history", newHistory).apply()
    }

    private fun updateOrderHistoryWithQr(destination: String, path: String) {
        val prefs = getSharedPreferences("app_prefs", MODE_PRIVATE)
        val history = prefs.getString("order_history", "") ?: ""
        if (history.isBlank()) return
        val items = history.split(";").toMutableList()
        
        for (i in items.indices.reversed()) {
            val parts = items[i].split("|")
            if (parts.size >= 2) {
                val dest = parts[1]
                if (dest == destination) {
                    val timestamp = parts[0]
                    val newEntry = "$timestamp|$dest|$path"
                    items[i] = newEntry
                    break
                }
            }
        }
        
        val newHistory = items.joinToString(";")
        prefs.edit().putString("order_history", newHistory).apply()
    }

    private fun showAlert(title: String, message: String) {
        runOnUiThread {
            AlertDialog.Builder(this)
                .setTitle(title)
                .setMessage(message)
                .setPositiveButton("OK", null)
                .show()
        }
    }

    private fun findFileProviderAuthority(): String? {
        try {
            val pi = packageManager.getPackageInfo(packageName, PackageManager.GET_PROVIDERS)
            val providers = pi.providers ?: return null
            for (p in providers) {
                val provName = p.name ?: ""
                val auth = p.authority ?: continue
                if (provName.contains("FileProvider", ignoreCase = true)) {
                    Log.i(TAG, "Detected provider authority=$auth name=$provName")
                    return auth
                }
            }
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
