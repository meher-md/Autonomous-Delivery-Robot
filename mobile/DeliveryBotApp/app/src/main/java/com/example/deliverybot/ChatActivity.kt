package com.example.deliverybot

import android.os.Bundle
import android.view.View
import android.widget.*
import androidx.appcompat.app.AppCompatActivity

class ChatActivity : AppCompatActivity() {

    private lateinit var controlPanel: LinearLayout
    private var panelVisible = false
    private var speed = 0.2

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_chat)

        val toggleBtn = findViewById<Button>(R.id.togglePanelBtn)
        controlPanel = findViewById(R.id.controlPanel)

        val speedText = findViewById<TextView>(R.id.speedText)
        val speedBar  = findViewById<SeekBar>(R.id.speedBar)

        fun updateSpeedText() { speedText.text = "Speed: ${"%.2f".format(speed)}" }
        updateSpeedText()
        speedBar.progress = (speed * 100).toInt()
        speedBar.setOnSeekBarChangeListener(object: SeekBar.OnSeekBarChangeListener {
            override fun onProgressChanged(sb: SeekBar?, p: Int, fromUser: Boolean) {
                speed = p / 100.0
                updateSpeedText()
            }
            override fun onStartTrackingTouch(sb: SeekBar?) {}
            override fun onStopTrackingTouch(sb: SeekBar?) {}
        })

        toggleBtn.setOnClickListener {
            panelVisible = !panelVisible
            controlPanel.visibility = if (panelVisible) View.VISIBLE else View.GONE
        }

        // الأسهم (placeholder: Toast)
        mapOf(
            R.id.btnUp to "UP",
            R.id.btnDown to "DOWN",
            R.id.btnLeft to "LEFT",
            R.id.btnRight to "RIGHT",
            R.id.btnStop to "STOP"
        ).forEach { (id, label) ->
            findViewById<Button>(id).setOnClickListener {
                Toast.makeText(this, "Cmd: $label @v=$speed", Toast.LENGTH_SHORT).show()
                // TODO: ابعت cmd_vel عبر rosbridge هنا
            }
        }

        // Connect placeholder
        findViewById<Button>(R.id.btnConnect).setOnClickListener {
            val host = findViewById<EditText>(R.id.hostInput).text.toString()
            Toast.makeText(this, "Connecting to $host ...", Toast.LENGTH_SHORT).show()
            // TODO: فعّل RosbridgeClient هنا
        }

        // إرسال رسالة (placeholder)
        val chatLog = findViewById<TextView>(R.id.chatLog)
        val sendBtn = findViewById<Button>(R.id.sendBtn)
        val input   = findViewById<EditText>(R.id.inputMessage)
        sendBtn.setOnClickListener {
            val msg = input.text.toString().trim()
            if (msg.isNotEmpty()) {
                chatLog.append("You: $msg\n")
                input.setText("")
            }
        }
    }
}
