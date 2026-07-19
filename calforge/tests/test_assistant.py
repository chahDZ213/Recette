"""Tests for v0.5: AI context builder, offline analyst, provider dispatch,
and the Claude provider (with a faked SDK — no network)."""

from __future__ import annotations

import types
from pathlib import Path

import pytest
from tests.test_mapdetect import build_synthetic_dump

from calforge.ai.base import (
    AiContext,
    AiRequest,
    AiTask,
    ContextFact,
    ProviderUnavailableError,
)
from calforge.ai.providers.anthropic import AnthropicProvider
from calforge.ai.providers.offline import OfflineAnalyst
from calforge.app import ApplicationContext
from calforge.data.models import MapCandidateStatus
from calforge.services.dto import VehicleInput


@pytest.fixture
def file_with_map(context: ApplicationContext, tmp_path: Path):
    data, offset = build_synthetic_dump()
    path = tmp_path / "dump.bin"
    path.write_bytes(data)
    vehicle = context.vehicles.create(
        VehicleInput(make="VW", model="Golf", engine_code="DKFA")
    )
    file = context.ecu_files.import_file(path, vehicle_id=vehicle.id)
    return file, vehicle, offset


class TestContextBuilder:
    def test_file_context_is_factual(self, context: ApplicationContext, file_with_map) -> None:
        file, _vehicle, _offset = file_with_map
        ctx = context.assistant._builder.file_context(file.id)

        labels = {f.label: f.value for f in ctx.facts}
        assert labels["Nom du fichier"] == file.original_filename
        assert labels["Empreinte SHA-256"] == file.sha256
        assert labels["Véhicule"] == "VW Golf"
        # The detector's guesses arrive as hypotheses, not facts.
        assert all("carte" not in f.label.lower() or "validée" in f.label.lower() for f in ctx.facts)

    def test_detected_maps_are_hypotheses_with_confidence(
        self, context: ApplicationContext, file_with_map
    ) -> None:
        file, _vehicle, offset = file_with_map
        context.analysis.detect_maps(file.id)
        ctx = context.assistant._builder.file_context(file.id)

        map_hyps = [h for h in ctx.hypotheses if f"0x{offset:X}" in h.statement]
        assert map_hyps, "the detected map must appear as a hypothesis"
        assert all(0.0 <= h.confidence <= 1.0 and h.rationale for h in ctx.hypotheses)

    def test_validated_map_becomes_fact(
        self, context: ApplicationContext, file_with_map
    ) -> None:
        file, _vehicle, offset = file_with_map
        candidates = context.analysis.detect_maps(file.id)
        target = next(c for c in candidates if c.offset == offset)
        context.analysis.set_candidate_status(
            target.id, MapCandidateStatus.VALIDATED, name="Injection"
        )
        ctx = context.assistant._builder.file_context(file.id)
        assert any("Injection" in f.label for f in ctx.facts)

    def test_compare_context_flags_overlap_with_maps(
        self, context: ApplicationContext, file_with_map, tmp_path: Path
    ) -> None:
        file, vehicle, offset = file_with_map
        candidates = context.analysis.detect_maps(file.id)
        target = next(c for c in candidates if c.offset == offset)
        context.analysis.set_candidate_status(
            target.id, MapCandidateStatus.VALIDATED, name="Injection"
        )
        data = bytearray(context.ecu_files.read_content(file.id))
        data[offset + 4] ^= 0xFF  # change a byte inside the validated map
        modified = tmp_path / "mod.bin"
        modified.write_bytes(bytes(data))
        other = context.ecu_files.import_file(modified, vehicle_id=vehicle.id)

        ctx = context.assistant._builder.compare_context(file.id, other.id)
        assert any("Injection" in note for note in ctx.notes)


class TestOfflineAnalyst:
    def test_always_available(self) -> None:
        assert OfflineAnalyst().is_available()

    def test_summary_restates_facts_without_inventing(self) -> None:
        analyst = OfflineAnalyst()
        ctx = AiContext(
            subject="Fichier test",
            facts=(ContextFact("Taille", "512.0 Kio"),),
        )
        answer = analyst.generate(AiRequest(AiTask.SUMMARIZE, ctx))
        assert not answer.ai_generated
        assert "512.0 Kio" in answer.text
        assert answer.facts_used == ctx.facts

    def test_deterministic(self, context: ApplicationContext, file_with_map) -> None:
        file, _v, _o = file_with_map
        first = context.assistant.summarize_file(file.id, provider="offline")
        second = context.assistant.summarize_file(file.id, provider="offline")
        assert first.text == second.text


class TestProviderDispatch:
    def test_default_is_offline_and_available_list(self, context: ApplicationContext) -> None:
        assert context.assistant.default_provider() == "offline"
        names = [name for name, _label in context.assistant.available_providers()]
        assert names == ["offline"]  # no API key configured

    def test_unknown_or_unavailable_provider_falls_back_to_offline(
        self, context: ApplicationContext, file_with_map
    ) -> None:
        file, _v, _o = file_with_map
        answer = context.assistant.summarize_file(file.id, provider="anthropic")
        assert answer.provider == "offline"  # anthropic not configured


class TestAnthropicProvider:
    def test_unavailable_without_key(self, monkeypatch) -> None:
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        provider = AnthropicProvider(model="claude-sonnet-5", api_key="")
        assert not provider.is_available()
        with pytest.raises(ProviderUnavailableError):
            provider.generate(AiRequest(AiTask.SUMMARIZE, AiContext(subject="x")))

    def test_generate_with_faked_sdk(self, monkeypatch) -> None:
        captured: dict = {}

        class _Block:
            type = "text"
            text = "Synthèse rédigée par le modèle."

        class _Message:
            content = [_Block()]

        class _Messages:
            def create(self, **kwargs):
                captured.update(kwargs)
                return _Message()

        class _Client:
            def __init__(self, api_key):
                captured["api_key"] = api_key
                self.messages = _Messages()

        fake = types.ModuleType("anthropic")
        fake.Anthropic = _Client
        monkeypatch.setitem(__import__("sys").modules, "anthropic", fake)

        provider = AnthropicProvider(model="claude-sonnet-5", api_key="secret-key")
        assert provider.is_available()

        ctx = AiContext(subject="Fichier X", facts=(ContextFact("Taille", "1 Mio"),))
        answer = provider.generate(AiRequest(AiTask.SUMMARIZE, ctx))

        assert answer.ai_generated
        assert answer.provider == "anthropic"
        assert answer.text == "Synthèse rédigée par le modèle."
        # The honesty contract must be sent as the system prompt, and the
        # factual context must be in the user message.
        assert "n'inventes JAMAIS" in captured["system"]
        assert "Taille : 1 Mio" in captured["messages"][0]["content"]
        assert captured["api_key"] == "secret-key"

    def test_sdk_error_becomes_clean_unavailable(self, monkeypatch) -> None:
        class _Messages:
            def create(self, **kwargs):
                raise RuntimeError("boom")

        class _Client:
            def __init__(self, api_key):
                self.messages = _Messages()

        fake = types.ModuleType("anthropic")
        fake.Anthropic = _Client
        monkeypatch.setitem(__import__("sys").modules, "anthropic", fake)

        provider = AnthropicProvider(model="claude-sonnet-5", api_key="k")
        with pytest.raises(ProviderUnavailableError, match="échoué"):
            provider.generate(AiRequest(AiTask.SUMMARIZE, AiContext(subject="x")))
