package com.example.deliverybot

import android.content.Context
import android.net.wifi.WifiManager
import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import kotlinx.coroutines.*
import java.net.InetAddress
import java.net.InetSocketAddress
import java.net.Socket
import java.net.NetworkInterface
import java.net.Inet4Address

data class Device(val ip: String, val name: String)

class ScanActivity : AppCompatActivity() {

    private lateinit var adapter: DeviceAdapter
    private val devices = mutableListOf<Device>()
    private var scanJob: Job? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_scan)

        val recycler = findViewById<RecyclerView>(R.id.recyclerDevices)
        recycler.layoutManager = LinearLayoutManager(this)
        adapter = DeviceAdapter(devices) { device ->
            // On Click
            Prefs.saveIp(this, device.ip)
            setResult(RESULT_OK)
            finish()
        }
        recycler.adapter = adapter

        findViewById<View>(R.id.btnCancel).setOnClickListener {
            setResult(RESULT_CANCELED)
            finish()
        }

        startScan()
        
        // Backup Box Logic
        val etManualIp = findViewById<android.widget.EditText>(R.id.etManualIp)
        findViewById<View>(R.id.btnManualConnect).setOnClickListener {
             val ip = etManualIp.text.toString().trim()
             if (ip.isNotEmpty()) {
                 Prefs.saveIp(this, ip)
                 setResult(RESULT_OK)
                 finish()
             }
        }
    }

    private fun startScan() {
        scanJob?.cancel()
        devices.clear()
        adapter.notifyDataSetChanged()
        findViewById<View>(R.id.progressBar).visibility = View.VISIBLE

        scanJob = CoroutineScope(Dispatchers.IO).launch {
            try {
                // Modified scan logic: try subnet scan and local fallback
                val wifiManager = applicationContext.getSystemService(Context.WIFI_SERVICE) as? WifiManager
                val myIps = getLocalIpAddresses()
                val allJobs = mutableListOf<Deferred<Unit>>()

                // 1. Wifi Scan (subnet)
                if (wifiManager != null) {
                    val dhcpInfo = wifiManager.dhcpInfo
                    if (dhcpInfo != null && dhcpInfo.ipAddress != 0) {
                         val myIp = formatIp(dhcpInfo.ipAddress)
                         val subnet = myIp.substringBeforeLast(".") + "."
                         
                         val subnetJobs = (1..254).map { i ->
                            async {
                                val targetIp = "$subnet$i"
                                checkIp(targetIp)
                            }
                         }
                         allJobs.addAll(subnetJobs)
                    }
                }
                
                // 2. Scan fallback (localhost or other interfaces if needed)
                // For now, simple subnet scan is usually enough. 
                // We'll trust the user to use manual box if scan fails.

                allJobs.awaitAll()
            } catch (e: Exception) {
                withContext(Dispatchers.Main) {
                    android.widget.Toast.makeText(this@ScanActivity, "Scan incomplete: ${e.message}", android.widget.Toast.LENGTH_SHORT).show()
                }
            } finally {
                withContext(Dispatchers.Main) {
                    findViewById<View>(R.id.progressBar).visibility = View.GONE
                    if (devices.isEmpty()) {
                        android.widget.Toast.makeText(this@ScanActivity, "No devices found", android.widget.Toast.LENGTH_SHORT).show()
                    }
                }
            }
        }
    }
    
    private suspend fun checkIp(targetIp: String) {
        try {
            val socket = Socket()
            socket.connect(InetSocketAddress(targetIp, 9090), 200)
            socket.close()
            
            val name = try {
                InetAddress.getByName(targetIp).canonicalHostName
            } catch (e: Exception) { targetIp }
            
            withContext(Dispatchers.Main) {
                devices.add(Device(targetIp, name))
                adapter.notifyItemInserted(devices.size - 1)
            }
        } catch (e: Exception) {
            // Not found
        }
    }

    private fun formatIp(ip: Int): String {
        return "${ip and 0xFF}.${(ip shr 8) and 0xFF}.${(ip shr 16) and 0xFF}.${(ip shr 24) and 0xFF}"
    }

    private fun getLocalIpAddresses(): List<String> {
         val ips = mutableListOf<String>()
         try {
             val en = NetworkInterface.getNetworkInterfaces()
             while (en.hasMoreElements()) {
                 val intf = en.nextElement()
                 val enumIpAddr = intf.inetAddresses
                 while (enumIpAddr.hasMoreElements()) {
                     val inetAddress = enumIpAddr.nextElement()
                     if (!inetAddress.isLoopbackAddress && inetAddress is Inet4Address) {
                         ips.add(inetAddress.hostAddress ?: "")
                     }
                 }
             }
         } catch (ex: Exception) {
             ex.printStackTrace()
         }
         return ips.filter { it.isNotEmpty() }
    }
    
    override fun onDestroy() {
        super.onDestroy()
        scanJob?.cancel()
    }
}

class DeviceAdapter(private val list: List<Device>, private val onClick: (Device) -> Unit) : RecyclerView.Adapter<DeviceAdapter.VH>() {
    class VH(v: View) : RecyclerView.ViewHolder(v) {
        val text: TextView = v.findViewById(android.R.id.text1)
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): VH {
        val v = LayoutInflater.from(parent.context).inflate(android.R.layout.simple_list_item_1, parent, false)
        return VH(v)
    }

    override fun onBindViewHolder(holder: VH, position: Int) {
        val d = list[position]
        holder.text.text = "${d.name}\n${d.ip}"
        holder.text.setTextColor(android.graphics.Color.WHITE)
        holder.itemView.setOnClickListener { onClick(d) }
    }

    override fun getItemCount() = list.size
}
