#!/bin/bash
echo "🤖 Delivery Bot Dependency Installer"
echo "===================================="

# 1. Update System
echo "[1/4] Updating Apt..."
sudo apt-get update

# 2. Install ROS Dependencies (rosdep)
echo "[2/4] Installing ROS System Dependencies..."
if ! command -v rosdep &> /dev/null; then
    sudo apt-get install -y python3-rosdep
    sudo rosdep init
    rosdep update
fi

# Install dependencies for all packages in src
rosdep install --from-paths src --ignore-src -r -y

# 3. Install Python Dependencies
echo "[3/4] Installing Python Libraries..."
pip3 install -r requirements.txt

# 4. Optional: Yasmin Web Client Warning
echo "[4/4] Checking Yasmin Viewer..."
YASMIN_BUILD_DIR="src/App/chatbot/yasmin/yasmin_viewer/yasmin_viewer_web_client/build"
if [ ! -d "$YASMIN_BUILD_DIR" ]; then
    echo "⚠️  Yasmin Viewer Web Client missing (Expected)."
    echo "   The system will work, but if you want the visual editor, run:"
    echo "   cd src/App/chatbot/yasmin/yasmin_viewer/yasmin_viewer_web_client && npm install && npm run build"
else
    echo "✅ Yasmin Viewer Web Client found."
fi

echo "===================================="
echo "✅ Installation Complete! Please run 'colcon build' now."
