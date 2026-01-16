package com.example.deliverybot

import android.content.Context
import android.content.res.AssetManager
import android.media.AudioAttributes
import android.media.AudioFormat
import android.media.AudioTrack
import android.util.Log
import com.k2fsa.sherpa.onnx.OfflineTts
import com.k2fsa.sherpa.onnx.OfflineTtsConfig
import com.k2fsa.sherpa.onnx.OfflineTtsModelConfig
import com.k2fsa.sherpa.onnx.OfflineTtsVitsModelConfig
import java.io.BufferedInputStream
import java.io.File
import java.io.FileOutputStream
import java.io.IOException
import java.net.URL
// Removed: TarInputStream unused
import org.apache.commons.compress.compressors.bzip2.BZip2CompressorInputStream

object OfflineTtsEngine {
    private const val TAG = "OfflineTtsEngine"
    
    // Dual engines - both preloaded at startup
    private var ttsMale: OfflineTts? = null
    private var ttsFemale: OfflineTts? = null
    private var activeEngine: OfflineTts? = null
    private var currentVoice = "male" // Default to Rafiq
    
    private var audioTrack: AudioTrack? = null

    // Only 2 models: Rafiq (male) and Rafiqa (female)
    val ASSET_EN_FEMALE = "model-en-female"  // Rafiqa
    val ASSET_EN_MALE = "model-en-male"      // Rafiq

    fun getSafeEngine(): OfflineTts? = activeEngine
    fun isInitialized() = ttsMale != null || ttsFemale != null
    
    /**
     * Preload BOTH voices at startup for instant switching.
     * Call this in MainActivity.onCreate() or ChatbotActivity.onCreate()
     */
    fun preloadBoth(context: Context, onComplete: (() -> Unit)? = null) {
        if (ttsMale != null && ttsFemale != null) {
            Log.d(TAG, "Both engines already loaded, skipping")
            activeEngine = if (currentVoice == "female") ttsFemale else ttsMale
            onComplete?.invoke()
            return
        }
        
        Thread {
            try {
                Log.d(TAG, "Loading BOTH voices (Ryan + Amy)...")
                
                // Load male (Rafiq/Ryan)
                ttsMale = createTts(context, ASSET_EN_MALE)
                Log.d(TAG, "Male voice loaded: ${ttsMale != null}")
                
                // Load female (Rafiqa/Amy)
                ttsFemale = createTts(context, ASSET_EN_FEMALE)
                Log.d(TAG, "Female voice loaded: ${ttsFemale != null}")
                
                // Set default active engine
                activeEngine = if (currentVoice == "female") ttsFemale else ttsMale
                
                Log.d(TAG, "Both voices preloaded! Ready for instant switching.")
                onComplete?.invoke()
            } catch (e: Exception) {
                Log.e(TAG, "Failed to preload voices", e)
            }
        }.start()
    }
    
    /**
     * Instantly switch active voice (no loading, just pointer change)
     */
    fun setActiveVoice(voice: String) {
        currentVoice = voice
        activeEngine = if (voice == "female") ttsFemale else ttsMale
        Log.d(TAG, "Switched to $voice voice (instant)")
    }

    // Legacy method for compatibility
    fun loadPersona(context: Context, modelEn: String, modelAr: String, onComplete: (() -> Unit)? = null) {
        val voice = if (modelEn == ASSET_EN_FEMALE) "female" else "male"
        setActiveVoice(voice)
        // If not preloaded yet, do it now
        if (activeEngine == null) {
            preloadBoth(context, onComplete)
        } else {
            onComplete?.invoke()
        }
    }

    private fun createTts(context: Context, modelName: String): OfflineTts? {
        val modelDir = getModelPath(context, modelName) ?: return null
        
        // Robust search for valid model directory (containing .onnx and tokens.txt)
        val targetDir = findValidModelDir(modelDir)
        if (targetDir == null) {
             Log.e(TAG, "Could not find valid model (onnx + tokens.txt) in ${modelDir.absolutePath}")
             return null
        }
        
        val onnxFile = findOnnxFile(targetDir)
        if (onnxFile == null) return null // Should not happen if findValidModelDir worked
        
        if (onnxFile == null) {
            Log.e(TAG, "No ONNX file found for $modelName in ${modelDir.absolutePath}")
            return null
        }

        return createTtsFromDir(targetDir.absolutePath, onnxFile.name)
    }
    
    private fun findOnnxFile(dir: File): File? {
        return dir.listFiles()?.find { it.name.endsWith(".onnx", true) }
    }
    
