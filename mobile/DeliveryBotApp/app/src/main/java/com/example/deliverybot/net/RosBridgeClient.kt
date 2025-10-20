package com.example.deliverybot.net

import android.util.Log
import okhttp3.*
import okio.ByteString
import java.util.concurrent.TimeUnit
import org.json.JSONObject

object RosBridgeClient {
    private const val TAG = "RosBridgeClient"
    private var ws: WebSocket? = null

    private val client = OkHttpClient.Builder()
        .pingInterval(15, TimeUnit.SECONDS)
        .retryOnConnectionFailure(true)
        .build()

    @JvmStatic
    fun connect(baseUrl: String = "ws://10.42.0.1/rosbridge") {
        try {
            val req = Request.Builder()
                .url(baseUrl) // لازم يكون ws://<IP>/rosbridge
                .build()

            ws = client.newWebSocket(req, object : WebSocketListener() {
                override fun onOpen(webSocket: WebSocket, response: Response) {
                    Log.i(TAG, "WS OPEN: $baseUrl  code=${response.code}")
                }
                override fun onMessage(webSocket: WebSocket, text: String) {
                    Log.d(TAG, "WS RX: $text")
                }
                override fun onMessage(webSocket: WebSocket, bytes: ByteString) {
                    Log.d(TAG, "WS RX(bytes): ${bytes.size}B")
                }
                override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                    Log.e(TAG, "WS FAIL: ${t.message}", t)
                }
                override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                    Log.i(TAG, "WS CLOSED: $code $reason")
                }
            })
        } catch (t: Throwable) {
            Log.e(TAG, "connect() error: ${t.message}", t)
        }
    }

    @JvmStatic
    fun send(json: String) { ws?.send(json) }

    /**
     * Helper: publish a plain string message to a topic using rosbridge "publish" op.
     * Example: publish("/app/address", "Library")
     */
    @JvmStatic
    fun publish(topic: String, data: String) {
        try {
            val obj = JSONObject()
            obj.put("op", "publish")
            obj.put("topic", topic)
            val msg = JSONObject()
            msg.put("data", data)
            obj.put("msg", msg)
            ws?.send(obj.toString())
            Log.d(TAG, "WS TX publish: ${obj.toString()}")
        } catch (t: Throwable) {
            Log.e(TAG, "publish() error: ${t.message}", t)
        }
    }

    @JvmStatic
    fun close() { ws?.close(1000, "bye") }
}
