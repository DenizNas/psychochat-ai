import os
import time
import logging
import openai
from dotenv import load_dotenv

from src.response_engine.models import EngineConfig, EngineInput, EngineOutput
from src.response_engine.prompts import build_system_prompt, build_user_prompt, PROMPT_VERSION
from src.response_engine.context_builder import build_messages
from src.response_engine.safety import (
    check_safety, get_crisis_safe_response, log_safety_event,
    CAT_INJECTION_ATTEMPT
)
from src.response_engine.response_formatter import format_response
from src.response_engine.memory_manager import process_memory
from src.response_engine.response_ranker import score_response, RankResult, NORMAL_THRESHOLD, CRISIS_THRESHOLD
from src.services.database import save_chat_message

logger = logging.getLogger(__name__)

class ResponseEngine:
    def __init__(self, config: EngineConfig = None):
        self.config = config or EngineConfig()
        
        load_dotenv()
        api_key = os.getenv("OPENAI_API_KEY")
        if api_key:
            openai.api_key = api_key
        else:
            logger.warning("OPENAI_API_KEY not found in environment variables.")

    def generate_response(self, engine_input: EngineInput) -> EngineOutput:
        """
        Orchestrates the response generation:
        1. Context Building (Prompts + History)
        2. GPT Call (with Fallback)
        3. Safety Check
        4. Formatting
        5. Database Saving
        """
        if not openai.api_key:
            return EngineOutput(
                final_text="Üzgünüm, şu an sistemde bir bağlantı sorunu yaşıyorum (API Key eksik).",
                is_fallback=True,
                metadata={"error": "API Key missing"}
            )
            
        start_time = time.time()
        
        # Structured Logging (Masking sensitive text, logging metadata)
        logger.info(
            f"Engine Request | UserID: {engine_input.user_id} | "
            f"Emotion: {engine_input.emotion} | Risk: {engine_input.risk} | "
            f"TextLength: {len(engine_input.text)}"
        )
        # pre-init for safe reference in finally/error paths
        memory_meta: dict = {"memory_count": 0, "selected_memory_count": 0, "memory_injected": False, "injection_text": ""}
        prompt_meta: dict = {"prompt_version": PROMPT_VERSION, "prompt_sections": [], "prompt_length": 0, "injection_guard_enabled": True}

        # 1.5. Memory Pipeline (Extract → Lookup → Inject)
        # Runs BEFORE prompt assembly so memory_context flows into build_system_prompt.
        # Crisis guard is enforced inside process_memory — no raw crisis data ever stored.
        memory_meta = process_memory(
            user_id=engine_input.user_id,
            text=engine_input.text,
            emotion=engine_input.emotion,
            risk=engine_input.risk,
        )
        memory_context_str = memory_meta.get("injection_text", "") if memory_meta.get("memory_injected") else ""

        # 1. Prompts (modular builder — assembles all sections with versioning)
        system_prompt, prompt_meta = build_system_prompt(
            language=engine_input.language,
            emotion=engine_input.emotion,
            risk=engine_input.risk,
            memory_context=memory_context_str,
        )
        user_prompt = build_user_prompt(
            text=engine_input.text,
            emotion=engine_input.emotion,
            risk=engine_input.risk,
        )

        # 2. Context Builder
        messages = build_messages(
            user_id=engine_input.user_id,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            limit=self.config.max_memory_length,
            emotion=engine_input.emotion,
            risk=engine_input.risk,
        )
        
        # 2.5. USER INPUT Safety Check (pre-GPT — fast path for crisis/injection)
        # This catches crisis signals BEFORE sending to GPT, saving latency and
        # ensuring no dangerous user message ever reaches the model unguarded.
        input_safe, input_reason = check_safety(
            engine_input.text,
            risk_level=engine_input.risk,
            language=engine_input.language,
            mode="user_input"
        )
        if not input_safe:
            is_crisis_by_text = True
            safe_resp = get_crisis_safe_response(
                language=engine_input.language,
                category=input_reason if input_reason else "default"
            )
            safe_resp = format_response(safe_resp)
            from src.response_engine.safety import log_safety_event
            log_safety_event({
                "request_id": engine_input.user_id,
                "crisis_detected": True,
                "unsafe_output_detected": False,
                "fallback_used": True,
                "safety_reason": input_reason,
                "injection_attempt_detected": (input_reason == CAT_INJECTION_ATTEMPT),
                "text_length": len(engine_input.text),
                "language": engine_input.language,
                "stage": "user_input_check"
            })
            try:
                save_chat_message(engine_input.user_id, "user", engine_input.text)
                save_chat_message(engine_input.user_id, "assistant", safe_resp)
            except Exception as db_err:
                logger.error(f"Failed to save chat history (pre-GPT fallback): {db_err}")
            latency = time.time() - start_time
            return EngineOutput(
                final_text=safe_resp,
                is_fallback=True,
                metadata={
                    "latency_sec": latency,
                    "model_used": "safety_template",
                    "safety": {
                        "is_safe": False,
                        "safety_reason": input_reason,
                        "injection_attempt_detected": (input_reason == CAT_INJECTION_ATTEMPT),
                        "stage": "user_input_check"
                    }
                }
            )

        # 3. GPT Provider Logic — Ranked + Retry
        #
        # Strategy:
        #   a) Call primary model (GPT-4o)
        #   b) Score the response via response_ranker
        #   c) If score < threshold:
        #       - Crisis turn → immediate safe template (no retry, safety first)
        #       - Normal turn → 1 retry with fallback model (GPT-3.5)
        #   d) If retry also fails quality → use last known text (safety still
        #      runs afterwards to catch any remaining issues)
        #
        # Max retries: self.config.max_retries (default: 1)
        # GPT cost: at most 2 calls per request

        final_text: str = ""
        is_fallback: bool = False
        error_meta = None
        is_crisis: bool = engine_input.risk.strip().lower() in {"1", "crisis", "kriz"}

        # Ranker tracking vars
        rank_result: RankResult = RankResult(score=0.0, passes=False)
        retry_count: int = 0
        primary_model_used: bool = False
        fallback_model_used: bool = False
        fallback_reason: str = ""
        final_model: str = ""

        def _call_gpt(model: str) -> str:
            """Single GPT call; returns stripped content or empty string."""
            resp = openai.chat.completions.create(
                model=model,
                messages=messages,
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
                timeout=self.config.timeout_seconds
            )
            content = resp.choices[0].message.content
            return content.strip() if content else ""

        # ── a) Primary model call ─────────────────────────────────────────
        try:
            final_text = _call_gpt(self.config.primary_model)
            primary_model_used = True
            final_model = self.config.primary_model
        except Exception as e_primary:
            logger.warning(
                "GPT primary model failed | Model: %s | Error: %s",
                self.config.primary_model, e_primary
            )
            error_meta = str(e_primary)
            is_fallback = True
            fallback_reason = "primary_model_exception"

        # ── b) Score primary response ─────────────────────────────────────
        if primary_model_used and final_text:
            rank_result = score_response(final_text, emotion=engine_input.emotion, risk=engine_input.risk)
            logger.info(
                "RANKER | UserID: %s | Model: %s | Score: %.4f | Passes: %s | Reasons: %s",
                engine_input.user_id, self.config.primary_model,
                rank_result.score, rank_result.passes, rank_result.reasons
            )

        # ── c) Decide retry / fallback based on score ─────────────────────
        needs_action = (
            not primary_model_used          # primary call failed outright
            or not final_text               # got empty response
            or not rank_result.passes       # quality too low
        )

        if needs_action:
            if is_crisis:
                # Crisis path: NEVER retry — go straight to safe template
                logger.warning(
                    "RANKER CRISIS FALLBACK | UserID: %s | Score: %.4f | Reasons: %s",
                    engine_input.user_id, rank_result.score, rank_result.reasons
                )
                final_text = get_crisis_safe_response(
                    language=engine_input.language,
                    category="default"
                )
                is_fallback = True
                fallback_reason = fallback_reason or "crisis_quality_threshold"
                final_model = "crisis_safe_template"
            else:
                # Normal path: 1 retry with fallback model
                max_retries = getattr(self.config, "max_retries", 1)
                attempt = 0
                while attempt < max_retries:
                    attempt += 1
                    retry_count += 1
                    try:
                        logger.info(
                            "RANKER RETRY | UserID: %s | Attempt: %d | Model: %s",
                            engine_input.user_id, attempt, self.config.fallback_model
                        )
                        final_text = _call_gpt(self.config.fallback_model)
                        fallback_model_used = True
                        final_model = self.config.fallback_model
                        is_fallback = True
                        fallback_reason = fallback_reason or "quality_below_threshold"

                        # Score the retry response
                        rank_result = score_response(
                            final_text, emotion=engine_input.emotion, risk=engine_input.risk
                        )
                        logger.info(
                            "RANKER RETRY SCORE | UserID: %s | Model: %s | Score: %.4f | Passes: %s",
                            engine_input.user_id, self.config.fallback_model,
                            rank_result.score, rank_result.passes
                        )
                        if rank_result.passes:
                            break  # good enough — stop retrying
                    except Exception as e_fallback:
                        logger.error(
                            "GPT fallback model failed | Model: %s | Error: %s",
                            self.config.fallback_model, e_fallback
                        )
                        final_text = "Üzgünüm, şu an sana yanıt üretmekte zorlanıyorum. Lütfen daha sonra tekrar dene."
                        is_fallback = True
                        fallback_reason = "fallback_model_exception"
                        final_model = "hardcoded_fallback"
                        return EngineOutput(
                            final_text=final_text,
                            is_fallback=True,
                            metadata={"error": "Both GPT models failed", "details": str(e_fallback)}
                        )

        # If primary worked but quality was borderline and no retry was done
        if not final_model:
            final_model = self.config.primary_model

        # 4. Safety Layer (Crisis-Aware Policy)
        is_safe, safety_reason = check_safety(
            final_text, 
            risk_level=engine_input.risk, 
            language=engine_input.language
        )
        
        is_crisis = engine_input.risk.lower() in ["1", "crisis", "kriz"]
        injection_attempt = (safety_reason == CAT_INJECTION_ATTEMPT)
        fallback_used = not is_safe
        
        # Structured Safety Log (Privacy-Aware)
        log_safety_event({
            "request_id": engine_input.user_id, # Using user_id as proxy for request tracking
            "crisis_detected": is_crisis,
            "unsafe_output_detected": not is_safe,
            "fallback_used": fallback_used,
            "safety_reason": safety_reason,
            "injection_attempt_detected": injection_attempt,
            "text_length": len(engine_input.text),
            "language": engine_input.language
        })

        if not is_safe:
            is_fallback = True
            # Select safe response based on category
            final_text = get_crisis_safe_response(
                language=engine_input.language,
                category=safety_reason if safety_reason else "default"
            )
            
            logger.warning(
                f"Safety Triggered | UserID: {engine_input.user_id} | "
                f"Reason: {safety_reason} | Injection: {injection_attempt} | "
                f"FallbackUsed: True"
            )
        else:
            safety_reason = None
            injection_attempt = False
            
        # 5. Formatter
        final_text = format_response(final_text)

        # 6. Database Integration
        try:
            save_chat_message(engine_input.user_id, "user", engine_input.text)
            save_chat_message(engine_input.user_id, "assistant", final_text)
        except Exception as db_err:
            logger.error(f"Failed to save chat history: {db_err}")

        latency = time.time() - start_time

        # Structured ENGINE_LOG — all metadata, no raw user content
        logger.info(
            "ENGINE_LOG | UserID: %s | Latency: %.3fs | final_model: %s | "
            "primary_model_used: %s | fallback_model_used: %s | retry_count: %d | "
            "quality_score: %.4f | quality_reasons: %s | fallback_reason: %s | "
            "memory_count: %d | selected_memory_count: %d | memory_injected: %s | "
            "prompt_version: %s | prompt_sections: %s | prompt_length: %d | injection_guard_enabled: %s",
            engine_input.user_id,
            latency,
            final_model,
            primary_model_used,
            fallback_model_used,
            retry_count,
            rank_result.score,
            rank_result.reasons,
            fallback_reason,
            memory_meta.get("memory_count", 0),
            memory_meta.get("selected_memory_count", 0),
            memory_meta.get("memory_injected", False),
            prompt_meta.get("prompt_version", PROMPT_VERSION),
            prompt_meta.get("prompt_sections", []),
            prompt_meta.get("prompt_length", 0),
            prompt_meta.get("injection_guard_enabled", True),
        )
        
        return EngineOutput(
            final_text=final_text,
            is_fallback=is_fallback,
            metadata={
                "latency_sec": latency,
                "final_model": final_model,
                "error": error_meta,
                "ranking": {
                    "primary_model_used": primary_model_used,
                    "fallback_model_used": fallback_model_used,
                    "retry_count": retry_count,
                    "quality_score": round(rank_result.score, 4),
                    "quality_reasons": rank_result.reasons,
                    "fallback_reason": fallback_reason or None,
                },
                "memory": {
                    "memory_count": memory_meta.get("memory_count", 0),
                    "selected_memory_count": memory_meta.get("selected_memory_count", 0),
                    "memory_injected": memory_meta.get("memory_injected", False),
                },
                "safety": {
                    "is_safe": is_safe,
                    "safety_reason": safety_reason,
                    "injection_attempt_detected": injection_attempt
                }
            }
        )

# Global singleton instance for easy usage
response_engine = ResponseEngine()
