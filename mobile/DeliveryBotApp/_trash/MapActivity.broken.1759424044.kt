package com.example.deliverybot

import android.annotation.SuppressLint
import android.graphics.Color
import android.os.Bundle
<<<<<<< HEAD
import android.widget.ImageView
import androidx.appcompat.app.AppCompatActivity

class MapActivity : AppCompatActivity() {
=======
import android.view.View
import android.webkit.WebChromeClient
import android.webkit.WebResourceRequest
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.FrameLayout
import androidx.appcompat.app.AppCompatActivity

class MapActivity : AppCompatActivity() {
    private lateinit var web: WebView
    private lateinit var root: FrameLayout
>>>>>>> 0bea46c (backup before replacing 5000)

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
<<<<<<< HEAD
        setContentView(R.layout.activity_map)

        // مجرد ربط ImageView عشان نتأكد إنه شغال (بدون تحديثات)
        val img = findViewById<ImageView>(R.id.mapView)
        // لو عايز تحط بلايسهولدر محلي:
        // img.setImageResource(R.drawable.ic_launcher_foreground)
=======

        // UI بسيط في الكود (من غير XML)
        root = FrameLayout(this).apply {
            setBackgroundColor(Color.BLACK)
        }
        web = WebView(this)
        root.addView(web, FrameLayout.LayoutParams(
            FrameLayout.LayoutParams.MATCH_PARENT,
            FrameLayout.LayoutParams.MATCH_PARENT
        ))
        setContentView(root)

        val s: WebSettings = web.settings
        s.javaScriptEnabled = true
        s.domStorageEnabled = true
        s.databaseEnabled = true
        s.loadWithOverviewMode = true
        s.useWideViewPort = true
        s.builtInZoomControls = true
        s.displayZoomControls = false
        s.mixedContentMode = WebSettings.MIXED_CONTENT_ALWAYS_ALLOW
        s.mediaPlaybackRequiresUserGesture = false

        web.webChromeClient = WebChromeClient()
        web.webViewClient = object : WebViewClient() {
            override fun shouldOverrideUrlLoading(
                view: WebView?, request: WebResourceRequest?
            ): Boolean {
                // خليك جوّه الـ WebView
                return false
            }
        }

        // حمّل صفحة السيرفر على الروبوت (بيتبني من SharedPreferences عبر ConnectionConfig)
        val base = ConnectionConfig.apiBase(this) // http://<host>:5000
        val url  = intent.getStringExtra("url") ?: "$base/"
        web.loadUrl(url)
    }

    override fun onBackPressed() {
        if (::web.isInitialized && web.canGoBack()) web.goBack() else super.onBackPressed()
    }

    override fun onDestroy() {
        try { if (::web.isInitialized) { web.loadUrl("about:blank"); web.destroy() } } catch (_:Throwable) {}
        super.onDestroy()
>>>>>>> 0bea46c (backup before replacing 5000)
    }
}