    private fun findValidModelDir(root: File): File? {
        val files = root.listFiles() ?: return null
        
        // Check current
        val hasOnnx = files.any { it.name.endsWith(".onnx", true) }
        val hasTokens = files.any { it.name == "tokens.txt" }
        if (hasOnnx && hasTokens) return root
        
        // Check subdirs
        for (f in files) {
            if (f.isDirectory) {
                val result = findValidModelDir(f)
                if (result != null) return result
            }
        }
        return null
    }

    private fun createTtsFromDir(dirPath: String, onnxFileName: String): OfflineTts? {
         val modelFile = File(dirPath, onnxFileName)
         val tokensFile = File(dirPath, "tokens.txt")
         
         if (!modelFile.exists() || !tokensFile.exists()) {
             Log.e(TAG, "Missing model files in $dirPath. Model: ${modelFile.exists()}, Tokens: ${tokensFile.exists()}")
             return null
         }

         val config = OfflineTtsConfig(
            model = OfflineTtsModelConfig(
                vits = OfflineTtsVitsModelConfig(
                    model = modelFile.absolutePath,
                    tokens = tokensFile.absolutePath,
                    dataDir = "$dirPath/espeak-ng-data"
                ),
                numThreads = 6,
                debug = false,
                provider = "cpu"
            )
        )
        return OfflineTts(config = config)
    }

    fun speak(text: String, speed: Float = 1.0f, pitch: Float = 1.0f) {
        Thread {
            try {
                // Use the active engine (either Rafiq or Rafiqa)
                val safeEngine = activeEngine ?: return@Thread
                
                val sid = 0 // Speaker ID
                val audio = safeEngine.generate(text, sid = sid, speed = speed)
                
                if (audio.samples.isNotEmpty()) {
                    playAudio(audio.samples, audio.sampleRate)
                }
            } catch (e: Exception) {
                Log.e(TAG, "Error synthesizing: $text", e)
            }
        }.start()
    }
    
    fun stop() {
        try {
            audioTrack?.pause()
            audioTrack?.flush()
        } catch (e: Exception) {}
    }

    // --- Asset & Storage Management ---

    fun isModelInstalled(context: Context, modelId: String): Boolean {
        return File(context.filesDir, "voices/$modelId").exists()
    }
    
    fun deleteModel(context: Context, modelId: String) {
        val dir = File(context.filesDir, "voices/$modelId")
        if (dir.exists()) dir.deleteRecursively()
    }

    // Prioritize FilesDir (Downloads), then Assets (Bundled)
    private fun getModelPath(context: Context, modelName: String): File? {
        // 1. Check Custom Storage (Downloads)
        val customDir = File(context.filesDir, "voices/$modelName")
        if (customDir.exists()) return customDir
        
        // 2. Check Assets (Bundled/Cache)
        // Sherpa needs Files, cannot read from Assets directly
        return copyAssets(context, "sherpa/$modelName")
    }

    private fun copyAssets(context: Context, path: String): File? {
        val assetManager = context.assets
        val targetDir = File(context.filesDir, "sherpa_cache/${File(path).name}")
        if (targetDir.exists()) return targetDir // Already copied
        targetDir.mkdirs()
        
        try {
            val files = assetManager.list(path) ?: return null
            for (filename in files) {
                 val inFile = "$path/$filename"
                 val outFile = File(targetDir, filename)
                 // Simple Copy
                 assetManager.open(inFile).use { input ->
                     FileOutputStream(outFile).use { output ->
                         input.copyTo(output)
                     }
                 }
            }
        } catch (e: IOException) {
            Log.e(TAG, "Asset missing: $path")
            return null
        }
        return targetDir
    }

    private fun playAudio(samples: FloatArray, sampleRate: Int) {
        val buffer = ShortArray(samples.size)
        for (i in samples.indices) {
            var s = samples[i]
            if (s > 1.0f) s = 1.0f
            if (s < -1.0f) s = -1.0f
            buffer[i] = (s * 32767).toInt().toShort()
        }

        val minBufferSize = AudioTrack.getMinBufferSize(sampleRate, AudioFormat.CHANNEL_OUT_MONO, AudioFormat.ENCODING_PCM_16BIT)
        if (audioTrack == null || audioTrack?.sampleRate != sampleRate) {
            audioTrack?.release()
            audioTrack = AudioTrack.Builder()
                .setAudioAttributes(AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_MEDIA).setContentType(AudioAttributes.CONTENT_TYPE_SPEECH).build())
                .setAudioFormat(AudioFormat.Builder().setEncoding(AudioFormat.ENCODING_PCM_16BIT).setSampleRate(sampleRate).setChannelMask(AudioFormat.CHANNEL_OUT_MONO).build())
                .setBufferSizeInBytes(maxOf(minBufferSize, buffer.size * 2))
                .setTransferMode(AudioTrack.MODE_STREAM)
                .build()
        }
        audioTrack?.play()
        audioTrack?.write(buffer, 0, buffer.size)
    }
}
