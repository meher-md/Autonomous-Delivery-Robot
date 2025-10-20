package com.example.deliverybot.net

import android.util.Log
import okhttp3.*
import okio.ByteString
import java.util.concurrent.TimeUnit
import org.json.JSONObject

object RosBridgeClient {
    private const val TAG = "RosBridgeClient"
    private var ws: WebSocket? = null
    private var connected: Boolean = false
    private val advertisedTopics = mutableSetOf<String>()

    private val client = OkHttpClient.Builder()
        .pingInterval(15, TimeUnit.SECONDS)
        .retryOnConnectionFailure(true)
        .build()

    @JvmStatic
    fun connect(baseUrl: String = "ws://10.42.0.1:9090") {
        try {
            val req = Request.Builder().url(baseUrl).build()
            ws = client.newWebSocket(req, object : WebSocketListener() {
                override fun onOpen(webSocket: WebSocket, response: Response) {
                    connected = true
                    Log.i(TAG, "WS OPEN: $baseUrl  code=${response.code}")
                }
                override fun onMessage(webSocket: WebSocket, text: String) {
                    Log.d(TAG, "WS RX: $text")
                }
                override fun onMessage(webSocket: WebSocket, bytes: ByteString) {
                    Log.d(TAG, "WS RX(bytes): ${bytes.size}B")
                }
                override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                    connected = false
                    Log.e(TAG, "WS FAIL: ${t.message}", t)
                }
                override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                    connected = false
                    Log.i(TAG, "WS CLOSED: $code $reason")
                }
            })
        } catch (t: Throwable) {
            connected = false
            Log.e(TAG, "connect() error: ${t.message}", t)
        }
    }

    @JvmStatic
    fun isConnected(): Boolean = connected

    @JvmStatic
    fun send(json: String) {
        if (!connected) {
            Log.w(TAG, "send() called but WS not connected")
            return
        }
        ws?.send(json)
    }

    /**
     * Always advertise topic (std_msgs/msg/String) before publishing.
     */
    @JvmStatic
    fun publish(topic: String, data: String) {
        if (!connected) {
            Log.w(TAG, "publish() called but WS not connected, topic=$topic")
            return
        }
        try {
            // Always advertise before publish (robust for rosbridge)
            val adv = JSONObject()
            adv.put("op", "advertise")
            adv.put("topic", topic)
            adv.put("type", "std_msgs/msg/String")
            ws?.send(adv.toString())
            Log.d(TAG, "WS TX advertise: ${adv.toString()}")

            // publish
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
    fun close() {
        try {
            // unadvertise previously advertised topics
            for (t in advertisedTopics) {
                try {
                    val unadv = JSONObject()
                    unadv.put("op", "unadvertise")
                    unadv.put("topic", t)
                    ws?.send(unadv.toString())
                    Log.d(TAG, "WS TX unadvertise: ${unadv.toString()}")
                } catch (_: Throwable) { /* ignore */ }
            }
            advertisedTopics.clear()
            ws?.close(1000, "bye")
        } finally {
            connected = false
            ws = null
        }
    }
}
