package com.example.deliverybot
import android.content.Context
import android.content.SharedPreferences
object ConnectionConfig {
  private fun prefs(ctx: Context): SharedPreferences =
    ctx.getSharedPreferences("delivery_prefs", Context.MODE_PRIVATE)
  fun setHost(ctx: Context, ip: String) { prefs(ctx).edit().putString("BASE_IP", ip.trim()).apply() }
  fun host(ctx: Context): String = (prefs(ctx).getString("BASE_IP", "") ?: "").ifBlank { "10.42.0.1" }
  fun cameraUrl(ctx: Context)   = "http://${host(ctx)}:8080/stream.mjpg"
  fun mapUrl(ctx: Context)      = "http://${host(ctx)}:8070/map.png"
  fun rosbridgeWs(ctx: Context) = "ws://${host(ctx)}:9090"
}
