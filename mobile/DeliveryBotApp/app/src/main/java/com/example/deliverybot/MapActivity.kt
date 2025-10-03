package com.example.deliverybot

import android.annotation.SuppressLint
import android.os.Bundle
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.appcompat.app.AppCompatActivity

class MapActivity : AppCompatActivity() {
    private lateinit var web: WebView

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        val wsUrl = ConnectionConfig.rosbridgeWs(this)

        web = WebView(this).apply {
            settings.javaScriptEnabled = true
            settings.cacheMode = WebSettings.LOAD_NO_CACHE
            settings.domStorageEnabled = true
            settings.useWideViewPort = true
            settings.loadWithOverviewMode = true
            try { settings.mixedContentMode = WebSettings.MIXED_CONTENT_ALWAYS_ALLOW } catch (_: Throwable) {}
            webViewClient = WebViewClient()
        }
        setContentView(web)

        val html = """
            <!doctype html>
            <html>
            <head>
              <meta name='viewport' content='width=device-width, initial-scale=1.0'>
              <style>
                /* ملء الشاشة بالكامل وتوسيط المحتوى */
                html, body {
                  height: 100vh; width: 100vw;
                  margin: 0; background: #000;
                  display: flex; align-items: center; justify-content: center;
                }
                /* صندوق يحتفظ بنصف الارتفاع */
                .wrap {
                  height: 50vh; width: 100vw;
                  display: flex; align-items: center; justify-content: center;
                }
                /* كانفس الماب */
                #c {
                  max-width: 90vw;      /* مسافة جانبية صغيرة */
                  max-height: 50vh;     /* نصف الشاشة */
                  width: auto; height: auto;
                  image-rendering: pixelated;
                  background: #111;
                }
              </style>
            </head>
            <body>
              <div class="wrap"><canvas id="c"></canvas></div>
              <script>
                const wsUrl = ${'"'}$wsUrl${'"'};
                const topic = "/map";
                const ws = new WebSocket(wsUrl.replace(/^http/i, "ws"));
                ws.onopen = () => ws.send(JSON.stringify({op:"subscribe", topic, type:"nav_msgs/OccupancyGrid"}));
                ws.onmessage = (ev) => {
                  const m = JSON.parse(ev.data);
                  if (m.op !== "publish" || m.topic !== topic) return;
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
              </script>
            </body>
            </html>
        """.trimIndent()

        web.loadDataWithBaseURL(null, html, "text/html", "utf-8", null)
    }

    override fun onDestroy() { try { web.destroy() } catch (_: Throwable) {}; super.onDestroy() }
}
