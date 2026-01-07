package com.example.deliverybot

import android.annotation.SuppressLint
import android.os.Bundle
import android.view.View
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.EditText
import android.widget.ImageButton
import android.widget.LinearLayout
import android.widget.SeekBar
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import com.example.deliverybot.teleop.CmdVelClient
import android.content.Intent
import android.speech.RecognizerIntent
import androidx.activity.result.contract.ActivityResultContracts

class ChatActivity : AppCompatActivity() {

    private var speed = 0.5
    private lateinit var cmd: CmdVelClient
    private lateinit var tvCommand1: TextView
    private lateinit var tvCommand2: TextView
    private lateinit var videoWebView: WebView
    private lateinit var speedText: TextView
    private lateinit var seekBarSpeed: SeekBar

    private val commandHistory = mutableListOf<String>()

    private val voiceLauncher = registerForActivityResult(ActivityResultContracts.StartActivityForResult()) { result ->
        if (result.resultCode == RESULT_OK) {
            val data = result.data
            val matches = data?.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS)
            if (!matches.isNullOrEmpty()) {
                val spokenText = matches[0]
                findViewById<EditText>(R.id.messageInput).setText(spokenText)
            }
        }
    }

    private fun log(msg: String) {
        // Add to history, keep only last 2
        commandHistory.add(msg)
        if (commandHistory.size > 2) {
            commandHistory.removeAt(0)
        }
        updateCommandDisplay()
    }

    private fun updateCommandDisplay() {
        val commandSection = findViewById<LinearLayout>(R.id.commandSection)
        
        when (commandHistory.size) {
            0 -> {
                // Hide when no commands
                commandSection.visibility = View.GONE
            }
            1 -> {
                // Show section, display command at bottom (tvCommand1)
                commandSection.visibility = View.VISIBLE
                tvCommand1.text = "Command: ${commandHistory[0]}"
                tvCommand2.visibility = View.GONE
            }
            else -> {
                // Both commands: older at top (tvCommand2), newer at bottom (tvCommand1)
                commandSection.visibility = View.VISIBLE
                tvCommand2.visibility = View.VISIBLE
                tvCommand2.text = "Command: ${commandHistory[0]}"  // Older command
                tvCommand1.text = "Command: ${commandHistory[1]}"  // Newer command
            }
        }
    }

    private fun updateSpeedUI() {
        speedText.text = "Speed: %.1f".format(speed)
    }

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_chat)

        // Initialize command display
        tvCommand1 = findViewById(R.id.tvCommand1)
        tvCommand2 = findViewById(R.id.tvCommand2)

        // Initialize video using VideoFragment (same as main screen)
        videoWebView = findViewById(R.id.videoWebView)
        setupVideoFragment()

        // Speed controls
        speedText = findViewById(R.id.speedText)
        seekBarSpeed = findViewById(R.id.seekBarSpeed)
        updateSpeedUI()

        seekBarSpeed.setOnSeekBarChangeListener(object : SeekBar.OnSeekBarChangeListener {
            override fun onProgressChanged(seekBar: SeekBar?, progress: Int, fromUser: Boolean) {
                speed = (progress / 100.0 * 2.0).coerceIn(0.1, 2.0)
                updateSpeedUI()
            }
            override fun onStartTrackingTouch(seekBar: SeekBar?) {}
            override fun onStopTrackingTouch(seekBar: SeekBar?) {}
        })

        // CmdVel client
        cmd = CmdVelClient(this)
        cmd.connect()

        // Direction buttons (now ImageButtons)
        findViewById<ImageButton>(R.id.btnUp).setOnClickListener { 
            log("MOVE_FORWARD")
            cmd.publish(linearX = speed) 
        }
        findViewById<ImageButton>(R.id.btnDown).setOnClickListener { 
            log("MOVE_BACKWARD")
            cmd.publish(linearX = -speed) 
        }
        findViewById<ImageButton>(R.id.btnLeft).setOnClickListener { 
            log("TURN_LEFT")
            cmd.publish(angularZ = speed) 
        }
        findViewById<ImageButton>(R.id.btnRight).setOnClickListener { 
            log("TURN_RIGHT")
            cmd.publish(angularZ = -speed) 
        }
        findViewById<ImageButton>(R.id.btnStop).setOnClickListener { 
            log("STOP")
            cmd.stop() 
        }

        // Voice input
        findViewById<ImageButton>(R.id.btnVoice).setOnClickListener {
            val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
                putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
                putExtra(RecognizerIntent.EXTRA_PROMPT, "Speak now...")
            }
            try {
                voiceLauncher.launch(intent)
            } catch (e: Exception) {
                Toast.makeText(this, "Voice input not supported", Toast.LENGTH_SHORT).show()
            }
        }

        // Send button
        findViewById<ImageButton>(R.id.btnSend).setOnClickListener {
            val input = findViewById<EditText>(R.id.messageInput)
            val text = input.text.toString().trim()
            if (text.isNotEmpty()) {
                processVoiceCommand(text)
                input.text.clear()
            }
        }
    }

    private var videoFragment: VideoFragment? = null

    private fun setupVideoFragment() {
        // Use VideoFragment - same as main screen
        val prefs = getSharedPreferences("app_prefs", MODE_PRIVATE)
        val ip = prefs.getString("ip", "ws://10.42.0.1:9090") ?: "ws://10.42.0.1:9090"
        val baseUrl = ip.replace("ws://", "http://").replace(":9090", ":8080")
        val videoUrl = "$baseUrl/stream?topic=/camera/image_raw"
        
        // Add VideoFragment to container - same as MainActivity
        videoFragment = VideoFragment.newInstance(videoUrl)
        supportFragmentManager.beginTransaction()
            .replace(R.id.videoFragmentContainer, videoFragment!!)
            .commitAllowingStateLoss()
    }

    override fun onResume() {
        super.onResume()
        videoFragment?.reloadVideo()
    }

    override fun onPause() {
        super.onPause()
        videoFragment?.stopVideo()
    }

    @SuppressLint("SetJavaScriptEnabled")
    private fun setupVideoStream() {
        videoWebView.visibility = android.view.View.VISIBLE
        videoWebView.settings.javaScriptEnabled = true
        videoWebView.settings.loadWithOverviewMode = true
        videoWebView.settings.useWideViewPort = true
        videoWebView.webViewClient = WebViewClient()

        // Load video stream from ROS web_video_server
        val prefs = getSharedPreferences("app_prefs", MODE_PRIVATE)
        val ip = prefs.getString("ip", "ws://10.42.0.1:9090") ?: "ws://10.42.0.1:9090"
        val baseUrl = ip.replace("ws://", "http://").replace(":9090", ":8080")
        val videoUrl = "$baseUrl/stream?topic=/camera/image_raw"
        
        videoWebView.loadUrl(videoUrl)
    }

    private fun processVoiceCommand(text: String) {
        val lowerText = text.lowercase()
        when {
            lowerText.contains("forward") || lowerText.contains("أمام") -> {
                log("MOVE_FORWARD")
                cmd.publish(linearX = speed)
            }
            lowerText.contains("back") || lowerText.contains("خلف") -> {
                log("MOVE_BACKWARD")
                cmd.publish(linearX = -speed)
            }
            lowerText.contains("left") || lowerText.contains("يسار") -> {
                log("TURN_LEFT")
                cmd.publish(angularZ = speed)
            }
            lowerText.contains("right") || lowerText.contains("يمين") -> {
                log("TURN_RIGHT")
                cmd.publish(angularZ = -speed)
            }
            lowerText.contains("stop") || lowerText.contains("قف") -> {
                log("STOP")
                cmd.stop()
            }
            else -> {
                Toast.makeText(this, "Unknown command: $text", Toast.LENGTH_SHORT).show()
            }
        }
    }

    override fun onDestroy() {
        try { cmd.stop() } catch (_: Throwable) {}
        try { cmd.close() } catch (_: Throwable) {}
        super.onDestroy()
    }
}
