package com.example.deliverybot

/**
 * Intelligent Chatbot Engine for Autonomous Delivery Robot
 * HTI Mechatronics Engineering Graduation Project
 *
 * This engine provides offline, rule-based responses about:
 * - Robot capabilities and features
 * - App usage instructions
 * - Team and project information
 * - Technical details about ROS 2 implementation
 */
class ChatbotEngine {

    // Response categories for intelligent matching
    private data class BotResponse(
        val keywords: List<String>,
        val response: String,
        val priority: Int = 1
    )

    private val responses = listOf(
        // Greetings and Introduction
        BotResponse(
            keywords = listOf("hello", "hi", "hey", "greetings", "good morning", "good evening"),
            response = "Hello! 👋 I'm your Autonomous Delivery Robot assistant. I'm here to help you with:\n\n" +
                    "📱 App features and usage\n" +
                    "🤖 Robot capabilities\n" +
                    "🗺️ Navigation and mapping\n" +
                    "📦 Order management\n" +
                    "⚙️ Technical information\n\n" +
                    "What would you like to know?",
            priority = 2
        ),

        // About the Project
        BotResponse(
            keywords = listOf("project", "graduation", "team", "hti", "about"),
            response = "🎓 **HTI Mechatronics Graduation Project**\n\n" +
                    "This is an Autonomous Mobile Delivery Robot developed by Mechatronics Engineering students from Higher Technological Institute.\n\n" +
                    "🔧 **Technology Stack:**\n" +
                    "• ROS 2 Humble framework\n" +
                    "• SLAM for mapping & localization\n" +
                    "• Autonomous navigation\n" +
                    "• Android mobile application\n" +
                    "• Real-time communication via WebSocket\n\n" +
                    "Our goal is to create a reliable, autonomous delivery solution!",
            priority = 2
        ),

        // About the Robot
        BotResponse(
            keywords = listOf("robot", "autonomous", "delivery", "capabilities", "what can"),
            response = "🤖 **Autonomous Delivery Robot**\n\n" +
                    "Our robot is designed for autonomous package delivery with these capabilities:\n\n" +
                    "✅ **Autonomous Navigation** - Moves independently to destinations\n" +
                    "✅ **SLAM Mapping** - Creates and updates maps in real-time\n" +
                    "✅ **Obstacle Avoidance** - Safely navigates around obstacles\n" +
                    "✅ **Live Camera Feed** - Real-time video streaming\n" +
                    "✅ **Remote Control** - Manual teleop when needed\n" +
                    "✅ **Order Tracking** - Complete delivery management\n\n" +
                    "Built on the Andino platform with ROS 2 Humble!",
            priority = 3
        ),

        // App Features Overview
        BotResponse(
            keywords = listOf("app", "features", "application", "what can i do", "functions"),
            response = "📱 **App Features:**\n\n" +
                    "🗺️ **Map Viewer** - Visualize SLAM maps in real-time\n" +
                    "📹 **Camera Stream** - Live video feed from robot\n" +
                    "🎮 **Teleop Control** - Manual robot control\n" +
                    "📦 **Order Management** - Create and track deliveries\n" +
                    "⚙️ **Settings** - Customize app preferences\n" +
                    "🔌 **Robot Connection** - WebSocket via ROSBridge\n\n" +
                    "Which feature would you like to learn more about?",
            priority = 2
        ),

        // Map and Navigation
        BotResponse(
            keywords = listOf("map", "mapping", "slam", "navigate", "navigation", "location"),
            response = "🗺️ **Mapping & Navigation:**\n\n" +
                    "The robot uses **SLAM (Simultaneous Localization and Mapping)** to:\n\n" +
                    "1. **Create Maps** - Builds environment maps autonomously\n" +
                    "2. **Localize** - Knows its exact position\n" +
                    "3. **Navigate** - Plans optimal paths to destinations\n" +
                    "4. **Update** - Continuously refines maps\n\n" +
                    "📍 **In the App:**\n" +
                    "• View real-time map updates\n" +
                    "• See robot's current position\n" +
                    "• Monitor navigation progress\n\n" +
                    "Open 'Map Viewer' to see it in action!",
            priority = 2
        ),

        // Camera Feature
        BotResponse(
            keywords = listOf("camera", "video", "stream", "feed", "watch", "see"),
            response = "📹 **Live Camera Stream:**\n\n" +
                    "View real-time video from the robot's camera:\n\n" +
                    "✅ High-quality video feed\n" +
                    "✅ Low latency streaming\n" +
                    "✅ Monitor robot's view\n" +
                    "✅ Useful for supervision\n\n" +
                    "📱 **How to Use:**\n" +
                    "1. Ensure robot is connected\n" +
                    "2. Tap 'Camera Stream' button\n" +
                    "3. Wait for stream to load\n" +
                    "4. View robot's perspective\n\n" +
                    "Perfect for monitoring deliveries!",
            priority = 2
        ),

        // Teleop Control
        BotResponse(
            keywords = listOf("control", "teleop", "drive", "move", "manual", "joystick"),
            response = "🎮 **Manual Control (Teleop):**\n\n" +
                    "Take manual control of the robot when needed:\n\n" +
                    "⬆️ **Forward** - Move robot ahead\n" +
                    "⬇️ **Backward** - Move robot back\n" +
                    "⬅️ **Turn Left** - Rotate left\n" +
                    "➡️ **Turn Right** - Rotate right\n" +
                    "⏹️ **Stop** - Emergency stop\n\n" +
                    "📱 **How to Use:**\n" +
                    "1. Open 'Teleop Control'\n" +
                    "2. Ensure robot is connected\n" +
                    "3. Use arrow buttons to control\n" +
                    "4. Robot responds in real-time\n\n" +
                    "⚠️ Use carefully in manual mode!",
            priority = 2
        ),

        // Orders and Delivery
        BotResponse(
            keywords = listOf("order", "delivery", "package", "deliver", "send", "create order"),
            response = "📦 **Order Management:**\n\n" +
                    "Create and manage delivery orders:\n\n" +
                    "**Creating New Order:**\n" +
                    "1. Tap 'Create New Order'\n" +
                    "2. Enter delivery address\n" +
                    "3. Add order details\n" +
                    "4. Confirm order\n" +
                    "5. Robot navigates autonomously!\n\n" +
                    "**Order History:**\n" +
                    "• View all past deliveries\n" +
                    "• Check order status\n" +
                    "• Track completion times\n\n" +
                    "📍 Robot automatically navigates to the destination!",
            priority = 2
        ),

        // Connection and Setup
        BotResponse(
            keywords = listOf("connect", "connection", "setup", "rosbridge", "websocket", "link"),
            response = "🔌 **Robot Connection:**\n\n" +
                    "The app connects to the robot via **WebSocket (ROSBridge)**:\n\n" +
                    "**Connection Process:**\n" +
                    "1. Robot runs ROSBridge server\n" +
                    "2. App connects via WebSocket\n" +
                    "3. Real-time bidirectional communication\n" +
                    "4. Send commands & receive data\n\n" +
                    "**Connection Status:**\n" +
                    "• 🟢 Green = Connected\n" +
                    "• 🔴 Red = Disconnected\n\n" +
                    "**Troubleshooting:**\n" +
                    "• Check robot is powered on\n" +
                    "• Verify network connection\n" +
                    "• Ensure ROSBridge is running\n" +
                    "• Check IP address in settings",
            priority = 2
        ),

        // Settings
        BotResponse(
            keywords = listOf("settings", "preferences", "dark mode", "theme", "customize", "configure"),
            response = "⚙️ **App Settings:**\n\n" +
                    "Customize your app experience:\n\n" +
                    "🌙 **Dark Mode** - Toggle dark/light theme\n" +
                    "🔔 **Notifications** - Enable/disable alerts\n" +
                    "🔌 **Connection** - Configure robot IP\n" +
                    "📊 **Display** - Adjust UI preferences\n\n" +
                    "📱 **How to Access:**\n" +
                    "1. Tap menu icon (≡)\n" +
                    "2. Select 'Settings'\n" +
                    "3. Adjust preferences\n" +
                    "4. Changes apply immediately\n\n" +
                    "Your preferences are saved automatically!",
            priority = 2
        ),

        // ROS 2 and Technical
        BotResponse(
            keywords = listOf("ros", "ros2", "humble", "packages", "andino", "technical", "how it works"),
            response = "⚙️ **Technical Details:**\n\n" +
                    "**ROS 2 Humble Framework:**\n\n" +
                    "📦 **Key Packages:**\n" +
                    "• **andino** - Base robot platform\n" +
                    "• **deliverybot_bringup** - Launch configurations\n" +
                    "• **app** - Custom ROS nodes\n" +
                    "• **andino_gz** - Gazebo simulation\n\n" +
                    "🔧 **Components:**\n" +
                    "• SLAM for mapping\n" +
                    "• Nav2 for autonomous navigation\n" +
                    "• ROSBridge for app communication\n" +
                    "• Camera drivers for video\n\n" +
                    "🐧 Running on Linux with ROS 2 Humble!",
            priority = 2
        ),

        // How to Use App
        BotResponse(
            keywords = listOf("how to use", "tutorial", "guide", "help", "start", "begin"),
            response = "📚 **Getting Started Guide:**\n\n" +
                    "**Step 1: Connection**\n" +
                    "• Ensure robot is powered on\n" +
                    "• Connect to same network\n" +
                    "• App auto-connects via ROSBridge\n\n" +
                    "**Step 2: Monitor**\n" +
                    "• View map in 'Map Viewer'\n" +
                    "• Check camera feed\n" +
                    "• Monitor robot status\n\n" +
                    "**Step 3: Control**\n" +
                    "• Create delivery orders OR\n" +
                    "• Use manual teleop control\n\n" +
                    "**Step 4: Track**\n" +
                    "• Monitor delivery progress\n" +
                    "• View order history\n\n" +
                    "Need help with a specific feature? Just ask!",
            priority = 2
        ),

        // Troubleshooting
        BotResponse(
            keywords = listOf("problem", "issue", "error", "not working", "fix", "troubleshoot", "help"),
            response = "🔧 **Troubleshooting:**\n\n" +
                    "**Common Issues:**\n\n" +
                    "❌ **Can't Connect:**\n" +
                    "• Check robot is powered on\n" +
                    "• Verify same WiFi network\n" +
                    "• Restart ROSBridge server\n" +
                    "• Check IP address in settings\n\n" +
                    "❌ **No Map Display:**\n" +
                    "• Ensure SLAM is running\n" +
                    "• Check map topic is published\n" +
                    "• Verify connection status\n\n" +
                    "❌ **Camera Not Working:**\n" +
                    "• Check camera is connected\n" +
                    "• Verify video topic\n" +
                    "• Restart camera node\n\n" +
                    "Still having issues? Check robot logs!",
            priority = 2
        ),

        // Thanks and Goodbye
        BotResponse(
            keywords = listOf("thank", "thanks", "appreciate", "helpful"),
            response = "You're welcome! 😊 I'm happy to help!\n\n" +
                    "Feel free to ask me anything about:\n" +
                    "• Using the app\n" +
                    "• Robot features\n" +
                    "• Technical details\n" +
                    "• Project information\n\n" +
                    "Good luck with your delivery! 🚀",
            priority = 1
        ),

        BotResponse(
            keywords = listOf("bye", "goodbye", "see you", "exit", "quit"),
            response = "Goodbye! 👋 Come back anytime you need help!\n\n" +
                    "Have a great day with your Autonomous Delivery Robot! 🤖📦",
            priority = 1
        ),

        // Default/Fallback Response
        BotResponse(
            keywords = listOf(""),
            response = "I'm here to help! 🤖\n\n" +
                    "I can answer questions about:\n\n" +
                    "🗺️ Mapping and navigation\n" +
                    "📹 Camera streaming\n" +
                    "🎮 Robot control\n" +
                    "📦 Order management\n" +
                    "⚙️ Technical details\n" +
                    "🎓 Project information\n\n" +
                    "What would you like to know?",
            priority = 0
        )
    )

