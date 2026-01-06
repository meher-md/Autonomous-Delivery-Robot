package com.example.deliverybot

import android.annotation.SuppressLint
import android.os.Bundle
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Toast // Import for Toast messages
import androidx.appcompat.app.AppCompatActivity

class MapActivity : AppCompatActivity() {
    private lateinit var web: WebView

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // Get the ROS WebSocket URL from the project's configuration
        val wsUrl = ConnectionConfig.rosbridgeWs(this)

        web = WebView(this).apply {
            // Enable JavaScript for ROS communication and button functionality
            settings.javaScriptEnabled = true
            settings.cacheMode = WebSettings.LOAD_NO_CACHE
            settings.domStorageEnabled = true
            settings.useWideViewPort = true
            settings.loadWithOverviewMode = true
            try { settings.mixedContentMode = WebSettings.MIXED_CONTENT_ALWAYS_ALLOW } catch (_: Throwable) {}
            webViewClient = object : WebViewClient() {
                @SuppressLint("WebViewClientOnReceivedSslError")
                override fun onReceivedSslError(view: WebView, handler: android.webkit.SslErrorHandler, error: android.net.http.SslError) {
                    handler.proceed()
                }
            }
        }
        setContentView(web)

        // The full HTML content for the WebView, including the map and the new button
        val html = """
            <!doctype html>
            <html>
            <head>
              <meta name='viewport' content='width=device-width, initial-scale=1.0'>
              <style>
                /* Full screen fill and center content */
                html, body {
                  height: 100vh; width: 100vw;
                  margin: 0; background: #000;
                  display: flex; flex-direction: column; /* Use column layout */
                  align-items: center; justify-content: flex-end; /* Align content to the bottom */
                }
                /* Container for the map, taking up most of the screen */
                .map-wrap {
                  flex-grow: 1; /* Allows map container to take remaining space */
                  width: 100vw;
                  display: flex; align-items: center; justify-content: center;
                }
                /* Map Canvas */
                #c {
                  max-width: 90vw;
                  max-height: 80vh; /* Allow more height for the map */
                  width: auto; height: auto;
                  image-rendering: pixelated;
                  background: #111;
                }
                /* Style for the new button */
                #confirm-btn {
                  background-color: #4CAF50; /* Green color */
                  color: white;
                  padding: 15px 32px;
                  text-align: center;
                  text-decoration: none;
                  display: inline-block;
                  font-size: 16px;
                  margin: 20px 0; /* Margin above and below the button */
                  cursor: pointer;
                  border: none;
                  border-radius: 8px;
                  box-shadow: 0 4px 8px 0 rgba(0,0,0,0.2);
                  position: relative; /* Position relative to the flow */
                  z-index: 10; /* Ensure button is above map if they overlap */
                }
              </style>
            </head>
            <body>
              <div class="map-wrap"><canvas id="c"></canvas></div>
              
              <button id="confirm-btn">CONFIRM DELIVERY (LIKE GESTURE)</button>
              
              <script>
                const wsUrl = ${'"'}$wsUrl${'"'};
                const mapTopic = "/map";
                const controlTopic = "/delivery_commands"; // ROS topic to send the command to
                const commandPayload = "START_LIKE_DETECTION"; // The specific command to start the Python script

                const ws = new WebSocket(wsUrl.replace(/^http/i, "ws"));
                
                // ---------------- ROS MAP HANDLING LOGIC (Your existing code) ----------------
                ws.onopen = () => {
                    // Subscribe to the map topic
                    ws.send(JSON.stringify({op:"subscribe", topic: mapTopic, type:"nav_msgs/OccupancyGrid"}));
                    // Optional: Log connection status
                    console.log("ROS WebSocket connected and subscribed to map.");
                };
                
                ws.onmessage = (ev) => {
                  const m = JSON.parse(ev.data);
                  if (m.op !== "publish" || m.topic !== mapTopic) return;
                  const msg = m.msg, w = msg.info.width|0, h = msg.info.height|0;
                  const data = msg.data;
                  const c = document.getElementById("c");
                  if (c.width !== w || c.height !== h) { c.width = w; c.height = h; }
                  const ctx = c.getContext("2d");
                  const img = ctx.createImageData(w, h);
                  for (let y=0; y<h; y++) for (let x=0; x<w; x++) {
                    const v = data[y*w + x];
                    const g = (v < 0) ? 127 : Math.max(0, Math.min(255, 255 - Math.round(255*(v/100))));
                    const yy = (h-1-y), i = (yy*w + x)*4;
                    img.data[i]=g; img.data[i+1]=g; img.data[i+2]=g; img.data[i+3]=255;
                  }
                  ctx.putImageData(img, 0, 0);
                };
                // ---------------- END OF ROS MAP HANDLING LOGIC ----------------

                
                // ---------------- NEW BUTTON LOGIC ----------------
                document.getElementById('confirm-btn').addEventListener('click', () => {
                    // Create the ROS message to publish
                    const cmdMsg = {
                        op: "publish",
                        topic: controlTopic,
                        type: "std_msgs/String", // Assuming the command topic uses the standard String message type
                        msg: { data: commandPayload }
                    };

                    if (ws.readyState === WebSocket.OPEN) {
                        ws.send(JSON.stringify(cmdMsg));
                        console.log('Command Sent:', commandPayload, 'to', controlTopic);
                        alert("Gesture detection started. Please show the 'Like' sign to the robot's camera.");
                    } else {
                        console.error('WebSocket is not open. Cannot send command.');
                        alert("Error: Robot connection is not ready.");
                    }
                });
                // ---------------- END OF NEW BUTTON LOGIC ----------------

              </script>
            </body>
            </html>
        """.trimIndent()

        web.loadDataWithBaseURL(null, html, "text/html", "utf-8", null)
    }

    override fun onDestroy() { try { web.destroy() } catch (_: Throwable) {}; super.onDestroy() }
}