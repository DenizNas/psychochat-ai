import time
import logging
from typing import Any, Dict, List
from src.ai_providers.base import BaseAIProvider, AIProviderResult

logger = logging.getLogger(__name__)

# Highly empathetic, clean, non-clinical local fallback templates
_EMPATHY_TEMPLATES = {
    "sadness": [
        "Paylaştığın bu hüzünlü hisleri tüm samimiyetimle duyuyorum. Şu an senin için zor bir süreç olabilir. Lütfen kendine şefkat göstermekten çekinme, bu süreci seninle paylaşmak ve destek olmak için buradayım.",
        "Üzgün hissetmen çok doğal ve bu duyguyu yaşamakta tamamen haklısın. Yalnız olmadığını bilmeni isterim. Dinlenmeye ve kendine zaman ayırmaya özen göster, buradayım."
    ],
    "anxiety": [
        "Zihninin şu an yoğun bir kaygı çemberinde olduğunu hissedebiliyorum. Bu kaygının seni korumaya çalışan doğal bir tepki olduğunu hatırla. Lütfen yavaşça derin bir nefes al, güvende olduğunu hissetmene yardımcı olmak için yanındayım.",
        "Endişeli hissettiğinde nefesine odaklanmak sana yardımcı olabilir. Zihninden geçen düşünceler ne olursa olsun, bu süreçte seninle yürümeye hazırım. Kendine karşı sabırlı ol."
    ],
    "anger": [
        "Öfkelenmek ve tepki göstermek son derece normal bir insani duygudur. Seni neyin bu kadar öfkelendirdiğini yargılamadan dinlemeye hazırım. Hazır hissettiğinde bu konuyu beraber detaylandırabiliriz.",
        "Öfke, sınırlarının ihlal edildiğini gösteren güçlü bir habercidir. Bu duygunun altında yatan nedenleri beraber anlamaya çalışabiliriz. Sana destek olmak için buradayım."
    ],
    "joy": [
        "Bu harika enerjiyi ve mutluluğu benimle paylaştığın için çok sevindim! Başarılarını ve seni gülümseten anları kutlamak benim için de çok kıymetli. Hep böyle güzel kalması dileğiyle!",
        "İçindeki bu güzel kıvılcım beni de çok mutlu etti. Hayatın getirdiği güzelliklerin tadını sonuna kadar çıkarmanı dilerim."
    ],
    "default": [
        "Seni ilgiyle ve yargılamadan dinliyorum. Zihnini meşgul eden her ne varsa benimle dilediğin gibi paylaşabilirsin. Bu yolda beraberiz.",
        "Anlatmak istediğin her detayı sabırla dinlemeye hazırım. Kendini nasıl hissettiğini daha fazla paylaşmak ister misin? Buradayım."
    ]
}

class LocalProvider(BaseAIProvider):
    """
    100% offline, deterministic local fallback provider.
    Ensures LLM reliability even under global internet or API outages.
    """

    def generate(
        self,
        messages: List[Dict[str, str]],
        model_config: Dict[str, Any]
    ) -> AIProviderResult:
        start_time = time.time()

        # Parse user turn content and infer emotion
        last_message = messages[-1].get("content", "") if messages else ""
        last_message_lower = last_message.lower()

        # Simple keyword emotion inference
        inferred_emotion = "default"
        if any(word in last_message_lower for word in ["üzg", "keder", "ağla", "acı", "mutsuz"]):
            inferred_emotion = "sadness"
        elif any(word in last_message_lower for word in ["kaygı", "endişe", "stres", "kork", "panik"]):
            inferred_emotion = "anxiety"
        elif any(word in last_message_lower for word in ["öfke", "kızgın", "delir", "sinir"]):
            inferred_emotion = "anger"
        elif any(word in last_message_lower for word in ["mutlu", "harika", "sevinç", "başar"]):
            inferred_emotion = "joy"

        # Determine index based on text length to make it deterministic but varied
        templates = _EMPATHY_TEMPLATES[inferred_emotion]
        idx = len(last_message) % len(templates)
        response_text = templates[idx]

        latency_ms = (time.time() - start_time) * 1000.0

        # Local calls are 100% cost-free!
        return AIProviderResult(
            text=response_text,
            provider="local",
            model="local-deterministic",
            latency_ms=latency_ms,
            token_estimate=len(response_text) // 4,
            cost_estimate=0.0,
            finish_reason="stop",
            fallback_used=True
        )
