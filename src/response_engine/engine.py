import os
import time
import logging
import openai
import threading
from src.core.config import settings

from src.response_engine.models import EngineConfig, EngineInput, EngineOutput
from src.response_engine.prompts import build_system_prompt, build_user_prompt, PROMPT_VERSION, build_retry_quality_instruction
from src.response_engine.context_builder import build_messages
from src.response_engine.safety import (
    check_safety, get_crisis_safe_response, log_safety_event,
    CAT_INJECTION_ATTEMPT
)
from src.response_engine.response_formatter import format_response
from src.response_engine.memory_manager import process_memory          # backward-compat kept
from src.response_engine.personal_context_engine import process_turn as pce_process_turn
from src.response_engine.response_ranker import score_response, RankResult, NORMAL_THRESHOLD, CRISIS_THRESHOLD
from src.services.database import save_chat_message, get_or_create_profile
from src.ai_providers import ai_orchestrator
from src.ai_providers.local_provider import sanitize_memory_inlay

logger = logging.getLogger(__name__)


class SessionCache(dict):
    """Thread-safe, memory-bounded cache for session user messages to prevent leaks in production."""
    def __init__(self, max_size=2000):
        super().__init__()
        self.max_size = max_size
        self._keys = []
        self._lock = threading.RLock()
    
    def __setitem__(self, key, value):
        with self._lock:
            if key not in self:
                self._keys.append(key)
            super().__setitem__(key, value)
            if len(self._keys) > self.max_size:
                oldest_key = self._keys.pop(0)
                self.pop(oldest_key, None)

    def __getitem__(self, key):
        with self._lock:
            return super().__getitem__(key)

    def __contains__(self, key):
        with self._lock:
            return super().__contains__(key)

    def get(self, key, default=None):
        with self._lock:
            return super().get(key, default)

    def pop(self, key, default=None):
        with self._lock:
            if key in self._keys:
                self._keys.remove(key)
            return super().pop(key, default)

_SESSION_USER_MESSAGES = SessionCache(max_size=2000)


