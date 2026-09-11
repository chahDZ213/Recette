"""AI assistant: provider abstraction, factual context, honest answers.

Design rules (ADR-0009), inheriting the founding facts-vs-hypotheses contract
(ADR-0004):

- Providers never see raw files; they receive a ``AiContext`` assembled from
  the services — proven facts and clearly-marked scored hypotheses only.
- Every ``AssistantAnswer`` separates facts from interpretation, carries a
  confidence and a disclaimer, and is presented as generated content the user
  must validate. Nothing the assistant says is ever treated as truth by the
  rest of the application.
- The offline provider is always available (no network, no key, deterministic,
  fully testable). The Claude provider is optional and activates only when a
  key is configured.
"""
