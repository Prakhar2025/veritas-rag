# 08. Security and Privacy

## Access control

The system implements document level access control with a role filter, following the pattern used in enterprise retrieval systems: access metadata travels with the chunk, and enforcement happens inside retrieval.

- Every document carries `departments` tags at ingestion time.
- Every request carries a `role` whose allowlist of departments is resolved from configuration.
- Candidate filtering removes out of scope chunks **before** dense and sparse scoring. Post filtering is rejected by design because it leaks document existence through ranking and count side channels.
- Permission blocked questions return an explicit denial (doc 06) and are distinguishable from empty retrieval in traces.

The default deployment ships an `analyst` role with access to all departments (documents are public) and evaluation uses restricted roles to prove the filter works (doc 09). This is deliberately a working model of enterprise RBAC, not a full multi tenant deployment; the scale out path is in the roadmap.

## Audit trail

Every request appends one JSONL trace record: timestamp, session, role, question length, stage latencies, token usage, retrieval identifiers, grade and attribution verdicts, cache hit flag. Traces contain no document bodies and no model outputs beyond verdicts, so they are safe to keep and small to store. The evaluation suite reads traces to verify refusal and permission behavior, and the API exposes a tail view for reviewers (doc 07).

## Prompt injection stance

Uploaded documents are untrusted input. The pipeline treats them as data end to end:

- Document content never enters control prompts; it appears only inside designated evidence slots.
- Graders and verifiers are instructed to evaluate slot content as text, never to follow instructions found inside it.
- No tool, shell, template or URL fetch ever executes on document derived strings.
- Safety critical judgments are deterministic: the numeric consistency guard in doc 06 drops sentences citing numbers that exist in no cited chunk, regardless of model opinion.

## Secrets and configuration

- All credentials live in environment variables loaded from `.env`, which is gitignored; `.env.example` documents every variable with no real values.
- Model identifiers, thresholds and provider selection are configuration, not code.
- The repository contains no credentials at any point in its history.

## Data handling

- The corpus consists of public documents only.
- Sessions store questions, answers and citations; deleting a session (doc 07) removes its history.
- No third party telemetry; the only outbound calls are the configured model provider.
- Logs are local files under `data/traces/`, gitignored.
