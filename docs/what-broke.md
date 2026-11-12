# What Broke

Real time failure log per the build protocol in CLAUDE.md. Every failure that costs time gets a row: what broke, the root cause, the fix. No silent edits, no polished after the fact stories. Entry count is part of the record.

| # | Date | What broke | Root cause | Fix |
|---|---|---|---|---|
| 1 | 2026-11-12 | Documentation suite landed as 8 fragmented micro commits; owner rejected the history as spam | Treated "one commit per concern" as "one commit per file pair" instead of one unit of completed work | History rewritten to 2 clean commits (scaffold + docs suite) and force pushed; granularity rule written into CLAUDE.md |
| 2 | 2026-11-12 | Default model initially proposed for downgrade after owner flagged the Llama 3.3 70B end of life | Trusted the Bedrock API `modelLifecycle.status` field (ACTIVE) over the AWS documented model card (EOL 2027-03-30); then over corrected to a smaller model against answer quality | Owner decision recorded: keep 70B as default for the assignment window; lifecycle caveat and discrepancy documented in docs/11; documented model cards take precedence over API lifecycle fields |
| 3 | 2026-11-13 | First real generation call failed: Llama 3.3 70B rejects direct model ids on this account | The model is only invocable through its inference profile; the configuration default carried the raw model id | Generator default switched to us.meta.llama3-3-70b-instruct-v1:0 in config and .env.example; the config first guard worked as designed, one line change |
| 4 | 2026-11-13 | Numeric consistency guard rejected honest sentences | The guard counted digits inside citation markers like [1] as claim numbers | Citation markers are stripped before the numeric check; guard unit tests updated to the corrected semantics |
