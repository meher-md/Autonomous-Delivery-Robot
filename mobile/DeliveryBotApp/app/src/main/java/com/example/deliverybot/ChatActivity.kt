package com.example.deliverybot

import android.os.Bundle
import android.view.View
import android.widget.Button
import android.widget.ScrollView
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import com.example.deliverybot.teleop.CmdVelClient

class ChatActivity : AppCompatActivity() {

    private var speed = 0.5
    private lateinit var logText: TextView
    private lateinit var logScroll: ScrollView
    private lateinit var cmd: CmdVelClient

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

        // شغّل ناشر cmd_vel
        cmd = CmdVelClient(this)
        cmd.connect()

        val panelInclude = findViewById<View>(R.id.panelInclude)
        findViewById<Button>(R.id.btnTogglePanel).setOnClickListener {
            panelInclude.visibility = if (panelInclude.visibility == View.VISIBLE) View.GONE else View.VISIBLE
        }

        // أزرار الاتجاهات (نفس IDs المستخدمة سابقًا)
        findViewById<Button>(R.id.btnUp).setOnClickListener    { log("MOVE_FORWARD");  cmd.publish(linearX =  speed) }
        findViewById<Button>(R.id.btnDown).setOnClickListener  { log("MOVE_BACKWARD"); cmd.publish(linearX = -speed) }
        findViewById<Button>(R.id.btnLeft).setOnClickListener  { log("TURN_LEFT");     cmd.publish(angularZ =  speed) }
        findViewById<Button>(R.id.btnRight).setOnClickListener { log("TURN_RIGHT");    cmd.publish(angularZ = -speed) }
        findViewById<Button>(R.id.btnStop).setOnClickListener  { log("STOP");          cmd.stop() }

        // لو عندك نصّ لعرض السرعة (اختياري)
        val speedText = findViewById<TextView?>(R.id.speedText)
        speedText?.let { updateSpeedUI(it) }
        findViewById<Button?>(R.id.btnSpeedPlus)?.setOnClickListener {
            speed = (speed + 0.1).coerceAtMost(2.0)
            speedText?.let { updateSpeedUI(it) }
        }
        findViewById<Button?>(R.id.btnSpeedMinus)?.setOnClickListener {
            speed = (speed - 0.1).coerceAtLeast(0.1)
            speedText?.let { updateSpeedUI(it) }
        }
    }

    override fun onDestroy() {
        try { cmd.stop() } catch (_: Throwable) {}
        try { cmd.close() } catch (_: Throwable) {}
        super.onDestroy()
    }
}
