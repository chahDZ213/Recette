"""Core AI types: factual context, requests, answers, provider protocol."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol, runtime_checkable


class AiTask(StrEnum):
    SUMMARIZE = "summarize"
    EXPLAIN = "explain"
    COMPARE = "compare"
    PROPOSE = "propose"
    ASK = "ask"


@dataclass(frozen=True, slots=True)
class ContextFact:
    """A proven statement about the subject (measured, never guessed)."""

    label: str
    value: str


@dataclass(frozen=True, slots=True)
class ContextHypothesis:
    """A scored guess with rationale — carried through verbatim from the
    services so the assistant can reason about it without re-deriving it."""

    statement: str
    confidence: float
    rationale: str


@dataclass(frozen=True, slots=True)
class AiContext:
    """The factual briefing given to a provider. This is the *only* thing a
    provider may reason from."""

    subject: str
    facts: tuple[ContextFact, ...] = ()
    hypotheses: tuple[ContextHypothesis, ...] = ()
    notes: tuple[str, ...] = ()

    def to_prompt(self) -> str:
        """Render the context as a plain-text block for an LLM prompt."""
        lines = [f"Sujet : {self.subject}", "", "FAITS AVÉRÉS (mesurés) :"]
        if self.facts:
            lines.extend(f"- {fact.label} : {fact.value}" for fact in self.facts)
        else:
            lines.append("- (aucun)")
        lines.append("")
        lines.append("HYPOTHÈSES (non confirmées, avec niveau de confiance) :")
        if self.hypotheses:
            lines.extend(
                f"- {h.statement} — confiance {h.confidence:.0%} — {h.rationale}"
                for h in self.hypotheses
            )
        else:
            lines.append("- (aucune)")
        if self.notes:
            lines.append("")
            lines.append("NOTES :")
            lines.extend(f"- {note}" for note in self.notes)
        return "\n".join(lines)


@dataclass(frozen=True, slots=True)
class AiRequest:
    task: AiTask
    context: AiContext
    question: str = ""


@dataclass(frozen=True, slots=True)
class AssistantAnswer:
    """An assistant reply. Always presented as generated, always separable
    into the facts it used and its own interpretation."""

    provider: str
    task: AiTask
    text: str
    facts_used: tuple[ContextFact, ...] = ()
    hypotheses: tuple[ContextHypothesis, ...] = ()
    confidence: float | None = None
    ai_generated: bool = False
    extra_notes: tuple[str, ...] = field(default_factory=tuple)

    def disclaimer(self) -> str:
        base = (
            "Réponse générée automatiquement à partir des données du projet. "
            "Les hypothèses ne sont pas des certitudes : vérifiez toujours "
            "avant toute modification."
        )
        if self.ai_generated:
            return (
                f"Généré par l'assistant IA « {self.provider} ». " + base
            )
        return base


class ProviderUnavailableError(RuntimeError):
    pass


@runtime_checkable
class AiProvider(Protocol):
    """An assistant backend. Implementations must honour ADR-0004/0009:
    reason only from ``request.context``; never fabricate offsets or values;
    always separate facts from interpretation."""

    name: str
    label: str

    def is_available(self) -> bool:
        """Whether this provider can currently be used (key present, etc.)."""
        ...

    def generate(self, request: AiRequest) -> AssistantAnswer:
        ...
