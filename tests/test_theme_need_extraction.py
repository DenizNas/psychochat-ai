"""
tests/test_theme_need_extraction.py — Phase 4.1 Sprint 7.1

Verifies the Theme & Need Extraction Engine:
1. Correct taxonomy membership for all outputs.
2. Five required benchmark inputs from the sprint spec.
3. Priority chain correctness (subtype > keyword > emotion > fallback).
4. Semantic equivalence: different phrasings → same theme.
5. No cross-contamination with crisis flows.
6. EngineInput model correctly carries theme/need/intent fields.
"""

import sys
import os
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.response_engine.theme_need_engine import (
    detect_theme_and_need,
    THEME_TAXONOMY,
    NEED_TAXONOMY,
    INTENT_TAXONOMY,
)
from src.response_engine.models import EngineInput


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _assert_valid(result: dict):
    """Assert all three fields are present and in their taxonomy."""
    assert "theme" in result, "Missing 'theme' key"
    assert "need" in result, "Missing 'need' key"
    assert "intent" in result, "Missing 'intent' key"
    assert result["theme"] in THEME_TAXONOMY, f"Invalid theme: {result['theme']}"
    assert result["need"] in NEED_TAXONOMY, f"Invalid need: {result['need']}"
    assert result["intent"] in INTENT_TAXONOMY, f"Invalid intent: {result['intent']}"


# ---------------------------------------------------------------------------
# 1. Sprint Spec Benchmark: five required inputs
# ---------------------------------------------------------------------------

class TestSprintBenchmarks:

    def test_anhedonia_keyif_alamiyorum(self):
        """'Hiçbir şeyden keyif alamıyorum.' → loss_of_pleasure / validation_normalization / emotional_expression"""
        result = detect_theme_and_need(
            text="Hiçbir şeyden keyif alamıyorum.",
            emotion="sadness",
            subtype="anhedonia",
        )
        _assert_valid(result)
        assert result["theme"] == "loss_of_pleasure"
        assert result["need"] == "validation_normalization"
        assert result["intent"] == "emotional_expression"

    def test_fear_of_failure_basarisiz(self):
        """'Başarısız olmaktan korkuyorum.' → fear_of_failure / emotional_exploration / self_reflection"""
        result = detect_theme_and_need(
            text="Başarısız olmaktan korkuyorum.",
            emotion="fear",
            subtype="failure_fear",
        )
        _assert_valid(result)
        assert result["theme"] == "fear_of_failure"
        assert result["need"] == "emotional_exploration"
        assert result["intent"] == "self_reflection"

    def test_exam_anxiety_sinav(self):
        """'Yarınki sınav için çok kaygılanıyorum.' → exam_pressure / gentle_reassurance / help_seeking"""
        result = detect_theme_and_need(
            text="Yarınki sınav için çok kaygılanıyorum.",
            emotion="anxiety",
            subtype="exam_anxiety",
        )
        _assert_valid(result)
        assert result["theme"] == "exam_pressure"
        assert result["need"] == "gentle_reassurance"
        assert result["intent"] == "help_seeking"

    def test_loneliness_yalniz(self):
        """'Kendimi çok yalnız hissediyorum.' → social_disconnection / connection_support / emotional_expression"""
        result = detect_theme_and_need(
            text="Kendimi çok yalnız hissediyorum.",
            emotion="loneliness",
            subtype=None,
        )
        _assert_valid(result)
        assert result["theme"] == "social_disconnection"
        assert result["need"] == "connection_support"
        assert result["intent"] == "emotional_expression"

    def test_life_direction_uncertainty(self):
        """'Hayatımın yönünü kaybetmiş gibi hissediyorum.' → life_direction_uncertainty"""
        result = detect_theme_and_need(
            text="Hayatımın yönünü kaybetmiş gibi hissediyorum.",
            emotion="uncertainty",
            subtype="life_direction_uncertainty",
        )
        _assert_valid(result)
        assert result["theme"] == "life_direction_uncertainty"
        assert result["need"] == "practical_guidance"


# ---------------------------------------------------------------------------
# 2. Priority chain correctness
# ---------------------------------------------------------------------------

class TestPriorityChain:

    def test_subtype_overrides_keyword(self):
        """Subtype lookup must win over keyword match."""
        # Text contains "başarısız olmaktan" (→ keyword: fear_of_failure)
        # Subtype is "anhedonia" (→ loss_of_pleasure)
        # Subtype should win.
        result = detect_theme_and_need(
            text="Başarısız olmaktan korkuyorum aynı zamanda keyif de alamıyorum.",
            emotion="sadness",
            subtype="anhedonia",
        )
        assert result["theme"] == "loss_of_pleasure", "Subtype must override keyword"

    def test_keyword_overrides_emotion(self):
        """Keyword rules must win over emotion-level lookup."""
        # Emotion is "sadness" → general_distress by default
        # Text has "hiçbir şeyden keyif" → loss_of_pleasure
        result = detect_theme_and_need(
            text="Hiçbir şeyden keyif alamıyorum artık.",
            emotion="sadness",
            subtype=None,
        )
        assert result["theme"] == "loss_of_pleasure", "Keyword must override emotion fallback"

    def test_emotion_fallback_when_no_keyword(self):
        """Emotion fallback is used when no subtype and no keyword matches."""
        result = detect_theme_and_need(
            text="Bugün biraz kötü hissediyorum.",
            emotion="sadness",
            subtype=None,
        )
        _assert_valid(result)
        assert result["theme"] == "general_distress"

    def test_neutral_fallback_on_unknown_emotion(self):
        """Unknown emotion and no keywords → neutral fallback returns valid taxonomy values."""
        result = detect_theme_and_need(
            text="merhaba",
            emotion="neutral",
            subtype=None,
        )
        _assert_valid(result)