class ResponseEngine:
    def __init__(self, config: EngineConfig = None):
        self.config = config or EngineConfig()
        
        api_key = settings.OPENAI_API_KEY
        if api_key:
            openai.api_key = api_key
        else:
            logger.warning("OPENAI_API_KEY not found in configuration system.")

    def generate_response(self, engine_input: EngineInput) -> EngineOutput:
        """
        Orchestrates the response generation:
        1. Context Building (Prompts + History)
        2. GPT Call (with Fallback)
        3. Safety Check
        4. Formatting
        5. Database Saving
        """
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
        memory_lookup_latency = 0.0

        # Determine crisis level early
        from src.response_engine.safety import classify_crisis_level, get_custom_crisis_response
        crisis_level = classify_crisis_level(engine_input.text, engine_input.risk)
        
        if crisis_level in ["high", "imminent"]:
            logger.warning(f"ENGINE | Crisis input detected! Level: {crisis_level}. Bypassing normal chatbot flow.")
            safe_resp = get_custom_crisis_response(crisis_level, engine_input.text)
            safe_resp = format_response(safe_resp)
            
            try:
                save_chat_message(engine_input.user_id, "user", engine_input.text)
                save_chat_message(engine_input.user_id, "assistant", safe_resp)
            except Exception as db_err:
                logger.error(f"Failed to save chat history (early crisis bypass): {db_err}")
                
            try:
                from src.services.database import SessionLocal
                from src.services.compliance_service import compliance_service
                db = SessionLocal()
                try:
                    compliance_service.log_security_event(
                        db=db,
                        user_id=engine_input.user_id,
                        event_type="crisis_safety_triggered",
                        ip_address="0.0.0.0",
                        user_agent="internal",
                        severity="WARNING",
                        metadata={"reason": f"early_crisis_{crisis_level}", "stage": "early_check"}
                    )
                finally:
                    db.close()
            except Exception as audit_err:
                logger.error(f"Failed to log crisis audit log: {audit_err}")
                
            latency = time.time() - start_time
            
            return EngineOutput(
                final_text=safe_resp,
                is_fallback=True,
                metadata={
                    "latency_sec": latency,
                    "model_used": "safety_template",
                    "final_model": "crisis_safe_template",
                    "is_crisis": True,
                    "crisis_level": crisis_level,
                    "show_emergency_support": True,
                    "emergency_phone": "112",
                    "emergency_title": "Acil Destek",
                    "emergency_message": "Güvende kalman öncelikli. Yalnız kalmamaya çalış ve mümkünse hemen destek al.",
                    "safety": {
                        "is_safe": False,
                        "safety_reason": f"early_crisis_{crisis_level}",
                        "injection_attempt_detected": False,
                        "stage": "early_crisis_bypass"
                    }
                }
            )

        # 1.5. Memory Pipeline (PersonalContextEngine — Extract → Lookup → Inject)
        # Primary engine: personal_context_engine (Faz 10 P2)
        # Crisis guard and privacy guard enforced inside process_turn.
        start_mem_time = time.time()
        memory_meta = pce_process_turn(
            user_id=engine_input.user_id,
            text=engine_input.text,
            emotion=engine_input.emotion,
            risk=engine_input.risk,
            privacy_mode=engine_input.preferences.privacy_mode
        )
        memory_lookup_latency = time.time() - start_mem_time
        memory_context_str = memory_meta.get("injection_text", "") if memory_meta.get("memory_injected") else ""

        # 1.6. Theme & Need Extraction (runs only on non-crisis turns)
        # Slot: AFTER subtype detection, BEFORE strategy selection and prompt construction.
        # Only extracts and transports — does not yet modify prompts or strategy.
        if not (engine_input.risk.strip().lower() in {"1", "crisis", "kriz"}):
            try:
                from src.response_engine.theme_need_engine import detect_theme_and_need
                tne = detect_theme_and_need(
                    text=engine_input.text,
                    emotion=engine_input.emotion,
                    subtype=engine_input.subtype,
                )
                engine_input = engine_input.model_copy(update={
                    "theme": tne["theme"],
                    "need":  tne["need"],
                    "intent": tne["intent"],
                })
                logger.debug(
                    "ENGINE | T&N extracted | theme=%s need=%s intent=%s",
                    tne["theme"], tne["need"], tne["intent"]
                )
            except Exception as tne_err:
                logger.error(f"ENGINE | Theme & Need extraction error: {tne_err}")

        # 1.7. Intent Enforcement Stage (runs only on non-crisis turns)
        # Mappings:
        #   emotional_expression  -> validation
        #   help_seeking          -> action_planning
        #   self_reflection       -> reflection
        #   problem_solving       -> action_planning  (internal tag: decision_support, no DB schema change)
        if not (engine_input.risk.strip().lower() in {"1", "crisis", "kriz"}):
            try:
                intent = engine_input.intent
                if intent == "emotional_expression":
                    engine_input = engine_input.model_copy(update={"strategy": "validation"})
                elif intent == "help_seeking":
                    engine_input = engine_input.model_copy(update={"strategy": "action_planning"})
                elif intent == "self_reflection":
                    engine_input = engine_input.model_copy(update={"strategy": "reflection"})
                elif intent == "problem_solving":
                    # Uses action_planning for provider routing; lightweight internal tag tracked in metadata.
                    engine_input = engine_input.model_copy(update={"strategy": "action_planning"})
                logger.debug(
                    "ENGINE | Intent Enforcement | intent=%s -> strategy=%s",
                    intent, engine_input.strategy
                )
            except Exception as ie_err:
                logger.error(f"ENGINE | Intent Enforcement error: {ie_err}")

        # 1. Variation Selection (runs only for normal non-crisis messages)
        is_crisis = engine_input.risk.strip().lower() in {"1", "crisis", "kriz"}
        variation_id = engine_input.variation
        variation_directive = None
        
        if not is_crisis:
            try:
                from src.response_engine.variation_engine import select_linguistic_variants, VARIANTS
                from src.services.database import get_chat_history
                
                history = get_chat_history(engine_input.user_id, limit=10)
                recent_assistant_responses = [msg["content"] for msg in history if msg.get("role") == "assistant"]
                
                if not variation_id:
                    variation_id, variation_directive = select_linguistic_variants(
                        recent_responses=recent_assistant_responses,
                        emotion=engine_input.emotion,
                        subtype=engine_input.subtype,
                        strategy=engine_input.strategy
                    )
                else:
                    for strat_opts in VARIANTS.values():
                        for opt in strat_opts:
                            if opt["id"] == variation_id:
                                variation_directive = opt["directive"]
                                break
                        if variation_directive:
                            break
            except Exception as var_err:
                logger.error(f"ENGINE | Variation engine error: {var_err}")

        # 1.8. Multi-Turn Pattern Detection (runs only on non-crisis turns)
        conversation_pattern = {"pattern_name": "none", "confidence": 0.0, "hit_count": 0}
        if not (engine_input.risk.strip().lower() in {"1", "crisis", "kriz"}):
            try:
                from src.response_engine.conversation_pattern_engine import detect_conversation_pattern
                from src.services.database import get_chat_history
                from datetime import datetime, timezone
                
                session_id = getattr(engine_input, "session_id", None)
                if session_id:
                    session_key = (engine_input.user_id, session_id)
                    if session_key not in _SESSION_USER_MESSAGES:
                        _SESSION_USER_MESSAGES[session_key] = []
                    session_msgs = _SESSION_USER_MESSAGES[session_key]
                    if not session_msgs or session_msgs[-1] != engine_input.text:
                        session_msgs.append(engine_input.text)
                    recent_user_messages = session_msgs[-5:]
                    _SESSION_USER_MESSAGES[session_key] = recent_user_messages
                else:
                    # Fallback to database history with time-gap threshold (e.g. 10 minutes = 600 seconds)
                    history = get_chat_history(engine_input.user_id, limit=20)
                    user_history_msgs = [msg for msg in history if msg.get("role") == "user"]
                    
                    threshold_seconds = 600
                    
                    def parse_ts(ts_str):
                        if ts_str.endswith('Z'):
                            ts_str = ts_str[:-1] + '+00:00'
                        return datetime.fromisoformat(ts_str)

                    if user_history_msgs:
                        last_msg = user_history_msgs[-1]
                        last_ts = parse_ts(last_msg["timestamp"])
                        
                        if last_ts.tzinfo is None:
                            current_time = datetime.now(timezone.utc).replace(tzinfo=None)
                        else:
                            current_time = datetime.now(timezone.utc)
                            
                        initial_gap = (current_time - last_ts).total_seconds()
                        if initial_gap < threshold_seconds:
                            valid_msgs = [last_msg["content"]]
                            prev_ts = last_ts
                            for msg in reversed(user_history_msgs[:-1]):
                                msg_ts = parse_ts(msg["timestamp"])
                                gap = (prev_ts - msg_ts).total_seconds()
                                if gap < threshold_seconds:
                                    valid_msgs.insert(0, msg["content"])
                                    prev_ts = msg_ts
                                else:
                                    break
                            recent_user_messages = valid_msgs
                        else:
                            recent_user_messages = []
                    else:
                        recent_user_messages = []

                    recent_user_messages.append(engine_input.text)
                    recent_user_messages = recent_user_messages[-5:]
                
                conversation_pattern = detect_conversation_pattern(
                    recent_user_messages=recent_user_messages,
                    current_theme=engine_input.theme,
                    current_need=engine_input.need
                )
                logger.debug(
                    "ENGINE | Multi-Turn Pattern | pattern=%s confidence=%.2f hit_count=%d",
                    conversation_pattern.get("pattern_name"),
                    conversation_pattern.get("confidence"),
                    conversation_pattern.get("hit_count")
                )
            except Exception as pat_err:
                logger.error(f"ENGINE | Multi-Turn Pattern detection error: {pat_err}")

        # 1.5. Prompts (modular builder — assembles all sections with versioning)
        system_prompt, prompt_meta = build_system_prompt(
            language=engine_input.language,
            emotion=engine_input.emotion,
            risk=engine_input.risk,
            memory_context=memory_context_str,
            preferences=engine_input.preferences.model_dump() if hasattr(engine_input.preferences, "model_dump") else engine_input.preferences.dict(),
            text=engine_input.text,
            subtype=engine_input.subtype,
            strategy=engine_input.strategy,
            variation_directive=variation_directive,
            theme=engine_input.theme,
            need=engine_input.need,
            intent=engine_input.intent,
            conversation_pattern=conversation_pattern,
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
            
            try:
                from src.services.database import SessionLocal
                from src.services.compliance_service import compliance_service
                db = SessionLocal()
                try:
                    compliance_service.log_security_event(
                        db=db,
                        user_id=engine_input.user_id,
                        event_type="crisis_safety_triggered",
                        ip_address="0.0.0.0",
                        user_agent="internal",
                        severity="WARNING",
                        metadata={"reason": input_reason, "stage": "pre_gpt_check"}
                    )
                finally:
                    db.close()
            except Exception as audit_err:
                logger.error(f"Failed to log crisis audit log: {audit_err}")
            latency = time.time() - start_time
            return EngineOutput(
                final_text=safe_resp,
                is_fallback=True,
                metadata={
                    "latency_sec": latency,
                    "model_used": "safety_template",
                    "final_model": "crisis_safe_template",
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

        # Telemetry / Orchestrator tracking vars
        ai_provider = "safety_template"
        ai_model = "crisis_safe_template"
        ai_latency_ms = 0.0
        ai_fallback_used = False
        ai_cost_estimate = 0.0
        ai_timeout = False
        ai_circuit_open = False
        retry_count = 0
        rank_result = RankResult(score=1.0, passes=True)
        fallback_reason = ""
        final_model = "crisis_safe_template"
        primary_model_used = "crisis_safe_template"
        fallback_model_used = None

        if is_crisis:
            # 100% Deterministic Crisis Bypass: Bypasses remote LLM calls completely!
            logger.warning("ENGINE | Crisis input detected! Bypassing remote LLM calls.")
            final_text = get_crisis_safe_response(language=engine_input.language, category="default")
            is_fallback = True
            fallback_reason = "crisis_bypass_safety"

            try:
                from src.services.database import SessionLocal
                from src.services.compliance_service import compliance_service
                db = SessionLocal()
                try:
                    compliance_service.log_security_event(
                        db=db,
                        user_id=engine_input.user_id,
                        event_type="crisis_safety_triggered",
                        ip_address="0.0.0.0",
                        user_agent="internal",
                        severity="WARNING",
                        metadata={"reason": "pre_flagged_risk", "stage": "input_risk_bypass"}
                    )
                finally:
                    db.close()
            except Exception as audit_err:
                logger.error(f"Failed to log crisis bypass audit log: {audit_err}")
        else:
            # Build safe memory inlays if not in crisis, privacy mode is disabled, and category is not neutral
            safe_memory_inlays = {}
            from src.response_engine.counseling_examples import categorize_input
            category = categorize_input(engine_input.text, engine_input.emotion)
            if not is_crisis and not engine_input.preferences.privacy_mode and category != "neutral":
                try:
                    from src.response_engine.memory_profile import load_profile
                    profile = load_profile(engine_input.user_id)
                    db_profile = get_or_create_profile(engine_input.user_id)
                    
                    display_name = db_profile.get("display_name") or db_profile.get("full_name") or ""
                    
                    stressors = profile.get("stressors", [])
                    goals = profile.get("goals", [])
                    emotions = profile.get("recurring_emotions", [])
                    advice_topics = profile.get("last_advice_topics", [])
                    
                    active_stressor = stressors[-1] if stressors else ""
                    current_goal = goals[-1] if goals else ""
                    recent_emotion = emotions[-1] if emotions else ""
                    last_advice_topic = advice_topics[-1] if advice_topics else ""
                    
                    safe_memory_inlays = {
                        "display_name": sanitize_memory_inlay(display_name),
                        "active_stressor": sanitize_memory_inlay(active_stressor),
                        "current_goal": sanitize_memory_inlay(current_goal),
                        "recent_emotion": sanitize_memory_inlay(recent_emotion),
                        "last_advice_topic": sanitize_memory_inlay(last_advice_topic)
                    }
                except Exception as inlay_err:
                    logger.error(f"ENGINE | Failed to build safe memory inlays: {inlay_err}")

            # Normal turns: route via multi-provider Orchestrator
            model_config = {
                "model": self.config.primary_model,
                "temperature": self.config.temperature,
                "max_tokens": self.config.max_tokens,
                "timeout_seconds": self.config.timeout_seconds,
                "counseling_category": prompt_meta.get("counseling_category", "neutral"),
                "counseling_strategy": engine_input.strategy,
                "counseling_subtype": engine_input.subtype,
                "intent": engine_input.intent,
                "answer_length_preference": engine_input.preferences.answer_length_preference,
                "response_style": engine_input.preferences.response_style,
                "safe_memory_inlays": safe_memory_inlays,
                "conversation_pattern": conversation_pattern,
            }
            
            # OpenAI is bypassed/minimalized in privacy mode
            orch_res = ai_orchestrator.generate_response(
                messages=messages,
                model_config=model_config,
                bypass_openai=engine_input.preferences.privacy_mode
            )
            
            final_text = orch_res.text
            ai_provider = orch_res.provider
            ai_model = orch_res.model
            ai_latency_ms = orch_res.latency_ms
            ai_fallback_used = orch_res.fallback_used
            ai_cost_estimate = orch_res.cost_estimate
            ai_timeout = (orch_res.error == "timeout" or "timeout" in str(orch_res.error).lower())
            ai_circuit_open = (orch_res.error == "circuit_breaker_open")
            is_fallback = orch_res.fallback_used
            final_model = orch_res.model
            error_meta = orch_res.error
            if orch_res.fallback_used:
                fallback_reason = orch_res.error or "primary_failed"
                primary_model_used = settings.AI_PRIMARY_MODEL
                fallback_model_used = orch_res.model
            else:
                primary_model_used = orch_res.model
                fallback_model_used = None

            # Extract recent assistant responses from the message history to check advice repetitions
            recent_responses = [msg["content"] for msg in messages if msg["role"] == "assistant"]

            # Response ranker check
            rank_result = score_response(
                final_text,
                emotion=engine_input.emotion,
                risk=engine_input.risk,
                user_id=engine_input.user_id,
                recent_responses=recent_responses
            )

            # If it fails ranker, try to regenerate exactly once (limit 1 retry) if primary provider was used and not local fallback
            if not rank_result.passes and orch_res.provider != "local":
                logger.warning(
                    "ENGINE | Orchestrator response failed ranker quality check. Attempting exactly 1 regeneration (retry) with calibrated prompt. UserID: %s, Score: %.4f",
                    engine_input.user_id, rank_result.score
                )
                retry_count += 1

                # Calibrate retry instructions based on ranker failure reasons
                retry_instr = build_retry_quality_instruction(rank_result.reasons)

                # Re-build system prompt and messages with the quality instructions
                retry_system_prompt, _ = build_system_prompt(
                    language=engine_input.language,
                    emotion=engine_input.emotion,
                    risk=engine_input.risk,
                    memory_context=memory_context_str,
                    preferences=engine_input.preferences.model_dump() if hasattr(engine_input.preferences, "model_dump") else engine_input.preferences.dict(),
                    text=engine_input.text,
                    retry_instruction=retry_instr,
                    subtype=engine_input.subtype,
                    strategy=engine_input.strategy,
                    variation_directive=variation_directive,
                    theme=engine_input.theme,
                    need=engine_input.need,
                    intent=engine_input.intent,
                    conversation_pattern=conversation_pattern,
                )

                retry_messages = build_messages(
                    user_id=engine_input.user_id,
                    system_prompt=retry_system_prompt,
                    user_prompt=user_prompt,
                    limit=self.config.max_memory_length,
                    emotion=engine_input.emotion,
                    risk=engine_input.risk,
                )

                orch_res = ai_orchestrator.generate_response(
                    messages=retry_messages,
                    model_config=model_config,
                    bypass_openai=engine_input.preferences.privacy_mode
                )
                final_text = orch_res.text
                ai_provider = orch_res.provider
                ai_model = orch_res.model
                ai_latency_ms += orch_res.latency_ms
                ai_fallback_used = orch_res.fallback_used
                ai_cost_estimate += orch_res.cost_estimate
                is_fallback = orch_res.fallback_used
                final_model = orch_res.model
                if orch_res.fallback_used:
                    fallback_reason = orch_res.error or "primary_failed"
                    fallback_model_used = orch_res.model
                else:
                    primary_model_used = orch_res.model
                    fallback_model_used = None

                rank_result = score_response(
                    final_text,
                    emotion=engine_input.emotion,
                    risk=engine_input.risk,
                    user_id=engine_input.user_id,
                    recent_responses=recent_responses
                )

            # Fall back to local provider if still failing the rank check
            if not rank_result.passes:
                logger.warning(
                    "ENGINE | Orchestrator response failed ranker quality check (UserID: %s, Score: %.4f). Switching to local fallback.",
                    engine_input.user_id, rank_result.score
                )
                orch_res = ai_orchestrator._execute_fallback(messages, model_config, "ranker_quality_failed")
                final_text = orch_res.text
                ai_provider = orch_res.provider
                ai_model = orch_res.model
                ai_fallback_used = True
                is_fallback = True
                final_model = orch_res.model
                fallback_reason = "ranker_quality_failed"
                fallback_model_used = orch_res.model

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

        # [NEW] Scan response to track advice topics for repetition prevention (only on safe turns)
        if is_safe:
            try:
                from src.response_engine.memory_profile import detect_and_add_advice_topics
                detect_and_add_advice_topics(engine_input.user_id, final_text)
            except Exception as advice_err:
                logger.error(f"ENGINE | Failed to detect and track advice topics: {advice_err}")

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
            "persistent_memory_enabled: %s | memory_count: %d | selected_memory_count: %d | "
            "memory_injected: %s | memory_candidates: %d | "
            "memory_filtered_privacy: %d | memory_filtered_crisis: %d | "
            "memory_lookup_latency: %.4fs | "
            "prompt_version: %s | prompt_sections: %s | prompt_length: %d | injection_guard_enabled: %s | "
            "pref_style: %s | pref_len: %s | pref_privacy: %s | counseling_category: %s",
            engine_input.user_id,
            latency,
            final_model,
            primary_model_used,
            fallback_model_used,
            retry_count,
            rank_result.score,
            rank_result.reasons,
            fallback_reason,
            True,
            memory_meta.get("memory_count", 0),
            memory_meta.get("selected_memory_count", 0),
            memory_meta.get("memory_injected", False),
            memory_meta.get("memory_candidates", 0),
            memory_meta.get("memory_filtered_privacy", 0),
            memory_meta.get("memory_filtered_crisis", 0),
            memory_lookup_latency,
            prompt_meta.get("prompt_version", PROMPT_VERSION),
            prompt_meta.get("prompt_sections", []),
            prompt_meta.get("prompt_length", 0),
            prompt_meta.get("injection_guard_enabled", True),
            engine_input.preferences.response_style,
            engine_input.preferences.answer_length_preference,
            engine_input.preferences.privacy_mode,
            prompt_meta.get("counseling_category", "neutral")
        )
        
        return EngineOutput(
            final_text=final_text,
            is_fallback=is_fallback,
            metadata={
                "latency_sec": latency,
                "final_model": final_model,
                "error": error_meta,
                "counseling_category": prompt_meta.get("counseling_category", "neutral"),
                "subtype": engine_input.subtype,
                "strategy": engine_input.strategy,
                "variation": variation_id,
                "conversation_pattern": conversation_pattern,
                "psychological_understanding": {
                    "theme": engine_input.theme,
                    "need":  engine_input.need,
                    "intent": engine_input.intent,
                    # Lightweight internal strategy tag: 'decision_support' for problem_solving,
                    # 'reflection' for self_reflection. No DB schema change.
                    "strategy_tag": (
                        "decision_support" if engine_input.intent == "problem_solving"
                        else engine_input.strategy or ""
                    ),
                },
                "is_crisis": (crisis_level in ["high", "imminent", "medium"]),
                "crisis_level": crisis_level,
                "show_emergency_support": (crisis_level in ["high", "imminent"]),
                "emergency_phone": "112" if crisis_level in ["high", "imminent"] else None,
                "emergency_title": "Acil Destek" if crisis_level in ["high", "imminent"] else None,
                "emergency_message": "Güvende kalman öncelikli. Yalnız kalmamaya çalış ve mümkünse hemen destek al." if crisis_level in ["high", "imminent"] else None,
                "ranking": {
                    "primary_model_used": primary_model_used,
                    "fallback_model_used": fallback_model_used,
                    "retry_count": retry_count,
                    "quality_score": round(rank_result.score, 4),
                    "quality_reasons": rank_result.reasons,
                    "fallback_reason": fallback_reason or None,
                },
                "memory": {
                    "persistent_memory_enabled": True,
                    "memory_count": memory_meta.get("memory_count", 0),
                    "selected_memory_count": memory_meta.get("selected_memory_count", 0),
                    "memory_injected": memory_meta.get("memory_injected", False),
                    "memory_candidates": memory_meta.get("memory_candidates", 0),
                    "memory_filtered_privacy": memory_meta.get("memory_filtered_privacy", 0),
                    "memory_filtered_crisis": memory_meta.get("memory_filtered_crisis", 0),
                    "memory_lookup_latency": round(memory_lookup_latency, 4)
                },
                "preferences": {
                    "response_style": engine_input.preferences.response_style,
                    "answer_length_preference": engine_input.preferences.answer_length_preference,
                    "privacy_mode": engine_input.preferences.privacy_mode
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
