# AI data processing and privacy

EDAgent computes every statistic, table and chart locally in the backend. An external language model is **optional** and is only used for two things: turning a question into a structured analysis plan, and phrasing an explanation of an already-computed result.

## What is sent to the AI provider (only when `LLM_PROVIDER` and `LLM_API_KEY` are set)

| Request | Contents |
| --- | --- |
| Planning | The user's question; the dataset name; for each column its name, type, role, missing %, distinct count, a few summary statistics and a handful of sanitised sample values (capped by `LLM_MAX_CONTEXT_CHARS`); the catalogue of approved analyses; the last few turns of the conversation (questions and the plans that were run). |
| Explanation | The user's question and the computed result facts (metrics and the first rows of result tables, truncated). |

Raw dataset files are never uploaded. Whole tables are never sent, only the truncated excerpts above. Column names and sample values are sanitised because they are untrusted input: control characters, role markers (such as `system:`), code fences and angle brackets are neutralised, length is capped, and everything is placed in a block the prompt labels as data, not instructions.

If you cannot share even this much with a third party, leave `LLM_PROVIDER=mock` (the default). Upload, profiling, the analysis workspace, charts, exports and reports all work without AI; only plain-English chat is unavailable and says so honestly.

## What the AI cannot do

- It never executes code. It can only choose one of the approved operations and fill in a validated plan; unknown keys are dropped and invalid plans are rejected with a repair attempt, then a clarification or refusal.
- It never supplies numbers. Numbers in its explanation are checked against the computed result; if any are not found, a deterministic template explanation is used instead and the UI labels which text is AI-written.
- Instructions hidden in column names, cell values or questions are treated as data.
- API keys are read from the server environment and are never returned by any endpoint or included in frontend code.

## Retention

Prompts and responses are not stored beyond the chat turn record (question, plan, result, explanation) that belongs to the user's session and is deleted with the session or dataset. The provider's own retention policy applies to anything sent to it; review it before enabling AI on sensitive data.