    /**
     * Get welcome message shown when chat starts
     */
    fun getWelcomeMessage(): String {
        return "👋 **Welcome to Autonomous Delivery Robot Assistant!**\n\n" +
                "🎓 **HTI Mechatronics Graduation Project**\n\n" +
                "I'm your intelligent assistant for the Autonomous Mobile Delivery Robot. " +
                "I can help you with everything related to our robot and this app!\n\n" +
                "🤖 **About Our Robot:**\n" +
                "• Autonomous navigation\n" +
                "• Real-time SLAM mapping\n" +
                "• Live camera streaming\n" +
                "• Package delivery system\n\n" +
                "💬 **Ask Me About:**\n" +
                "• How to use app features\n" +
                "• Robot capabilities\n" +
                "• Navigation & mapping\n" +
                "• Creating orders\n" +
                "• Technical details\n\n" +
                "Feel free to ask me anything! 😊"
    }

    /**
     * Get intelligent response based on user message
     * Uses keyword matching with priority scoring
     */
    fun getResponse(userMessage: String): String {
        val message = userMessage.lowercase().trim()

        // Empty message handling
        if (message.isEmpty()) {
            return "Please type a message! I'm here to help. 😊"
        }

        // Find best matching response
        var bestMatch: BotResponse? = null
        var highestScore = 0

        for (response in responses) {
            var score = 0

            // Calculate match score based on keywords
            for (keyword in response.keywords) {
                if (message.contains(keyword)) {
                    score += response.priority
                }
            }

            // Update best match if this score is higher
            if (score > highestScore) {
                highestScore = score
                bestMatch = response
            }
        }

        // Return best match or default response
        return bestMatch?.response ?: responses.last().response
    }

    /**
     * Get suggested questions user might ask
     */
    fun getSuggestedQuestions(): List<String> {
        return listOf(
            "What can this robot do?",
            "How do I create an order?",
            "Show me app features",
            "How does navigation work?",
            "Tell me about the project",
            "How to use teleop control?",
            "What is SLAM?",
            "Camera not working"
        )
    }
}