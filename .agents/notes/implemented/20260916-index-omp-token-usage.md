## Problem

Rinq did not report local oh-my-pi (`omp`) token usage. Its default source discovery covered Codex, TraeX, Claude Code, and ZCode, but not OMP's `~/.omp/agent/sessions` tree. OMP also uses its own JSONL shape: each assistant `message` contains `provider`, `model`, and `usage` fields named `input`, `output`, `cacheRead`, `cacheWrite`, and optionally `reasoningTokens`.

OMP main sessions and nested subagent transcripts share the same sessions tree. Forked sessions can copy prior message entries, so file path plus byte offset is not sufficient to prevent double counting across files.

## Decision

Add an `omp` usage adapter rooted at `PI_CODING_AGENT_DIR/sessions`, falling back to `~/.omp/agent/sessions`. Parse only entries with `type=message`, `message.role=assistant`, a non-empty message ID, and a structured usage object. Normalize OMP's token buckets into the existing Rinq usage contract and label the app `OMP`.

Add a nullable `event_key` column to the local usage index through an additive migration. OMP rows use the stable message ID plus timestamp as this key. Aggregation selects the first row for each non-null key, so a message copied into a fork remains stored for file-level incremental bookkeeping but contributes to totals only once. Existing adapters keep a null key and retain their current behavior.

## Alternatives considered

- Configure OMP manually through `usage.extraSources`: rejected because OMP is a supported local CLI with a stable default path and should work without user configuration.
- Reuse the Codex `token_count` parser: rejected because OMP persists assistant messages with different field names and semantics.
- Count every OMP JSONL row by path and byte offset: rejected because forked transcripts can contain copied provider requests and inflate totals.
- Store message content to improve classification: rejected because token counters, provider, model, timestamp, and stable ID are sufficient; Rinq's privacy boundary excludes conversation content.

## Consequences

- Rinq discovers default-profile OMP main and nested subagent sessions automatically.
- `PI_CODING_AGENT_DIR` is supported for a custom OMP agent directory; other unusual locations can still use `usage.extraSources` with adapter `omp`.
- Existing `usage.sqlite3` databases are upgraded in place without deleting prior rows.
- The source list and app breakdown display OMP explicitly.
- OMP prompt text, assistant content, tool arguments, and tool results are not stored in Rinq's index.
