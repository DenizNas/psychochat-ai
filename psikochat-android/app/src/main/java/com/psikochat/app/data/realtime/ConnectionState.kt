package com.psikochat.app.data.realtime

/**
 * WebSocket bağlantı durum makinesi.
 *
 * Geçişler:
 *   Disconnected → Connecting → Connected
 *   Connected → Reconnecting → Connected (hata sonrası)
 *   * → Disconnected (kalıcı hata / logout)
 */
sealed class ConnectionState {
    /** Hiç bağlantı kurulmadı ya da kasıtlı olarak kapatıldı. */
    object Disconnected : ConnectionState()

    /** İlk bağlantı girişimi sürüyor. */
    object Connecting : ConnectionState()

    /** WebSocket bağlantısı aktif. */
    object Connected : ConnectionState()

    /**
     * Bağlantı kesildi; exponential backoff ile yeniden denenecek.
     * @param attempt Kaçıncı deneme (1-indexed).
     * @param delayMs Bir sonraki denemeye kadar bekleme süresi (ms).
     */
    data class Reconnecting(val attempt: Int, val delayMs: Long) : ConnectionState()

    /** Kalıcı hata (max retry aşıldı veya auth hatası). */
    data class Failed(val reason: String) : ConnectionState()
}

/**
 * Exponential backoff hesaplayıcı.
 *
 * delay = min(BASE_DELAY_MS * 2^(attempt-1) + jitter, MAX_DELAY_MS)
 */
object BackoffCalculator {
    private const val BASE_DELAY_MS = 1_000L   // 1 sn
    private const val MAX_DELAY_MS  = 60_000L  // 60 sn
    private const val MAX_ATTEMPTS  = 8        // 8 denemeden sonra Failed

    fun delayFor(attempt: Int): Long {
        val exp = (1L shl (attempt - 1).coerceAtLeast(0)) // 2^(attempt-1)
        val jitter = (Math.random() * 500).toLong()        // 0–500 ms jitter
        return (BASE_DELAY_MS * exp + jitter).coerceAtMost(MAX_DELAY_MS)
    }

    fun hasReachedMax(attempt: Int): Boolean = attempt > MAX_ATTEMPTS
}
