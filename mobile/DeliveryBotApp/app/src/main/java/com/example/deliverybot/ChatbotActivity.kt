package com.example.deliverybot

import android.content.Intent
import android.os.Bundle
import android.speech.RecognizerIntent
import android.speech.tts.TextToSpeech
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.Button
import android.widget.EditText
import android.widget.ImageButton
import android.widget.TextView
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.drawerlayout.widget.DrawerLayout
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import org.json.JSONArray
import org.json.JSONObject
import java.text.SimpleDateFormat
import java.util.*

/**
 * AI Chat Activity - ROS Llama-powered Chatbot
 * Features: Voice input/output, Chat history drawer, Multiple conversations
 */
class ChatbotActivity : AppCompatActivity(), TextToSpeech.OnInitListener {

    // UI Components
    private lateinit var drawerLayout: DrawerLayout
    private lateinit var recyclerViewChat: RecyclerView
    private lateinit var recyclerViewHistory: RecyclerView
    private lateinit var editTextMessage: EditText
    private lateinit var btnSend: ImageButton
    private lateinit var btnBack: ImageButton
    private lateinit var btnMic: ImageButton
    private lateinit var btnHistory: ImageButton
    private lateinit var btnNewChat: ImageButton
    private lateinit var btnClearHistory: Button
    private lateinit var txtChatTitle: TextView
    private lateinit var txtConnectionStatus: TextView
    private lateinit var btnRobotAssistant: ImageButton

    // Chat Components
    private lateinit var chatAdapter: ChatAdapter
    private val messagesList = mutableListOf<ChatMessage>()
    private val chatbotEngine = ChatbotEngine()

    // Conversation Management
    private var currentConversationId: String = ""
    private val conversations = mutableListOf<Conversation>()
    private lateinit var historyAdapter: HistoryAdapter

    // Text-to-Speech
    private lateinit var tts: TextToSpeech
    private var wasVoiceInput = false

    // SharedPreferences keys
    private val PREFS_NAME = "chat_history"
    private val CONVERSATIONS_KEY = "conversations"

