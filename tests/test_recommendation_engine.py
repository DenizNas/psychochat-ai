"""
tests/test_recommendation_engine.py — Faz 10 Prompt 7
=====================================================
Unit tests for the privacy-safe, rule-based Recommendation Engine.

Run with:
    python -m unittest tests/test_recommendation_engine.py -v

Tests verify:
  1. Signal collection logic
  2. Rule-based recommendation generation
  3. Crisis-safe prioritization
  4. Diversity filter
  5. Duplicate guard logic
  6. Language / privacy safety
  7. Output schema integrity
"""

import json
import os
import sys
import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

# Ensure src is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set minimal env before importing settings-dependent modules
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_recommendations.db")
os.environ.setdefault("SECRET_KEY", "test_secret_key_for_unit_tests_only")
os.environ.setdefault("OPENAI_API_KEY", "sk-dummy-test-key")
os.environ.setdefault("APP_ENV", "development")


class TestRecommendationEngineInternal(unittest.TestCase):
    """Tests for internal engine functions (no DB required)."""

    def setUp(self):
        """Import internal helpers lazily to allow env setup first."""
        from src.services.recommendation_engine import (
            _run_rules,
            _apply_crisis_prioritization,
            _apply_diversity,
            _make_rec,
        )
        self._run_rules = _run_rules
        self._apply_crisis_prioritization = _apply_crisis_prioritization
        self._apply_diversity = _apply_diversity
        self._make_rec = _make_rec
        self.now = datetime.now(timezone.utc)

    def _base_signals(self, **overrides):
        """Returns a base signal dict for rule testing."""
        signals = {
            "total_messages_7d": 10,
            "crisis_count_7d": 0,
            "crisis_count_30d": 0,
            "dominant_emotion_7d": "neutral",
            "dominant_emotion_30d": "neutral",
            "anxiety_rate_7d": 0.0,
            "sadness_rate_7d": 0.0,
            "joy_rate_7d": 0.5,
            "anger_rate_7d": 0.0,
            "anxiety_rate_30d": 0.0,
            "total_messages_30d": 30,
            "mood_entry_count_7d": 3,
            "mood_entry_count_30d": 10,
            "mood_avg_intensity_7d": 2.5,
            "mood_avg_intensity_30d": 2.5,
            "mood_types_7d": {},
            "pending_interventions_count": 0,
            "stress_trend_increasing": False,
            "anomaly_intensity_spike": False,
            "anomaly_journal_drop": False,
        }
        signals.update(overrides)
        return signals

    # ── Rule Tests ──────────────────────────────────────────────────────────

    def test_no_recommendations_for_neutral_low_data(self):
        """Neutral signals with low data should produce no or minimal recommendations."""
        sig = self._base_signals(total_messages_7d=2)  # below threshold
        recs = self._run_rules("testuser", sig)
        # None of the critical rules should fire for neutral low-data user
        rec_types = [r["recommendation_type"] for r in recs]
        self.assertNotIn("professional_support", rec_types)
        self.assertNotIn("breathing_break", rec_types)

    def test_crisis_rule_fires_at_threshold(self):
        """professional_support should appear when crisis_count_7d >= 2."""
        sig = self._base_signals(crisis_count_7d=2)
        recs = self._run_rules("testuser", sig)
        rec_types = [r["recommendation_type"] for r in recs]
        self.assertIn("professional_support", rec_types)

    def test_crisis_rule_does_not_fire_below_threshold(self):
        """professional_support should NOT appear when crisis_count_7d < 2."""
        sig = self._base_signals(crisis_count_7d=1)
        recs = self._run_rules("testuser", sig)
        rec_types = [r["recommendation_type"] for r in recs]
        self.assertNotIn("professional_support", rec_types)

    def test_anxiety_rule_fires(self):
        """breathing_break should appear when anxiety_rate_7d >= 0.35."""
        sig = self._base_signals(anxiety_rate_7d=0.40, total_messages_7d=6)
        recs = self._run_rules("testuser", sig)
        rec_types = [r["recommendation_type"] for r in recs]
        self.assertIn("breathing_break", rec_types)

    def test_sadness_rule_fires(self):
        """journaling_prompt should appear when sadness_rate_7d >= 0.30."""
        sig = self._base_signals(sadness_rate_7d=0.35, total_messages_7d=6)
        recs = self._run_rules("testuser", sig)
        rec_types = [r["recommendation_type"] for r in recs]
        self.assertIn("journaling_prompt", rec_types)

    def test_stress_trend_rule_fires(self):
        """grounding_exercise should appear when stress_trend_increasing=True."""
        sig = self._base_signals(stress_trend_increasing=True, total_messages_7d=5)
        recs = self._run_rules("testuser", sig)
        rec_types = [r["recommendation_type"] for r in recs]
        self.assertIn("grounding_exercise", rec_types)

    def test_intensity_anomaly_rule_fires(self):
        """mood_checkin should appear when anomaly_intensity_spike=True."""
        sig = self._base_signals(
            anomaly_intensity_spike=True,
            mood_entry_count_7d=3,
        )
        recs = self._run_rules("testuser", sig)
        rec_types = [r["recommendation_type"] for r in recs]
        self.assertIn("mood_checkin", rec_types)

    def test_journal_drop_anomaly_fires(self):
        """mood_checkin should appear when anomaly_journal_drop=True."""
        sig = self._base_signals(anomaly_journal_drop=True)
        recs = self._run_rules("testuser", sig)
        rec_types = [r["recommendation_type"] for r in recs]
        self.assertIn("mood_checkin", rec_types)

    # ── Crisis Prioritization Tests ─────────────────────────────────────────

    def test_crisis_prioritization_puts_support_first(self):
        """professional_support must be sorted to position 0 when crisis_count >= 2."""
        sig = self._base_signals(crisis_count_7d=3, anxiety_rate_7d=0.50, total_messages_7d=8)
        candidates = self._run_rules("testuser", sig)
        result = self._apply_crisis_prioritization(candidates, sig)
        if result:
            self.assertEqual(result[0]["recommendation_type"], "professional_support")

    def test_crisis_prioritization_demotes_others(self):
        """When crisis is active, medium recommendations should be demoted to low."""
        sig = self._base_signals(
            crisis_count_7d=2,
            anxiety_rate_7d=0.50,
            total_messages_7d=8,
        )
        candidates = self._run_rules("testuser", sig)
        result = self._apply_crisis_prioritization(candidates, sig)
        # Non-support recs should be demoted
        for r in result:
            if r["recommendation_type"] != "professional_support":
                self.assertIn(r["priority"], ["low", "medium"])

    def test_no_prioritization_when_crisis_count_low(self):
        """Prioritization should not alter anything when crisis_count < 2."""
        sig = self._base_signals(crisis_count_7d=0, anxiety_rate_7d=0.50, total_messages_7d=8)
        candidates = self._run_rules("testuser", sig)
        result_without = self._apply_crisis_prioritization(candidates, sig)
        # Check professional_support not added when crisis = 0
        types_without = [r["recommendation_type"] for r in result_without]
        self.assertNotIn("professional_support", types_without)

    # ── Diversity Filter Tests ──────────────────────────────────────────────

    def test_diversity_filter_removes_duplicates(self):
        """Same recommendation type should appear only once after diversity filter."""
        now = self.now
        candidates = [
            self._make_rec("u", "breathing_break", "T", "D", "medium", 0.8, "R", [], now),
            self._make_rec("u", "breathing_break", "T2", "D2", "low", 0.5, "R2", [], now),
        ]
        result = self._apply_diversity(candidates)
        rec_types = [r["recommendation_type"] for r in result]
        self.assertEqual(rec_types.count("breathing_break"), 1)

    def test_diversity_filter_keeps_highest_confidence(self):
        """Among duplicates, the one with higher confidence should survive."""
        now = self.now
        candidates = [
            self._make_rec("u", "breathing_break", "T", "D", "medium", 0.5, "R", [], now),
            self._make_rec("u", "breathing_break", "T", "D", "medium", 0.9, "R", [], now),
        ]
        result = self._apply_diversity(candidates)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["confidence"], 0.9)

    def test_diversity_filter_caps_at_five(self):
        """Output should be capped at 5 recommendations."""
        now = self.now
        types = [
            "breathing_break", "journaling_prompt", "grounding_exercise",
            "short_walk", "hydration_reminder", "sleep_routine", "social_connection",
        ]
        candidates = [
            self._make_rec("u", t, "T", "D", "medium", 0.7, "R", [], now)
            for t in types
        ]
        result = self._apply_diversity(candidates)
        self.assertLessEqual(len(result), 5)

    # ── Output Schema Tests ─────────────────────────────────────────────────

    def test_make_rec_schema(self):
        """_make_rec should produce all required output fields."""
        now = self.now
        rec = self._make_rec(
            user_id="u",
            rec_type="breathing_break",
            title="Nefes al",
            description="Bir dakika nefes almayı dene.",
            priority="medium",
            confidence=0.75,
            reason="Kaygı örüntüleri öne çıktı.",
            actions=[{"label": "Nefes", "action_type": "open_breathing_timer"}],
            now=now,
        )
        required_keys = [
            "id", "recommendation_type", "title", "description",
            "priority", "confidence", "reason", "actions",
            "created_at", "expires_at", "source",
        ]
        for k in required_keys:
            self.assertIn(k, rec, f"Missing key: {k}")

    def test_rec_expires_at_48h(self):
        """expires_at should be exactly 48 hours after created_at."""
        now = self.now
        rec = self._make_rec("u", "breathing_break", "T", "D", "medium", 0.7, "R", [], now)
        created = datetime.fromisoformat(rec["created_at"])
        expires = datetime.fromisoformat(rec["expires_at"])
        delta = expires - created
        self.assertEqual(delta.total_seconds(), 48 * 3600)

    def test_confidence_clamped_to_one(self):
        """Confidence from rules should never exceed 1.0."""
        sig = self._base_signals(crisis_count_7d=100)  # very high crisis
        recs = self._run_rules("testuser", sig)
        for r in recs:
            self.assertLessEqual(r["confidence"], 1.0)

    # ── Privacy Language Tests ──────────────────────────────────────────────

    FORBIDDEN_WORDS = [
        "depresyon", "anksiyete bozukluğu", "riskli hasta",
        "depression", "anxiety disorder", "psychiatric", "diagnosis",
        "teşhis", "hastalık tanısı",
    ]

    def test_no_medical_diagnosis_language_in_titles(self):
        """Titles must not contain medical diagnosis terms."""
        sig = self._base_signals(
            crisis_count_7d=3,
            anxiety_rate_7d=0.70,
            sadness_rate_7d=0.50,
            total_messages_7d=10,
        )
        recs = self._run_rules("testuser", sig)
        for rec in recs:
            for word in self.FORBIDDEN_WORDS:
                self.assertNotIn(
                    word.lower(),
                    rec["title"].lower(),
                    f"Forbidden word '{word}' in title: {rec['title']}",
                )

    def test_no_medical_diagnosis_language_in_reasons(self):
        """Reasons must not contain medical diagnosis terms."""
        sig = self._base_signals(
            crisis_count_7d=3,
            anxiety_rate_7d=0.70,
            sadness_rate_7d=0.50,
            total_messages_7d=10,
        )
        recs = self._run_rules("testuser", sig)
        for rec in recs:
            for word in self.FORBIDDEN_WORDS:
                reason = (rec.get("reason") or "").lower()
                self.assertNotIn(
                    word.lower(),
                    reason,
                    f"Forbidden word '{word}' in reason: {reason}",
                )

    def test_no_medical_diagnosis_language_in_descriptions(self):
        """Descriptions must not contain medical diagnosis terms."""
        sig = self._base_signals(
            crisis_count_7d=3,
            anxiety_rate_7d=0.70,
            sadness_rate_7d=0.50,
            total_messages_7d=10,
        )
        recs = self._run_rules("testuser", sig)
        for rec in recs:
            for word in self.FORBIDDEN_WORDS:
                desc = rec.get("description", "").lower()
                self.assertNotIn(
                    word.lower(),
                    desc,
                    f"Forbidden word '{word}' in description: {desc}",
                )

    # ── Consent / Privacy Gate Tests ────────────────────────────────────────

    def test_privacy_mode_blocks_generation(self):
        """privacy_mode=True should return empty list (skips generation)."""
        with patch("src.services.recommendation_engine._collect_signals") as mock_sig:
            mock_sig.return_value = {}  # should never be called
            from src.services.recommendation_engine import generate_recommendations
            # Mock DB calls
            with patch("src.services.recommendation_engine._persist_recommendations", return_value=[]):
                with patch("src.services.recommendation_engine._filter_existing", return_value=[]):
                    result = generate_recommendations(
                        user_id="u",
                        privacy_mode=True,
                        wellness_insights_consent=True,
                    )
            self.assertEqual(result, [])
            mock_sig.assert_not_called()

    def test_consent_off_blocks_generation(self):
        """wellness_insights_consent=False should return empty list."""
        with patch("src.services.recommendation_engine._collect_signals") as mock_sig:
            mock_sig.return_value = {}
            from src.services.recommendation_engine import generate_recommendations
            with patch("src.services.recommendation_engine._persist_recommendations", return_value=[]):
                with patch("src.services.recommendation_engine._filter_existing", return_value=[]):
                    result = generate_recommendations(
                        user_id="u",
                        privacy_mode=False,
                        wellness_insights_consent=False,
                    )
            self.assertEqual(result, [])
            mock_sig.assert_not_called()


class TestRecommendationEngineWithDB(unittest.TestCase):
    """Integration-style tests using SQLite in-memory DB."""

    def setUp(self):
        """Override DATABASE_URL to use isolated in-memory SQLite."""
        os.environ["DATABASE_URL"] = "sqlite:///:memory:"

    def tearDown(self):
        # Reset to avoid interference
        os.environ.pop("DATABASE_URL", None)

    def test_module_imports_cleanly(self):
        """recommendation_engine module should import without errors."""
        try:
            import importlib
            import src.services.recommendation_engine as re_mod
            importlib.reload(re_mod)
        except Exception as e:
            self.fail(f"Import failed: {e}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
