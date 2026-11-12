# 06. Generation and Grounding

## Grounding contract

An answer is a list of sentences. Each sentence is either (a) supported by the chunk it cites, or (b) removed before the user sees it. If no sentence survives, the user receives the refusal message. This contract is enforced by code, not by prompt instructions alone.

## Evidence assembly

The generator receives numbered evidence blocks built by retrieval:

```
[1] Annual Report FY2025, page 41, section 5.2 Operating Margin
    <parent chunk text>
[2] Regulatory Circular, page 7, section 3.1 Definitions
    <parent chunk text>
```

The system prompt states the rules: answer only from the evidence blocks, cite the block number after each factual sentence, and state when the evidence is insufficient. Prompts live in a dedicated module with versions, so eval runs record which prompt produced which result.

## Citation format

Inline citations use `[1]` style markers tied to evidence blocks. The response carries a structured sources list:

```json
{
  "citations": [
    {"n": 1, "doc": "FY2025 Annual Report", "pages": "41", "section": "5.2 Operating Margin"}
  ]
}
```

Page ranges resolve to the small chunk that was retrieved, so the reference is precise even though the generator read the parent.

## Sentence level attribution

This is the core honesty mechanism, executed after generation and before delivery:

1. Split the draft into sentences.
2. For each sentence carrying factual claims, run a verification call (cheap model) with the sentence and the chunk it cites: supported, contradicted, or unverifiable.
3. Remove unsupported and contradicted sentences; keep supported ones in order.
4. Recompute the citation list from surviving sentences.

Deterministic guards wrap the model judge: a sentence with a number that appears in no cited chunk is dropped regardless of the judge's opinion, and a sentence citing a block number that does not exist is dropped. If fewer than one supported sentence remains, the pipeline refuses.

## Refusal policy

| Condition | Response |
|---|---|
| Retrieval empty or all evidence graded irrelevant | "The uploaded documents do not contain information about this." |
| All draft sentences failed attribution | Same refusal, with a note that partial evidence was found but insufficient |
| Question blocked by role | "This question requires access to documents outside your role." |

Refusals are recorded in traces with the cause, so the evaluation suite can tell honest refusal from missing retrieval.

## Conversational memory

Sessions persist in SQLite through the graph checkpointer. Memory has two layers:

- **Recent turns window**: the last six messages are passed to the condense node.
- **Standalone rewrite**: the condense node rewrites the user question into a self contained query using that window, for example "summarize that for a CFO" becomes "summarize the FY2025 operating margin discussion for a CFO audience". The rewritten query drives retrieval; the original question stays in history verbatim.

Memory is per session, deleted on session removal, and never mixes evidence across sessions.

## Prompt injection stance

Document text is data, never instructions. The pipeline never executes, follows or interpolates document content into control prompts; quoted content appears only inside evidence blocks. The grade and attribution prompts are built from fixed templates with content in a designated data slot, and the verifier is instructed to treat anything inside the data slot as text to evaluate, not commands to follow. Where a judgment is safety critical, code decides (the number guard above), keeping with the project principle: models propose, code decides.
