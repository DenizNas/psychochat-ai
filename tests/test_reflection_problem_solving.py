"""
test_reflection_problem_solving.py — Phase 4.1 Sprint 7.4

Verifies that self_reflection and problem_solving intents produce
clearly different counseling experiences, and that crisis bypass
suppresses both intent directives entirely.

Tests:
    1. "Neden hep böyle hissediyorum?"  → self_reflection, reflective response
    2. "Kendimi anlamıyorum."            → self_reflection, understanding-focused response
    3. "Bu iki seçenek arasında kaldım." → problem_solving, decision-support response
    4. "Hangi seçeneği seçmeliyim?"      → problem_solving, comparison framing
    5. "Artık yaşamak istemiyorum."      → crisis bypass, no intent directives
"""

import sys
import unittest
import re

sys.path.insert(0, ".")

from src.core.config import settings
from src.response_engine.theme_need_engine import detect_theme_and_need
from src.response_engine.engine import response_engine
from src.response_engine.models import EngineInput, UserPreferences
from src.ai_providers import ai_orchestrator
from src.ai_providers.mock_provider import MockProvider
from src.core.redis_client import redis_client


class CaptureSystemPromptMockProvider(MockProvider):
    """Mock provider that captures the last system prompt for assertion."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.last_system_prompt = None

    def generate(self, messages, model_config):
        for msg in messages:
            if msg.get("role") == "system":
                self.last_system_prompt = msg.get("content")
        return super().generate(messages, model_config)


class TestReflectionProblemSolving(unittest.TestCase):

    def setUp(self):
        self.original_primary_provider = settings.AI_PRIMARY_PROVIDER
        self.original_api_key = settings.OPENAI_API_KEY
        self.original_max_retries = settings.AI_MAX_RETRIES

        # Disable Redis to speed up unit tests
        redis_client._client = False

        self.mock_provider = CaptureSystemPromptMockProvider(
            mock_response="Empatik ve yapılandırılmış test yanıtı."
        )
        ai_orchestrator.register_provider("mock_provider", self.mock_provider)

        settings.AI_PRIMARY_PROVIDER = "mock_provider"
        settings.OPENAI_API_KEY = ""
        settings.AI_MAX_RETRIES = 0

    def tearDown(self):
        settings.AI_PRIMARY_PROVIDER = self.original_primary_provider
        settings.OPENAI_API_KEY = self.original_api_key
        settings.AI_MAX_RETRIES = self.original_max_retries

        ai_orchestrator.register_provider("openai", ai_orchestrator.openai_provider)
        ai_orchestrator.register_provider("local", ai_orchestrator.local_provider)

    # ------------------------------------------------------------------
    # Test 1 — "Neden hep böyle hissediyorum?"
    # Expected: intent=self_reflection, reflective language, one exploratory question
    # ------------------------------------------------------------------

    def test_1a_intent_detection_why_always_feeling(self):
        """TNE: 'Neden hep böyle hissediyorum?' → intent=self_reflection"""
        res = detect_theme_and_need(
            text="Neden hep böyle hissediyorum?",
            emotion="sadness",
            subtype=None
        )
        self.assertEqual(res["intent"], "self_reflection",
                         f"Expected self_reflection, got: {res['intent']}")

    def test_1b_local_response_why_always_feeling(self):
        """Local fallback: 'Neden hep böyle hissediyorum?' → reflective + exploratory question."""
        inp = EngineInput(
            user_id="test_sr_1",
            text="Neden hep böyle hissediyorum?",
            emotion="sadness",
            risk="Normal",
            preferences=UserPreferences(privacy_mode=True)
        )
        res = response_engine.generate_response(inp)
        text = res.final_text

        # Intent must be self_reflection
        self.assertEqual(
            res.metadata["psychological_understanding"]["intent"],
            "self_reflection",
            f"Expected self_reflection intent, got: {res.metadata['psychological_understanding']['intent']}"
        )

        # Must contain a reflective/exploratory question
        self.assertIn("?", text, "Response must contain at least one question mark.")

        # Must NOT contain action advice keywords
        advice_keywords = ["öneririm", "deneyebilirsin", "adım at", "şunu yap",
                           "egzersiz", "nefes al", "pratik", "liste yap"]
        for kw in advice_keywords:
            self.assertNotIn(kw, text.lower(),
                             f"Forbidden advice keyword '{kw}' found in self_reflection response.")

    def test_1c_system_prompt_why_always_feeling(self):
        """System prompt: 'Neden hep böyle hissediyorum?' → self_reflection directives injected."""
        inp = EngineInput(
            user_id="test_sr_1_prompt",
            text="Neden hep böyle hissediyorum?",
            emotion="sadness",
            risk="Normal"
        )
        response_engine.generate_response(inp)
        prompt = self.mock_provider.last_system_prompt
        self.assertIsNotNone(prompt)
        self.assertIn("NİYET VE YAPI KURALI (Kendini Sorgulama / self_reflection)", prompt,
                      "self_reflection directive must be present in system prompt.")
        # Verify forbidden advice language injected as a rule
        self.assertIn("YASAKTIR", prompt)

    # ------------------------------------------------------------------
    # Test 2 — "Kendimi anlamıyorum."
    # Expected: intent=self_reflection, understanding-focused response
    # ------------------------------------------------------------------

    def test_2a_intent_detection_dont_understand_myself(self):
        """TNE: 'Kendimi anlamıyorum.' → intent=self_reflection"""
        res = detect_theme_and_need(
            text="Kendimi anlamıyorum.",
            emotion="sadness",
            subtype=None
        )
        self.assertEqual(res["intent"], "self_reflection",
                         f"Expected self_reflection, got: {res['intent']}")

    def test_2b_local_response_dont_understand_myself(self):
        """Local fallback: 'Kendimi anlamıyorum.' → self-understanding focused, no advice."""
        inp = EngineInput(
            user_id="test_sr_2",
            text="Kendimi anlamıyorum.",
            emotion="sadness",
            risk="Normal",
            preferences=UserPreferences(privacy_mode=True)
        )
        res = response_engine.generate_response(inp)
        text = res.final_text

        self.assertEqual(
            res.metadata["psychological_understanding"]["intent"],
            "self_reflection",
            f"Expected self_reflection, got: {res.metadata['psychological_understanding']['intent']}"
        )

        # Response must contain a question (exploratory)
        self.assertIn("?", text, "self_reflection response must contain a question.")

        # Must NOT contain action planning language
        action_keywords = ["öneririm", "adım at", "şunu yap", "deneyebilirsin"]
        for kw in action_keywords:
            self.assertNotIn(kw, text.lower(),
                             f"Action keyword '{kw}' must not appear in self_reflection response.")

    # ------------------------------------------------------------------
    # Test 3 — "Bu iki seçenek arasında kaldım."
    # Expected: intent=problem_solving, dilemma acknowledgement + decision structure
    # ------------------------------------------------------------------

    def test_3a_intent_detection_two_options(self):
        """TNE: 'Bu iki seçenek arasında kaldım.' → intent=problem_solving"""
        res = detect_theme_and_need(
            text="Bu iki seçenek arasında kaldım.",
            emotion="uncertainty",
            subtype=None
        )
        self.assertEqual(res["intent"], "problem_solving",
                         f"Expected problem_solving, got: {res['intent']}")

    def test_3b_local_response_two_options(self):
        """Local fallback: 'Bu iki seçenek arasında kaldım.' → dilemma ack + decision framing."""
        inp = EngineInput(
            user_id="test_ps_3",
            text="Bu iki seçenek arasında kaldım.",
            emotion="uncertainty",
            risk="Normal",
            preferences=UserPreferences(privacy_mode=True)
        )
        res = response_engine.generate_response(inp)
        text = res.final_text

        # Intent must be problem_solving
        self.assertEqual(
            res.metadata["psychological_understanding"]["intent"],
            "problem_solving",
            f"Expected problem_solving, got: {res.metadata['psychological_understanding']['intent']}"
        )

        # strategy_tag must be decision_support
        self.assertEqual(
            res.metadata["psychological_understanding"].get("strategy_tag"),
            "decision_support",
            "strategy_tag must be 'decision_support' for problem_solving intent."
        )

        # Must acknowledge the dilemma/tiredness of being stuck
        dilemma_markers = ["yorucu", "ikilem", "seçenek", "ağır", "arasında"]
        has_dilemma_ack = any(m in text.lower() for m in dilemma_markers)
        self.assertTrue(has_dilemma_ack,
                        f"Response must acknowledge the dilemma. Got: '{text}'")

        # Must contain decision-support framing keywords
        decision_markers = ["artı", "eksi", "değer", "seçenek", "hangisi", "karar"]
        has_decision_framing = any(m in text.lower() for m in decision_markers)
        self.assertTrue(has_decision_framing,
                        f"Response must contain decision-support framing. Got: '{text}'")

    def test_3c_system_prompt_two_options(self):
        """System prompt: 'Bu iki seçenek arasında kaldım.' → problem_solving directives injected."""
        inp = EngineInput(
            user_id="test_ps_3_prompt",
            text="Bu iki seçenek arasında kaldım.",
            emotion="uncertainty",
            risk="Normal"
        )
        response_engine.generate_response(inp)
        prompt = self.mock_provider.last_system_prompt
        self.assertIsNotNone(prompt)
        self.assertIn("NİYET VE YAPI KURALI (Problem Çözme / problem_solving)", prompt,
                      "problem_solving directive must be present in system prompt.")

    # ------------------------------------------------------------------
    # Test 4 — "Hangi seçeneği seçmeliyim?"
    # Expected: intent=problem_solving, comparison framing, no advice dumping
    # ------------------------------------------------------------------

    def test_4a_intent_detection_which_option(self):
        """TNE: 'Hangi seçeneği seçmeliyim?' → intent=problem_solving"""
        res = detect_theme_and_need(
            text="Hangi seçeneği seçmeliyim?",
            emotion="uncertainty",
            subtype=None
        )
        self.assertEqual(res["intent"], "problem_solving",
                         f"Expected problem_solving, got: {res['intent']}")

    def test_4b_local_response_which_option(self):
        """Local fallback: 'Hangi seçeneği seçmeliyim?' → decision framing, no advice dump."""
        inp = EngineInput(
            user_id="test_ps_4",
            text="Hangi seçeneği seçmeliyim?",
            emotion="uncertainty",
            risk="Normal",
            preferences=UserPreferences(privacy_mode=True)
        )
        res = response_engine.generate_response(inp)
        text = res.final_text

        self.assertEqual(
            res.metadata["psychological_understanding"]["intent"],
            "problem_solving",
            f"Expected problem_solving, got: {res.metadata['psychological_understanding']['intent']}"
        )

        # No bullet-list / advice dumping
        self.assertNotIn("1.", text, "No numbered advice list should appear.")
        self.assertNotIn("2.", text, "No numbered advice list should appear.")

        # Must contain decision-support language
        decision_markers = ["artı", "eksi", "değer", "seçenek", "hangisi", "karar", "karşılaştır"]
        has_framing = any(m in text.lower() for m in decision_markers)
        self.assertTrue(has_framing,
                        f"Response should contain decision-support framing. Got: '{text}'")

    def test_4c_system_prompt_which_option(self):
        """System prompt: 'Hangi seçeneği seçmeliyim?' → problem_solving directive injected."""
        inp = EngineInput(
            user_id="test_ps_4_prompt",
            text="Hangi seçeneği seçmeliyim?",
            emotion="uncertainty",
            risk="Normal"
        )
        response_engine.generate_response(inp)
        prompt = self.mock_provider.last_system_prompt
        self.assertIsNotNone(prompt)
        self.assertIn("NİYET VE YAPI KURALI (Problem Çözme / problem_solving)", prompt)

    # ------------------------------------------------------------------
    # Test 5 — "Artık yaşamak istemiyorum."
    # Expected: crisis bypass, NO reflection/problem-solving directives injected
    # ------------------------------------------------------------------

    def test_5_crisis_bypass_no_intent_directives(self):
        """Crisis bypass: 'Artık yaşamak istemiyorum.' → crisis template, no LLM call."""
        inp = EngineInput(
            user_id="test_crisis_5",
            text="Artık yaşamak istemiyorum.",
            emotion="sadness",
            risk="1"
        )
        self.mock_provider.last_system_prompt = None
        res = response_engine.generate_response(inp)

        # LLM must be bypassed — no system prompt sent
        self.assertIsNone(
            self.mock_provider.last_system_prompt,
            "System prompt must NOT be sent to LLM during crisis bypass."
        )

        # Crisis metadata must be present
        self.assertTrue(res.is_fallback, "Crisis response must be marked as fallback.")
        self.assertEqual(
            res.metadata["final_model"], "crisis_safe_template",
            "Final model must be 'crisis_safe_template' during crisis bypass."
        )

        # No self_reflection / problem_solving directives in the final text
        text = res.final_text
        self.assertNotIn(
            "NİYET VE YAPI KURALI (Kendini Sorgulama", text,
            "self_reflection directive must NOT appear in crisis response."
        )
        self.assertNotIn(
            "NİYET VE YAPI KURALI (Problem Çözme", text,
            "problem_solving directive must NOT appear in crisis response."
        )

    # ------------------------------------------------------------------
    # Additional regression: priority test (problem_solving > self_reflection)
    # ------------------------------------------------------------------

    def test_priority_problem_solving_over_self_reflection(self):
        """
        'Hangi seçeneği seçmeliyim, neden böyle hissediyorum?' contains both
        problem_solving and self_reflection triggers → must resolve to problem_solving.
        """
        res = detect_theme_and_need(
            text="Hangi seçeneği seçmeliyim, neden böyle hissediyorum?",
            emotion="uncertainty",
            subtype=None
        )
        self.assertEqual(
            res["intent"], "problem_solving",
            f"problem_solving must win over self_reflection. Got: {res['intent']}"
        )

    def test_priority_self_reflection_over_help_seeking(self):
        """
        'Neden hep böyle hissediyorum, ne yapabilirim?' contains both
        self_reflection and help_seeking triggers → must resolve to self_reflection.
        """
        res = detect_theme_and_need(
            text="Neden hep böyle hissediyorum, ne yapabilirim?",
            emotion="sadness",
            subtype=None
        )
        self.assertEqual(
            res["intent"], "self_reflection",
            f"self_reflection must win over help_seeking. Got: {res['intent']}"
        )

    # ------------------------------------------------------------------
    # Sprint 7.4 new trigger regression tests
    # ------------------------------------------------------------------

    def test_new_trigger_kendimi_cözemedim(self):
        """'Kendimi çözemedim.' → self_reflection"""
        res = detect_theme_and_need(
            text="Kendimi çözemedim.",
            emotion="sadness",
            subtype=None
        )
        self.assertEqual(res["intent"], "self_reflection")

    def test_new_trigger_neden_surekli(self):
        """'Neden sürekli böyle oluyorum?' → self_reflection"""
        res = detect_theme_and_need(
            text="Neden sürekli böyle oluyorum?",
            emotion="sadness",
            subtype=None
        )
        self.assertEqual(res["intent"], "self_reflection")

    def test_new_trigger_iki_secenek_arasinda_kaldim(self):
        """'İki seçenek arasında kaldım.' → problem_solving"""
        res = detect_theme_and_need(
            text="İki seçenek arasında kaldım.",
            emotion="uncertainty",
            subtype=None
        )
        self.assertEqual(res["intent"], "problem_solving")

    def test_new_trigger_kararimi_veremiyorum(self):
        """'Kararımı veremiyorum.' → problem_solving"""
        res = detect_theme_and_need(
            text="Kararımı veremiyorum.",
            emotion="uncertainty",
            subtype=None
        )
        self.assertEqual(res["intent"], "problem_solving")

    def test_new_trigger_hangisi_daha_mantikli(self):
        """'Hangisi daha mantıklı?' → problem_solving"""
        res = detect_theme_and_need(
            text="Hangisi daha mantıklı?",
            emotion="uncertainty",
            subtype=None
        )
        self.assertEqual(res["intent"], "problem_solving")

    def test_new_trigger_neyi_secmeliyim(self):
        """'Neyi seçmeliyim?' → problem_solving"""
        res = detect_theme_and_need(
            text="Neyi seçmeliyim?",
            emotion="uncertainty",
            subtype=None
        )
        self.assertEqual(res["intent"], "problem_solving")


if __name__ == "__main__":
    unittest.main()
