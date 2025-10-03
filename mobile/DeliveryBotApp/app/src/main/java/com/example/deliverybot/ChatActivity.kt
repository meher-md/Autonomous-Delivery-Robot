package com.example.deliverybot

import android.os.Bundle
import android.view.View
import android.widget.*
import androidx.appcompat.app.AppCompatActivity

class ChatActivity : AppCompatActivity() {
    private var speed = 0.5

    private lateinit var logText: TextView
    private lateinit var logScroll: ScrollView

    private fun log(msg: String) {
        logText.append("Command: $msg\n")
        logScroll.post { logScroll.fullScroll(View.FOCUS_DOWN) }
    }

    private fun updateSpeedUI(speedText: TextView) {
        speedText.text = "Speed: %.1f".format(speed)
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_chat)

        logText = findViewById(R.id.logText)
        logScroll = findViewById(R.id.logScroll)

        val panelInclude = findViewById<View>(R.id.panelInclude)
        findViewById<Button>(R.id.btnTogglePanel).setOnClickListener {
            panelInclude.visibility = if (panelInclude.visibility == View.VISIBLE) View.GONE else View.VISIBLE
        }

        // أزرار الاتجاهات
        findViewById<Button>(R.id.btnUp).setOnClickListener    { log("MOVE_FORWARD") }
        findViewById<Button>(R.id.btnDown).setOnClickListener  { log("MOVE_BACKWARD") }
        findViewById<Button>(R.id.btnLeft).setOnClickListener  { log("TURN_LEFT") }
        findViewById<Button>(R.id.btnRight).setOnClickListener { log("TURN_RIGHT") }
        findViewById<Button>(R.id.btnStop).setOnClickListener  { log("STOP") }

        // السرعة
        val speedText = findViewById<TextView>(R.id.speedText)
        updateSpeedUI(speedText)
        findViewById<Button>(R.id.btnSpeedPlus).setOnClickListener {
            speed = (speed + 0.1).coerceAtMost(2.0)
            updateSpeedUI(speedText)
            log("SPEED_UP -> %.1f".format(speed))
        }
        findViewById<Button>(R.id.btnSpeedMinus).setOnClickListener {
            speed = (speed - 0.1).coerceAtLeast(0.1)
            updateSpeedUI(speedText)
            log("SPEED_DOWN -> %.1f".format(speed))
        }

        // إرسال رسالة نصية (placeholder)
        val input = findViewById<EditText>(R.id.messageInput)
        findViewById<Button>(R.id.btnSend).setOnClickListener {
            val txt = input.text.toString().trim()
            if (txt.isNotEmpty()) {
                log("MSG: $txt")
                input.setText("")
            }
        }
    }
}
