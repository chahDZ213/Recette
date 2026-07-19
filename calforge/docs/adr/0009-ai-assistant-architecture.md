# ADR-0009 — AI assistant: provider abstraction and honesty

Date: 2026-07-19 · Status: accepted

## Context

The product promises AI assistance, but calibration is safety-relevant and the
founding rule (ADR-0004) forbids presenting guesses as facts. The assistant
must be genuinely useful, never fabricate, work offline by default, remain
fully testable without a network, and not lock the user into one AI vendor.

## Decision

1. **Provider abstraction** (``calforge.ai.base.AiProvider``): the assistant
   dispatches ``AiRequest`` to an interchangeable backend. Two ship:
   - **OfflineAnalyst** — deterministic, always available, no network, no key.
     Not a language model: it composes the factual context into a readable
     briefing. Honest by construction, and the reason the feature works with
     zero configuration and is testable offline.
   - **AnthropicProvider** — optional Claude backend via the official SDK,
     active only when an API key is present. Absent key or SDK,
     ``is_available()`` is False and the app falls back to offline; any
     network/auth error surfaces as a clean message, never a crash.
2. **Factual context boundary** (``calforge.ai.context.ContextBuilder``): the
   single place product data becomes AI input. Only measured **facts** and
   already-scored **hypotheses** cross it — providers never touch a service or
   a raw file. A validated map is a fact; a detected-but-unvalidated map is a
   hypothesis carrying its confidence and rationale.
3. **Honesty enforced at the provider**: the Claude system prompt hard-codes
   the contract (reason only from supplied context; never invent
   offsets/values; separate facts from hypotheses; never present a hypothesis
   as certainty; answer in French; human validates). Every ``AssistantAnswer``
   records the facts and hypotheses it used, is labelled generated, and
   carries a standing disclaimer.
4. **Human validation path**: answers are ephemeral by default and can be
   saved to the vehicle timeline as a note — reusing the existing
   documentation/validation flow, so v0.5 needs no migration.
5. **No secrets on disk by default**: the API key is read from config *or* the
   ``ANTHROPIC_API_KEY`` environment variable; the config key stays empty
   unless the user deliberately sets it.

## Consequences

- The assistant is useful and safe out of the box, better with a key.
- New backends (local LLM, other vendors) implement one protocol; the context
  boundary and honesty rules are inherited unchanged.
- Because facts vs hypotheses were modelled from v0.1, the assistant reasons
  over trustworthy structured data instead of re-parsing binaries.
