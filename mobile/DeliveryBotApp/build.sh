#!/bin/bash

# إعداد البيئة
export JAVA_HOME="/usr/lib/jvm/java-17-openjdk-amd64"
export ANDROID_SDK_ROOT="${ANDROID_SDK_ROOT:-$HOME/Android/Sdk}"
export PATH="$ANDROID_SDK_ROOT/platform-tools:$ANDROID_SDK_ROOT/cmdline-tools/latest/bin:$ANDROID_SDK_ROOT/tools/bin:$PATH"

# قبول الترخيص
yes | sdkmanager --licenses >/dev/null 2>&1 || true
sdkmanager "platform-tools" "platforms;android-34" "build-tools;34.0.0" >/dev/null 2>&1 || true

# إعادة بناء التطبيق
./gradlew --no-daemon clean assembleDebug
