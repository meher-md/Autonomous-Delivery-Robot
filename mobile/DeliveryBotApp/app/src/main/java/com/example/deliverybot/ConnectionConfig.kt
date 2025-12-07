package com.example.deliverybot
import android.content.Context
import android.content.SharedPreferences

object ConnectionConfig {
    private fun prefs(ctx: Context): SharedPreferences =
        ctx.getSharedPreferences("app", Context.MODE_PRIVATE)

    // Helper to get raw saved string
    private fun getRaw(ctx: Context): String =
        (prefs(ctx).getString("ip", "10.42.0.1") ?: "10.42.0.1").trim()

    // Extract just the host (IP or hostname) without port or scheme
    fun host(ctx: Context): String {
        var s = getRaw(ctx)
        // remove scheme
        if (s.contains("://")) s = s.substringAfter("://")
        // remove port if present
        if (s.contains(":")) s = s.substringBefore(":")
        return s.ifBlank { "10.42.0.1" }
    }

    // Get the full WS URL. If user entered port, use it. Else default to 9090.
    fun rosbridgeWs(ctx: Context): String {
        var s = getRaw(ctx)
        // Check scheme
        if (s.startsWith("ws://")) {
            s = s.replace("ws://", "wss://")
        } else if (!s.startsWith("wss://")) {
             // connection missing scheme entirely
             s = "wss://$s"
        }
        
        // Check port
        val noScheme = s.substringAfter("://")
        if (!noScheme.contains(":")) {
            s = "$s:9090"
        }
        return s
    }

    fun cameraUrl(ctx: Context) = "http://${host(ctx)}/camera/stream?topic=/image_raw"
    fun mapUrl(ctx: Context)    = "http://${host(ctx)}/map/latest.png"
    
    // For compatibility if needed
    fun setHost(ctx: Context, ip: String) {
        prefs(ctx).edit().putString("ip", ip.trim()).apply()
    }
}
