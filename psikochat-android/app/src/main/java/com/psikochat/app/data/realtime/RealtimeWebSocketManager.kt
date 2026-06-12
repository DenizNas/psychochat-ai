package com.psikochat.app.data.realtime

import android.util.Log
import com.psikochat.app.data.local.TokenManager
import com.psikochat.app.BuildConfig
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.*
import okhttp3.*
import org.json.JSONObject
import java.util.concurrent.TimeUnit

/**
 * Real-Time WebSocket Manager
 * ===========================
 * OkHttp tabanlı WebSocket istemcisi.
 *
 * Özellikler:
 * - JWT token handshake (query param)
 * - Exponential backoff ile reconnect (BackoffCalculator)
 * - 4001 auth hatası → tekrar deneme yapılmaz; REST fallback devreye girer
 * - Typing indicator (raw mesaj içermez, privacy-safe)
 * - Event callback'leri Flow ile iletilir
 * - Token, raw chat text, password loglanmaz
 */
class RealtimeWebSocketManager(
    private val tokenManager: TokenManager,
    private val scope: CoroutineScope,
) {
    companion object {
        private const val TAG = "RealtimeWS"
        private const val WS_PATH = "/ws/chat"
    }

    // ─── Public State Flows ────────────────────────────────────────────────
    private val _connectionState = MutableStateFlow<ConnectionState>(ConnectionState.Disconnected)
    val connectionState: StateFlow<ConnectionState> = _connectionState.asStateFlow()

    /** Sunucudan gelen chat_response event'leri. */
    private val _incomingEvents = MutableSharedFlow<WsEvent>(extraBufferCapacity = 32)
    val incomingEvents: SharedFlow<WsEvent> = _incomingEvents.asSharedFlow()

    // ─── Internal ─────────────────────────────────────────────────────────
    private var webSocket: WebSocket? = null
    private var reconnectJob: Job? = null
    private var reconnectAttempt = 0

    private val client = OkHttpClient.Builder()
        .connectTimeout(10, TimeUnit.SECONDS)
        .readTimeout(30, TimeUnit.SECONDS)
        .writeTimeout(10, TimeUnit.SECONDS)
        .retryOnConnectionFailure(false) // Yeniden bağlanmayı biz yönetiyoruz
        .build()

    // ─── Connect / Disconnect ─────────────────────────────────────────────
    fun connect() {
        if (_connectionState.value is ConnectionState.Connected ||
            _connectionState.value is ConnectionState.Connecting
        ) return

        scope.launch { attemptConnect() }
    }

    fun disconnect() {
        reconnectJob?.cancel()
        reconnectJob = null
        reconnectAttempt = 0
        webSocket?.close(1000, "User logout")
        webSocket = null
        _connectionState.value = ConnectionState.Disconnected
        Log.i(TAG, "WS bağlantı kasıtlı olarak kapatıldı.")
    }

    // ─── Send Events ───────────────────────────────────────────────────────
    /**
     * Sunucuya chat_message event'i gönder.
     * @return true → gönderildi; false → WS bağlı değil (REST fallback kullan)
     */
    fun sendMessage(text: String, language: String = "tr", conversationId: String): Boolean {
        val ws = webSocket ?: return false
        if (_connectionState.value !is ConnectionState.Connected) return false

        val payload = JSONObject().apply {
            put("type", "chat_message")
            put("payload", JSONObject().apply {
                put("text", text)
                put("language", language)
                put("conversation_id", conversationId)
            })
        }
        // Mesaj içeriği loglanmaz
        return ws.send(payload.toString())
    }

    /** Typing start event gönder (raw mesaj içermez). */
    fun sendTypingStart() {
        sendSimpleEvent("typing_start")
    }

    /** Typing stop event gönder. */
    fun sendTypingStop() {
        sendSimpleEvent("typing_stop")
    }

    /** Ping event gönder (heartbeat). */
    fun sendPing() {
        sendSimpleEvent("ping")
    }

    private fun sendSimpleEvent(type: String) {
        val ws = webSocket ?: return
        if (_connectionState.value !is ConnectionState.Connected) return
        val payload = JSONObject().apply {
            put("type", type)
            put("payload", JSONObject())
        }
        ws.send(payload.toString())
    }

    // ─── Internal Connect Logic ────────────────────────────────────────────
    private suspend fun attemptConnect() {
        _connectionState.value = if (reconnectAttempt == 0)
            ConnectionState.Connecting
        else
            ConnectionState.Reconnecting(reconnectAttempt, BackoffCalculator.delayFor(reconnectAttempt))

        // Token al (DataStore'dan)
        val token = tokenManager.getToken().firstOrNull()
        if (token.isNullOrBlank()) {
            // Token yok → bağlantı yapma
            _connectionState.value = ConnectionState.Failed("Token bulunamadı")
            Log.w(TAG, "WS: Token yok, bağlantı iptal edildi.")
            return
        }

        // WS URL oluştur (token query param olarak eklenir; header desteği yok)
        val baseUrl = BuildConfig.BASE_URL
            .replace("https://", "wss://")
            .replace("http://", "ws://")
        val wsUrl = "$baseUrl$WS_PATH?token=$token"

        val request = Request.Builder()
            .url(wsUrl)
            .build()

        Log.i(TAG, "WS bağlantı deneniyor. Attempt=$reconnectAttempt")

        webSocket = client.newWebSocket(request, object : WebSocketListener() {

            override fun onOpen(webSocket: WebSocket, response: Response) {
                reconnectAttempt = 0
                _connectionState.value = ConnectionState.Connected
                Log.i(TAG, "WS bağlandı.")
            }

            override fun onMessage(webSocket: WebSocket, text: String) {
                parseServerEvent(text)
            }

            override fun onClosing(webSocket: WebSocket, code: Int, reason: String) {
                webSocket.close(1000, null)
                Log.i(TAG, "WS kapanıyor. code=$code")
                handleDisconnect(code, reason)
            }

            override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                Log.i(TAG, "WS kapatıldı. code=$code")
                handleDisconnect(code, reason)
            }

            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                // Hata tipi loglanır ama URL/token loglanmaz
                Log.w(TAG, "WS bağlantı hatası: ${t.javaClass.simpleName}")
                handleDisconnect(-1, t.javaClass.simpleName)
            }
        })
    }

    private fun handleDisconnect(code: Int, reason: String) {
        webSocket = null

        // 4001 = Auth hatası → reconnect yapma
        if (code == 4001) {
            _connectionState.value = ConnectionState.Failed("Auth hatası: $reason")
            Log.w(TAG, "WS: Auth hatası. Reconnect iptal.")
            return
        }

        // Kasıtlı kapat (1000) veya Failed durumu → reconnect yapma
        if (_connectionState.value is ConnectionState.Failed ||
            _connectionState.value is ConnectionState.Disconnected
        ) return

        scheduleReconnect()
    }

    private fun scheduleReconnect() {
        reconnectAttempt++

        if (BackoffCalculator.hasReachedMax(reconnectAttempt)) {
            _connectionState.value = ConnectionState.Failed("Maksimum bağlantı denemesi aşıldı")
            Log.w(TAG, "WS: Max retry aşıldı. REST fallback aktif.")
            return
        }

        val delay = BackoffCalculator.delayFor(reconnectAttempt)
        _connectionState.value = ConnectionState.Reconnecting(reconnectAttempt, delay)
        Log.i(TAG, "WS: $delay ms sonra yeniden denenecek. Attempt=$reconnectAttempt")

        reconnectJob?.cancel()
        reconnectJob = scope.launch {
            delay(delay)
            attemptConnect()
        }
    }

    // ─── Event Parser ─────────────────────────────────────────────────────
    private fun parseServerEvent(text: String) {
        try {
            val json = JSONObject(text)
            val type = json.optString("type")
            val payload = json.optJSONObject("payload") ?: JSONObject()

            val event = when (type) {
                "chat_response" -> WsEvent.ChatResponse(
                    emotion = payload.optString("emotion", "neutral"),
                    risk = payload.optString("risk", "low"),
                    response = payload.optString("response", ""),
                    emergencyContact = payload.optString("emergency_contact").takeIf { it.isNotEmpty() },
                )
                "typing_indicator" -> WsEvent.TypingIndicator(
                    isTyping = payload.optBoolean("is_typing", false)
                )
                "presence_update" -> WsEvent.PresenceUpdate(
                    userId = payload.optString("user_id"),
                    online = payload.optBoolean("online", false),
                )
                "intervention" -> WsEvent.Intervention(
                    title = payload.optString("title"),
                    body = payload.optString("body"),
                    severity = payload.optString("severity"),
                )
                "error" -> WsEvent.Error(
                    code = payload.optString("code"),
                    message = payload.optString("message"),
                )
                "pong" -> WsEvent.Pong
                "connected" -> WsEvent.Connected
                else -> {
                    Log.d(TAG, "Bilinmeyen event tipi: $type")
                    return
                }
            }

            scope.launch { _incomingEvents.emit(event) }
        } catch (e: Exception) {
            // Raw içerik loglanmaz; sadece hata tipi
            Log.w(TAG, "Event parse hatası: ${e.javaClass.simpleName}")
        }
    }
}

// ─── WebSocket Event Sealed Class ────────────────────────────────────────────
sealed class WsEvent {
    object Connected : WsEvent()
    object Pong : WsEvent()

    data class ChatResponse(
        val emotion: String,
        val risk: String,
        val response: String,
        val emergencyContact: String?,
    ) : WsEvent()

    data class TypingIndicator(val isTyping: Boolean) : WsEvent()
    data class PresenceUpdate(val userId: String, val online: Boolean) : WsEvent()
    data class Intervention(val title: String, val body: String, val severity: String) : WsEvent()
    data class Error(val code: String, val message: String) : WsEvent()
}
