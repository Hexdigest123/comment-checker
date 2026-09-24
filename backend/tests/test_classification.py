"""Tests for score-derived confidence and severity."""

import pytest

from src.db.models import ClassificationSeverity
from src.services.classification import (
    _confidence_and_severity,
    _severity_from_score,
    classify_with_mistral,
)


MOCK_SCORES = {
    "hate_and_discrimination": 0.02,
    "violence_and_threats": 0.01,
    "sexual": 0.0,
    "dangerous": 0.0,
    "criminal": 0.0,
    "selfharm": 0.0,
    "financial": 0.25,
    "pii": 0.0,
}


class TestSeverityFromScore:
    def test_bins(self):
        assert _severity_from_score(0.95) == ClassificationSeverity.CRITICAL
        assert _severity_from_score(0.9) == ClassificationSeverity.CRITICAL
        assert _severity_from_score(0.75) == ClassificationSeverity.HIGH
        assert _severity_from_score(0.7) == ClassificationSeverity.HIGH
        assert _severity_from_score(0.55) == ClassificationSeverity.MEDIUM
        assert _severity_from_score(0.5) == ClassificationSeverity.MEDIUM
        assert _severity_from_score(0.35) == ClassificationSeverity.LOW
        assert _severity_from_score(0.0) == ClassificationSeverity.LOW


class TestConfidenceAndSeverity:
    def test_flagged_uses_winning_label_score(self):
        scores = dict(MOCK_SCORES, hate_and_discrimination=0.85)
        confidence, severity = _confidence_and_severity(scores, flagged=True)
        assert confidence == 0.85
        assert severity == ClassificationSeverity.HIGH

    def test_safe_uses_inverse_of_max_mapped_score(self):
        # financial (0.25) is mapped and drives the result
        confidence, severity = _confidence_and_severity(MOCK_SCORES, flagged=False)
        assert confidence == 0.75
        assert severity == ClassificationSeverity.LOW

    def test_flagged_fallback_injected_score(self):
        scores = dict(MOCK_SCORES, hate_speech=1.0)
        confidence, severity = _confidence_and_severity(scores, flagged=True)
        assert confidence == 1.0
        assert severity == ClassificationSeverity.CRITICAL

    def test_empty_scores(self):
        assert _confidence_and_severity({}, flagged=False) == (1.0, ClassificationSeverity.LOW)
        assert _confidence_and_severity({}, flagged=True) == (0.0, ClassificationSeverity.LOW)


class FakeLLMClient:
    """Stands in for the Mistral Moderation 2 client."""

    def __init__(self, scores, second_opinion=False, **kwargs):
        self._scores = scores
        self._second_opinion = second_opinion

    def classify(self, comment):
        return dict(self._scores)

    def check_with_context(self, comment):
        return self._second_opinion


class TestClassifyWithMistral:
    @pytest.mark.asyncio
    async def test_returns_derived_confidence_and_severity(self, monkeypatch):
        scores = dict(MOCK_SCORES, hate_and_discrimination=0.85)
        monkeypatch.setattr(
            "src.services.mistral_client.LLMClient", lambda **kw: FakeLLMClient(scores, **kw)
        )

        result = await classify_with_mistral("some comment")

        assert result["confidence"] == 0.85
        assert result["severity"] == "high"
        assert result["flagged"] is True
        assert result["flagged_by"] == "mistral_moderation"
        assert result["harmful"] == 0.85

    @pytest.mark.asyncio
    async def test_safe_comment(self, monkeypatch):
        monkeypatch.setattr(
            "src.services.mistral_client.LLMClient", lambda **kw: FakeLLMClient(MOCK_SCORES, **kw)
        )

        result = await classify_with_mistral("some comment", fallback=False)

        assert result["confidence"] == 0.75
        assert result["severity"] == "low"
        assert result["flagged"] is False
        assert result["flagged_by"] is None
        assert result["harmful"] == 0.25

    @pytest.mark.asyncio
    async def test_fallback_flagged_comment(self, monkeypatch):
        monkeypatch.setattr(
            "src.services.mistral_client.LLMClient",
            lambda **kw: FakeLLMClient(MOCK_SCORES, second_opinion=True, **kw),
        )

        result = await classify_with_mistral("some comment")

        assert result["confidence"] == 1.0
        assert result["severity"] == "critical"
        assert result["flagged_by"] == "mistral_fallback"
        assert result["harmful"] == 1.0
