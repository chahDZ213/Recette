"""Assistant service — orchestrates context building and provider dispatch.

The UI calls high-level operations (summarize a file, explain a candidate,
compare two files, ask a free question about a subject). The service builds the
factual context, routes it to the selected provider, and returns an
``AssistantAnswer``. Providers are thread-safe to construct and call, so the UI
runs every operation on a worker thread.
"""

from __future__ import annotations

import logging

from calforge.ai.base import AiProvider, AiRequest, AiTask, AssistantAnswer
from calforge.ai.context import ContextBuilder

logger = logging.getLogger(__name__)


class AssistantService:
    def __init__(
        self,
        builder: ContextBuilder,
        providers: list[AiProvider],
        default_provider: str,
    ) -> None:
        self._builder = builder
        self._providers = {p.name: p for p in providers}
        self._default = default_provider if default_provider in self._providers else "offline"

    # --------------------------------------------------------- providers --

    def available_providers(self) -> list[tuple[str, str]]:
        """(name, label) of every currently usable provider, default first."""
        usable = [(p.name, p.label) for p in self._providers.values() if p.is_available()]
        usable.sort(key=lambda item: (item[0] != self._default, item[1]))
        return usable

    def default_provider(self) -> str:
        if self._providers.get(self._default, None) and self._providers[self._default].is_available():
            return self._default
        available = self.available_providers()
        return available[0][0] if available else "offline"

    def _provider(self, name: str | None) -> AiProvider:
        chosen = name or self.default_provider()
        provider = self._providers.get(chosen)
        if provider is None or not provider.is_available():
            provider = self._providers["offline"]
        return provider

    # -------------------------------------------------------- operations --

    def summarize_file(self, file_id: int, *, provider: str | None = None) -> AssistantAnswer:
        context = self._builder.file_context(file_id)
        return self._provider(provider).generate(AiRequest(AiTask.SUMMARIZE, context))

    def explain_candidate(
        self, candidate_id: int, *, provider: str | None = None
    ) -> AssistantAnswer:
        context = self._builder.candidate_context(candidate_id)
        return self._provider(provider).generate(AiRequest(AiTask.EXPLAIN, context))

    def compare_files(
        self, file_id_a: int, file_id_b: int, *, provider: str | None = None
    ) -> AssistantAnswer:
        context = self._builder.compare_context(file_id_a, file_id_b)
        return self._provider(provider).generate(AiRequest(AiTask.COMPARE, context))

    def summarize_vehicle(
        self, vehicle_id: int, *, provider: str | None = None
    ) -> AssistantAnswer:
        context = self._builder.vehicle_context(vehicle_id)
        return self._provider(provider).generate(AiRequest(AiTask.SUMMARIZE, context))

    def propose_for_file(self, file_id: int, *, provider: str | None = None) -> AssistantAnswer:
        context = self._builder.file_context(file_id)
        return self._provider(provider).generate(AiRequest(AiTask.PROPOSE, context))

    def ask_about_file(
        self, file_id: int, question: str, *, provider: str | None = None
    ) -> AssistantAnswer:
        context = self._builder.file_context(file_id)
        return self._provider(provider).generate(AiRequest(AiTask.ASK, context, question))

    def ask_about_vehicle(
        self, vehicle_id: int, question: str, *, provider: str | None = None
    ) -> AssistantAnswer:
        context = self._builder.vehicle_context(vehicle_id)
        return self._provider(provider).generate(AiRequest(AiTask.ASK, context, question))