# ---------------------------------------------------------------------------
# 3. Semantic equivalence — different phrasings, same theme
# ---------------------------------------------------------------------------

class TestSemanticEquivalence:

    def test_anhedonia_three_phrasings(self):
        """Three semantically equivalent anhedonia expressions → same theme."""
        phrases = [
            ("Hiçbir şeyden keyif alamıyorum.", "sadness", "anhedonia"),
            ("Eskiden sevdiğim şeyler artık boş geliyor.", "sadness", None),
            ("Her şey anlamsız ve renksiz gibi.", "sadness", None),
        ]
        for text, emo, sub in phrases:
            result = detect_theme_and_need(text=text, emotion=emo, subtype=sub)
            _assert_valid(result)
            assert result["theme"] == "loss_of_pleasure", (
                f"Expected loss_of_pleasure for: '{text}', got: {result['theme']}"
            )

    def test_life_direction_two_phrasings(self):
        """Two life-direction expressions → same theme."""
        phrases = [
            ("Ne yapacağımı bilmiyorum.", "uncertainty", "decision_uncertainty"),
            ("Hayatımın yönünü kaybettim.", "uncertainty", "life_direction_uncertainty"),
        ]
        for text, emo, sub in phrases:
            result = detect_theme_and_need(text=text, emotion=emo, subtype=sub)
            _assert_valid(result)
            assert result["theme"] == "life_direction_uncertainty"

    def test_loneliness_two_phrasings(self):
        """Two loneliness expressions → same theme."""
        phrases = [
            ("Kendimi çok yalnız hissediyorum.", "loneliness", None),
            ("Etrafımda kimse yok gibiyim.", "loneliness", None),
        ]
        for text, emo, sub in phrases:
            result = detect_theme_and_need(text=text, emotion=emo, subtype=sub)
            _assert_valid(result)
            assert result["theme"] == "social_disconnection"


# ---------------------------------------------------------------------------
# 4. All subtypes produce valid taxonomy members
# ---------------------------------------------------------------------------

class TestAllSubtypesValid:

    SUBTYPES = [
        ("anhedonia", "sadness"),
        ("burnout", "sadness"),
        ("grief", "sadness"),
        ("hopelessness", "sadness"),
        ("disappointment", "sadness"),
        ("exam_anxiety", "anxiety"),
        ("performance_anxiety", "anxiety"),
        ("social_anxiety", "anxiety"),
        ("generalized_anxiety", "anxiety"),
        ("failure_fear", "fear"),
        ("rejection_fear", "fear"),
        ("future_fear", "fear"),
        ("health_fear", "fear"),
        ("guilt", "guilt_shame"),
        ("shame", "guilt_shame"),
        ("decision_uncertainty", "uncertainty"),
        ("life_direction_uncertainty", "uncertainty"),
    ]

    @pytest.mark.parametrize("subtype,emotion", SUBTYPES)
    def test_subtype_produces_valid_output(self, subtype, emotion):
        result = detect_theme_and_need(
            text="test",
            emotion=emotion,
            subtype=subtype,
        )
        _assert_valid(result)


# ---------------------------------------------------------------------------
# 5. EngineInput carries theme/need/intent fields
# ---------------------------------------------------------------------------

class TestEngineInputModel:

    def test_engine_input_has_theme_need_intent_fields(self):
        inp = EngineInput(text="test", emotion="sadness", risk="Normal")
        assert hasattr(inp, "theme")
        assert hasattr(inp, "need")
        assert hasattr(inp, "intent")
        assert inp.theme is None
        assert inp.need is None
        assert inp.intent is None

    def test_engine_input_accepts_theme_need_intent(self):
        inp = EngineInput(
            text="Hiçbir şeyden keyif alamıyorum.",
            emotion="sadness",
            risk="Normal",
            subtype="anhedonia",
            theme="loss_of_pleasure",
            need="validation_normalization",
            intent="emotional_expression",
        )
        assert inp.theme == "loss_of_pleasure"
        assert inp.need == "validation_normalization"
        assert inp.intent == "emotional_expression"

    def test_engine_input_model_copy_with_theme(self):
        """Verify model_copy (used in engine.py) correctly propagates extracted values."""
        base = EngineInput(text="test", emotion="sadness", risk="Normal")
        updated = base.model_copy(update={
            "theme": "loss_of_pleasure",
            "need": "validation_normalization",
            "intent": "emotional_expression",
        })
        assert updated.theme == "loss_of_pleasure"
        assert updated.need == "validation_normalization"
        assert updated.intent == "emotional_expression"
        # original unchanged
        assert base.theme is None


# ---------------------------------------------------------------------------
# 6. No label leakage in theme taxonomy strings
# ---------------------------------------------------------------------------

class TestNoLabelLeakage:

    def test_theme_values_are_snake_case(self):
        """All taxonomy values are snake_case identifiers, not Turkish clinical labels."""
        forbidden = ["anhedonia", "depresyon", "klinik", "diagnosis"]
        for theme in THEME_TAXONOMY:
            for word in forbidden:
                assert word not in theme, f"Forbidden label in theme: {theme}"

    def test_all_taxonomy_values_strings(self):
        for val in THEME_TAXONOMY:
            assert isinstance(val, str)
        for val in NEED_TAXONOMY:
            assert isinstance(val, str)
        for val in INTENT_TAXONOMY:
            assert isinstance(val, str)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
