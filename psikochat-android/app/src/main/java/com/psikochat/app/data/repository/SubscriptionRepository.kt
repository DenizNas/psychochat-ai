package com.psikochat.app.data.repository

import com.psikochat.app.data.api.PsikoApi
import com.psikochat.app.data.model.*
import retrofit2.HttpException
import java.io.IOException
import org.json.JSONObject

class SubscriptionRepository(private val api: PsikoApi) {

    suspend fun getPlans(): Resource<List<SubscriptionPlanDto>> {
        return try {
            val response = api.getSubscriptionPlans()
            Resource.Success(response)
        } catch (e: Exception) {
            parseError(e, "Abonelik planları alınamadı")
        }
    }

    suspend fun getMySubscription(): Resource<SubscriptionStatusDto> {
        return try {
            val response = api.getMySubscription()
            Resource.Success(response)
        } catch (e: Exception) {
            parseError(e, "Abonelik durumu alınamadı")
        }
    }

    suspend fun startCheckout(planId: String): Resource<CheckoutResponseDto> {
        return try {
            val request = CheckoutRequestDto(planId)
            val idempotencyKey = java.util.UUID.randomUUID().toString()
            val response = api.startCheckout(request, idempotencyKey)
            Resource.Success(response)
        } catch (e: Exception) {
            parseError(e, "Ödeme başlatılamadı")
        }
    }

    suspend fun getPaymentHistory(): Resource<List<PaymentHistoryDto>> {
        return try {
            val response = api.getPaymentHistory()
            Resource.Success(response)
        } catch (e: Exception) {
            parseError(e, "Ödeme geçmişi alınamadı")
        }
    }

    private fun <T> parseError(e: Exception, defaultMessage: String): Resource<T> {
        return when (e) {
            is HttpException -> {
                if (e.code() == 503) {
                    Resource.Error("Ödeme altyapısı henüz yapılandırılmadı. Lütfen daha sonra tekrar deneyin.")
                } else {
                    val errorBody = e.response()?.errorBody()?.string()
                    val parsedMessage = try {
                        if (!errorBody.isNullOrBlank()) {
                            val json = JSONObject(errorBody)
                            when {
                                json.has("message") -> json.getString("message")
                                json.has("detail") -> json.getString("detail")
                                else -> defaultMessage
                            }
                        } else defaultMessage
                    } catch (ex: Exception) {
                        defaultMessage
                    }
                    Resource.Error(parsedMessage)
                }
            }
            is IOException -> Resource.Error("Sunucuya bağlanılamadı. İnternet bağlantınızı kontrol edin.")
            else -> Resource.Error(e.message ?: defaultMessage)
        }
    }
}