    data class Conversation(
        val id: String,
        var title: String,
        var messages: MutableList<ChatMessage>,
        val timestamp: Long
    )

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_chatbot)

        // Initialize TTS
        tts = TextToSpeech(this, this)

        // Initialize views
        initializeViews()
        setupRecyclerView()
        setupHistoryRecyclerView()
        setupListeners()
        setupRosSubscription()

        // Load conversations and start new or resume
        loadConversations()
        if (conversations.isEmpty()) {
            startNewConversation()
        } else {
            loadConversation(conversations.first().id)
        }

        // Update connection status
        updateConnectionStatus()
    }

    override fun onInit(status: Int) {
        if (status == TextToSpeech.SUCCESS) {
            tts.language = Locale.US
        }
    }

    private fun initializeViews() {
        drawerLayout = findViewById(R.id.drawerLayout)
        recyclerViewChat = findViewById(R.id.recyclerViewChat)
        recyclerViewHistory = findViewById(R.id.recyclerViewHistory)
        editTextMessage = findViewById(R.id.editTextMessage)
        btnSend = findViewById(R.id.btnSend)
        btnBack = findViewById(R.id.btnBack)
        btnMic = findViewById(R.id.btnMic)
        btnHistory = findViewById(R.id.btnHistory)
        btnNewChat = findViewById(R.id.btnNewChat)
        btnClearHistory = findViewById(R.id.btnClearHistory)
        txtChatTitle = findViewById(R.id.txtChatTitle)
        txtConnectionStatus = findViewById(R.id.txtConnectionStatus)
        btnRobotAssistant = findViewById(R.id.btnRobotAssistant)
    }

    private fun setupRecyclerView() {
        chatAdapter = ChatAdapter(messagesList)
        recyclerViewChat.apply {
            adapter = chatAdapter
            layoutManager = LinearLayoutManager(this@ChatbotActivity).apply {
                stackFromEnd = true
            }
        }
    }

    private fun setupHistoryRecyclerView() {
        historyAdapter = HistoryAdapter(
            conversations,
            onClick = { conversation ->
                loadConversation(conversation.id)
                drawerLayout.closeDrawers()
            },
            onDelete = { conversation, position ->
                deleteConversation(conversation, position)
            }
        )
        recyclerViewHistory.apply {
            adapter = historyAdapter
            layoutManager = LinearLayoutManager(this@ChatbotActivity)
        }
    }

    private fun deleteConversation(conv: Conversation, position: Int) {
        // If deleting current conversation, start new one
        if (conv.id == currentConversationId) {
            currentConversationId = ""
            messagesList.clear()
            chatAdapter.notifyDataSetChanged()
            txtChatTitle.text = "AI Chat"
        }
        conversations.removeAt(position)
        historyAdapter.notifyItemRemoved(position)
        saveConversations()
        
        // If no conversations left, start new one
        if (conversations.isEmpty()) {
            startNewConversation()
        }
    }

    private fun setupListeners() {
        btnSend.setOnClickListener { sendMessage() }
        
        btnBack.setOnClickListener {
            saveCurrentConversation()
            finish()
        }

        btnMic.setOnClickListener { startVoiceRecognition() }

        btnHistory.setOnClickListener {
            if (drawerLayout.isDrawerOpen(android.view.Gravity.END)) {
                drawerLayout.closeDrawer(android.view.Gravity.END)
            } else {
                drawerLayout.openDrawer(android.view.Gravity.END)
            }
        }

        btnNewChat.setOnClickListener {
            saveCurrentConversation()
            startNewConversation()
        }

        btnClearHistory.setOnClickListener {
            conversations.clear()
            saveConversations()
            historyAdapter.notifyDataSetChanged()
            startNewConversation()
            drawerLayout.closeDrawers()
            Toast.makeText(this, "History cleared", Toast.LENGTH_SHORT).show()
        }

        btnRobotAssistant.setOnClickListener {
            startActivity(Intent(this, RobotAssistantActivity::class.java))
        }

        editTextMessage.setOnEditorActionListener { _, _, _ ->
            sendMessage()
            true
        }
    }

    // Voice recognition
    private val voiceLauncher = registerForActivityResult(
        ActivityResultContracts.StartActivityForResult()
    ) { result ->
        if (result.resultCode == RESULT_OK) {
            val results = result.data?.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS)
            results?.firstOrNull()?.let { spokenText ->
                editTextMessage.setText(spokenText)
                wasVoiceInput = true
                sendMessage()
            }
        }
    }

    private fun startVoiceRecognition() {
        val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
            putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            putExtra(RecognizerIntent.EXTRA_LANGUAGE, "ar")
            putExtra(RecognizerIntent.EXTRA_PROMPT, "Speak now...")
        }
        try {
            voiceLauncher.launch(intent)
        } catch (e: Exception) {
            Toast.makeText(this, "Voice input not available", Toast.LENGTH_SHORT).show()
        }
    }

    // ROS Subscription
    private var responseCallback: ((String) -> Unit)? = null

    private fun setupRosSubscription() {
        responseCallback = { response: String ->
            runOnUiThread {
                addBotMessage(response)
                if (wasVoiceInput) {
                    tts.speak(response, TextToSpeech.QUEUE_FLUSH, null, "response")
                    wasVoiceInput = false
                }
            }
        }
        com.example.deliverybot.net.RosBridgeClient.subscribe("/app/chat/response", responseCallback!!)
    }

    private fun updateConnectionStatus() {
        val connected = com.example.deliverybot.net.RosBridgeClient.isConnected()
        val symbol = if (connected) "🟢" else "🔴"
        txtConnectionStatus.text = "$symbol Powered by Llama AI"
        txtConnectionStatus.setTextColor(0xFFB0BEC5.toInt()) // Blue-Gray
    }

    private fun sendMessage() {
        val messageText = editTextMessage.text.toString().trim()
        if (messageText.isEmpty()) return

        addUserMessage(messageText)
        editTextMessage.text.clear()

        // Update conversation title in HISTORY based on first user message
        // We only update if the title is still the default or generic
        val currentConv = conversations.find { it.id == currentConversationId }
        if (currentConv != null && (currentConv.title == "AI Chat" || currentConv.title == "New Chat")) {
            val title = messageText.take(25) + if (messageText.length > 25) "..." else ""
            currentConv.title = title
            historyAdapter.notifyDataSetChanged()
        }

        // ROS Llama only - no offline fallback
        if (com.example.deliverybot.net.RosBridgeClient.isConnected()) {
            com.example.deliverybot.net.RosBridgeClient.publish("/app/chat/request", messageText)
        } else {
            // Show not connected message
            addBotMessage("⚠️ Not connected to AI server. Please run ./app on your computer and ensure you're on the same network.")
        }
    }

    private fun addUserMessage(message: String) {
        val chatMessage = ChatMessage(message, false, getCurrentTime())
        messagesList.add(chatMessage)
        chatAdapter.notifyItemInserted(messagesList.size - 1)
        scrollToBottom()
        saveCurrentConversation()
    }

    private fun addBotMessage(message: String) {
        val chatMessage = ChatMessage(message, true, getCurrentTime())
        messagesList.add(chatMessage)
        chatAdapter.notifyItemInserted(messagesList.size - 1)
        scrollToBottom()
        saveCurrentConversation()
    }

    private fun scrollToBottom() {
        if (messagesList.isNotEmpty()) {
            recyclerViewChat.smoothScrollToPosition(messagesList.size - 1)
        }
    }

    private fun getCurrentTime(): String {
        return SimpleDateFormat("hh:mm a", Locale.getDefault()).format(Date())
    }

    // Conversation Management
    private fun startNewConversation() {
        saveCurrentConversation()
        currentConversationId = UUID.randomUUID().toString()
        messagesList.clear()
        chatAdapter.notifyDataSetChanged()
        txtChatTitle.text = "AI Chat"

        val newConv = Conversation(
            id = currentConversationId,
            title = "AI Chat",
            messages = mutableListOf(),
            timestamp = System.currentTimeMillis()
        )
        conversations.add(0, newConv)
        historyAdapter.notifyDataSetChanged()
        saveConversations()

        // Welcome message
        addBotMessage("Hi! 👋 How can I help you today?")
    }

    private fun loadConversation(id: String) {
        saveCurrentConversation()
        currentConversationId = id
        val conv = conversations.find { it.id == id } ?: return

        messagesList.clear()
        messagesList.addAll(conv.messages)
        chatAdapter.notifyDataSetChanged()
        txtChatTitle.text = "AI Chat"
        scrollToBottom()
    }

    private fun saveCurrentConversation() {
        if (currentConversationId.isEmpty()) return
        val conv = conversations.find { it.id == currentConversationId } ?: return
        conv.messages.clear()
        conv.messages.addAll(messagesList)
        saveConversations()
    }

    private fun saveConversations() {
        val prefs = getSharedPreferences(PREFS_NAME, MODE_PRIVATE)
        val jsonArray = JSONArray()
        conversations.forEach { conv ->
            val convObj = JSONObject().apply {
                put("id", conv.id)
                put("title", conv.title)
                put("timestamp", conv.timestamp)
                val messagesArray = JSONArray()
                conv.messages.forEach { msg ->
                    val msgObj = JSONObject().apply {
                        put("text", msg.text)
                        put("isBot", msg.isBot)
                        put("timestamp", msg.timestamp)
                    }
                    messagesArray.put(msgObj)
                }
                put("messages", messagesArray)
            }
            jsonArray.put(convObj)
        }
        prefs.edit().putString(CONVERSATIONS_KEY, jsonArray.toString()).apply()
    }

    private fun loadConversations() {
        val prefs = getSharedPreferences(PREFS_NAME, MODE_PRIVATE)
        val json = prefs.getString(CONVERSATIONS_KEY, null) ?: return
        try {
            val jsonArray = JSONArray(json)
            conversations.clear()
            for (i in 0 until jsonArray.length()) {
                val convObj = jsonArray.getJSONObject(i)
                val messagesArray = convObj.getJSONArray("messages")
                val messages = mutableListOf<ChatMessage>()
                for (j in 0 until messagesArray.length()) {
                    val msgObj = messagesArray.getJSONObject(j)
                    messages.add(ChatMessage(
                        text = msgObj.getString("text"),
                        isBot = msgObj.getBoolean("isBot"),
                        timestamp = msgObj.getString("timestamp")
                    ))
                }
                conversations.add(Conversation(
                    id = convObj.getString("id"),
                    title = convObj.getString("title"),
                    messages = messages,
                    timestamp = convObj.getLong("timestamp")
                ))
            }
            historyAdapter.notifyDataSetChanged()
        } catch (e: Exception) {
            // Ignore
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        saveCurrentConversation()
        tts.stop()
        tts.shutdown()
        responseCallback?.let {
            com.example.deliverybot.net.RosBridgeClient.unsubscribe("/app/chat/response", it)
        }
    }

    // Chat Message Data Class
    data class ChatMessage(val text: String, val isBot: Boolean, val timestamp: String)

    // Chat Adapter
    inner class ChatAdapter(private val messages: List<ChatMessage>) :
        RecyclerView.Adapter<RecyclerView.ViewHolder>() {

        private val VIEW_TYPE_USER = 1
        private val VIEW_TYPE_BOT = 2

        override fun getItemViewType(position: Int) =
            if (messages[position].isBot) VIEW_TYPE_BOT else VIEW_TYPE_USER

        override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): RecyclerView.ViewHolder {
            return if (viewType == VIEW_TYPE_BOT) {
                val view = LayoutInflater.from(parent.context)
                    .inflate(R.layout.item_bot_message, parent, false)
                BotViewHolder(view)
            } else {
                val view = LayoutInflater.from(parent.context)
                    .inflate(R.layout.item_user_message, parent, false)
                UserViewHolder(view)
            }
        }

        override fun onBindViewHolder(holder: RecyclerView.ViewHolder, position: Int) {
            val msg = messages[position]
            when (holder) {
                is BotViewHolder -> holder.bind(msg)
                is UserViewHolder -> holder.bind(msg)
            }
        }

        override fun getItemCount() = messages.size

        inner class BotViewHolder(itemView: View) : RecyclerView.ViewHolder(itemView) {
            private val textMessage: TextView = itemView.findViewById(R.id.textBotMessage)
            private val textTime: TextView = itemView.findViewById(R.id.textBotTime)
            fun bind(msg: ChatMessage) {
                textMessage.text = msg.text
                textTime.text = msg.timestamp
            }
        }

        inner class UserViewHolder(itemView: View) : RecyclerView.ViewHolder(itemView) {
            private val textMessage: TextView = itemView.findViewById(R.id.textUserMessage)
            private val textTime: TextView = itemView.findViewById(R.id.textUserTime)
            fun bind(msg: ChatMessage) {
                textMessage.text = msg.text
                textTime.text = msg.timestamp
            }
        }
    }

    // History Adapter
    inner class HistoryAdapter(
        private val items: MutableList<Conversation>,
        private val onClick: (Conversation) -> Unit,
        private val onDelete: (Conversation, Int) -> Unit
    ) : RecyclerView.Adapter<HistoryAdapter.ViewHolder>() {

        override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): ViewHolder {
            val view = LayoutInflater.from(parent.context)
                .inflate(R.layout.item_conversation, parent, false)
            return ViewHolder(view)
        }

        override fun onBindViewHolder(holder: ViewHolder, position: Int) {
            holder.bind(items[position], position)
        }

        override fun getItemCount() = items.size

        inner class ViewHolder(itemView: View) : RecyclerView.ViewHolder(itemView) {
            private val txtTitle: TextView = itemView.findViewById(R.id.txtConversationTitle)
            private val txtPreview: TextView = itemView.findViewById(R.id.txtConversationPreview)
            private val txtTime: TextView = itemView.findViewById(R.id.txtConversationTime)
            private val btnDelete: ImageButton = itemView.findViewById(R.id.btnDeleteConversation)

            fun bind(conv: Conversation, position: Int) {
                txtTitle.text = conv.title
                txtPreview.text = conv.messages.lastOrNull()?.text ?: "No messages"
                txtTime.text = getRelativeTime(conv.timestamp)
                itemView.setOnClickListener { onClick(conv) }
                btnDelete.setOnClickListener { onDelete(conv, position) }
            }

            private fun getRelativeTime(timestamp: Long): String {
                val diff = System.currentTimeMillis() - timestamp
                return when {
                    diff < 60000 -> "Just now"
                    diff < 3600000 -> "${diff / 60000} min ago"
                    diff < 86400000 -> "${diff / 3600000} hours ago"
                    else -> SimpleDateFormat("MMM dd", Locale.getDefault()).format(Date(timestamp))
                }
            }
        }
    }
}