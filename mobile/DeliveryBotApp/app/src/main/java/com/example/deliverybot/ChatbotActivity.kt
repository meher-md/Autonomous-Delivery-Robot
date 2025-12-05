package com.example.deliverybot

import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.Button
import android.widget.EditText
import android.widget.ImageButton
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import java.text.SimpleDateFormat
import java.util.*

/**
 * Chatbot Activity - Intelligent Assistant for Autonomous Delivery Robot
 * HTI Mechatronics Engineering Graduation Project
 *
 * Features:
 * - Offline rule-based chatbot
 * - Smart context-aware responses
 * - Beautiful chat UI with message bubbles
 * - Automatic scrolling and timestamps
 */
class ChatbotActivity : AppCompatActivity() {

    // UI Components
    private lateinit var recyclerViewChat: RecyclerView
    private lateinit var editTextMessage: EditText
    private lateinit var btnSend: Button
    private lateinit var btnBack: ImageButton

    // Chat Components
    private lateinit var chatAdapter: ChatAdapter
    private val messagesList = mutableListOf<ChatMessage>()
    private val chatbotEngine = ChatbotEngine()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_chatbot)

        // Initialize UI components
        initializeViews()

        // Setup RecyclerView
        setupRecyclerView()

        // Setup click listeners
        setupListeners()

        // Show welcome message
        addBotMessage(chatbotEngine.getWelcomeMessage())
    }

    /**
     * Initialize all UI components
     */
    private fun initializeViews() {
        recyclerViewChat = findViewById(R.id.recyclerViewChat)
        editTextMessage = findViewById(R.id.editTextMessage)
        btnSend = findViewById(R.id.btnSend)
        btnBack = findViewById(R.id.btnBack)
    }

    /**
     * Setup RecyclerView with adapter and layout manager
     */
    private fun setupRecyclerView() {
        chatAdapter = ChatAdapter(messagesList)
        recyclerViewChat.apply {
            adapter = chatAdapter
            layoutManager = LinearLayoutManager(this@ChatbotActivity).apply {
                stackFromEnd = true // Start from bottom
            }
        }
    }

    /**
     * Setup all button click listeners
     */
    private fun setupListeners() {
        // Send button click
        btnSend.setOnClickListener {
            sendMessage()
        }

        // Back button click
        btnBack.setOnClickListener {
            finish()
        }

        // Send on Enter key (optional enhancement)
        editTextMessage.setOnEditorActionListener { _, _, _ ->
            sendMessage()
            true
        }
    }

    /**
     * Send user message and get bot response
     */
    private fun sendMessage() {
        val messageText = editTextMessage.text.toString().trim()

        // Check if message is not empty
        if (messageText.isEmpty()) {
            return
        }

        // Add user message
        addUserMessage(messageText)

        // Clear input field
        editTextMessage.text.clear()

        // Get bot response (with slight delay for natural feel)
        recyclerViewChat.postDelayed({
            val botResponse = chatbotEngine.getResponse(messageText)
            addBotMessage(botResponse)
        }, 500) // 500ms delay
    }

    /**
     * Add user message to chat
     */
    private fun addUserMessage(message: String) {
        val chatMessage = ChatMessage(
            text = message,
            isBot = false,
            timestamp = getCurrentTime()
        )
        messagesList.add(chatMessage)
        chatAdapter.notifyItemInserted(messagesList.size - 1)
        scrollToBottom()
    }

    /**
     * Add bot message to chat
     */
    private fun addBotMessage(message: String) {
        val chatMessage = ChatMessage(
            text = message,
            isBot = true,
            timestamp = getCurrentTime()
        )
        messagesList.add(chatMessage)
        chatAdapter.notifyItemInserted(messagesList.size - 1)
        scrollToBottom()
    }

    /**
     * Scroll RecyclerView to bottom (latest message)
     */
    private fun scrollToBottom() {
        if (messagesList.isNotEmpty()) {
            recyclerViewChat.smoothScrollToPosition(messagesList.size - 1)
        }
    }

    /**
     * Get current time as formatted string
     */
    private fun getCurrentTime(): String {
        val dateFormat = SimpleDateFormat("hh:mm a", Locale.getDefault())
        return dateFormat.format(Date())
    }

    /**
     * Data class for chat messages
     */
    data class ChatMessage(
        val text: String,
        val isBot: Boolean,
        val timestamp: String
    )

    /**
     * RecyclerView Adapter for chat messages
     */
    inner class ChatAdapter(private val messages: List<ChatMessage>) :
        RecyclerView.Adapter<RecyclerView.ViewHolder>() {

        private val VIEW_TYPE_USER = 1
        private val VIEW_TYPE_BOT = 2

        override fun getItemViewType(position: Int): Int {
            return if (messages[position].isBot) VIEW_TYPE_BOT else VIEW_TYPE_USER
        }

        override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): RecyclerView.ViewHolder {
            return if (viewType == VIEW_TYPE_BOT) {
                val view = LayoutInflater.from(parent.context)
                    .inflate(R.layout.item_bot_message, parent, false)
                BotMessageViewHolder(view)
            } else {
                val view = LayoutInflater.from(parent.context)
                    .inflate(R.layout.item_user_message, parent, false)
                UserMessageViewHolder(view)
            }
        }

        override fun onBindViewHolder(holder: RecyclerView.ViewHolder, position: Int) {
            val message = messages[position]
            if (holder is BotMessageViewHolder) {
                holder.bind(message)
            } else if (holder is UserMessageViewHolder) {
                holder.bind(message)
            }
        }

        override fun getItemCount(): Int = messages.size

        /**
         * ViewHolder for bot messages
         */
        inner class BotMessageViewHolder(itemView: View) : RecyclerView.ViewHolder(itemView) {
            private val textMessage: TextView = itemView.findViewById(R.id.textBotMessage)
            private val textTime: TextView = itemView.findViewById(R.id.textBotTime)

            fun bind(message: ChatMessage) {
                textMessage.text = message.text
                textTime.text = message.timestamp
            }
        }

        /**
         * ViewHolder for user messages
         */
        inner class UserMessageViewHolder(itemView: View) : RecyclerView.ViewHolder(itemView) {
            private val textMessage: TextView = itemView.findViewById(R.id.textUserMessage)
            private val textTime: TextView = itemView.findViewById(R.id.textUserTime)

            fun bind(message: ChatMessage) {
                textMessage.text = message.text
                textTime.text = message.timestamp
            }
        }
    }
}