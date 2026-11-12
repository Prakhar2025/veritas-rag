# INTERVIEW-PREP

Owner facing notes for defending Veritas RAG in interviews. Not part of the
engineering contract; keep out of the README.

## The 30 second pitch

Veritas RAG answers questions over multiple PDFs where every sentence is verified
against the chunk it cites before the user sees it. Unsupported sentences are
stripped by deterministic code, insufficient evidence is refused explicitly,
conversations persist across restarts, and document level access rules are
enforced at retrieval time. It runs Llama 3.3 70B on AWS Bedrock through a
LangGraph pipeline, with Nova Micro grading and judging, hybrid BM25 plus dense
retrieval fused with reciprocal rank, and a local cross encoder reranking.

## Decisions an interviewer will probe

1. Why a graph and not a chain: the flow branches. Grade can short circuit to
   refusal, attribution can refuse, condense depends on persisted history. A
   state graph makes those branches explicit and testable.
2. Why hybrid retrieval: dense catches paraphrase, sparse catches identifiers and
   exact figures. RRF needs no score calibration between the two. The published
   baseline (dense only) is right beside the headline number, honestly.
3. Why contextual chunking: chunk text is ambiguous in isolation ("the margin
   improved by 340 basis points"); an LLM written blurb anchored to the document
   fixes embedding quality. Anthropic published this pattern with large failure
   rate reductions.
4. Why Nova Micro grades while Llama 70B writes: grading is high volume and low
   complexity; generation is the reverse. Routing is a cost and latency decision,
   not a quality compromise where it matters.
5. Why sentence level attribution: chunk level grounding hides unsupported
   clauses inside good paragraphs. Sentence level is where hallucination lives.
   The numeric guard is deterministic: a sentence citing numbers absent from its
   source is dropped regardless of the judge's opinion. Models propose, code
   decides.
6. Why refuse: an unanswerable question answered confidently is the worst failure
   mode. Refusal accuracy is a gated metric with its own evaluation category.
7. Why pre filter access control: post filtering leaks document existence through
   ranking and counts. Filtering happens before scoring, and the wrong domain
   denial fails closed.

## Numbers to quote (from evals/report.md, refresh before use)

- Recall@5 on the golden set: 0.818, dense only baseline 0.833
- Refusal accuracy 8/8, permission accuracy 4/4
- Attribution benchmark precision 1.000
- Cost per answer around 0.001 USD on the default routing
- Latency around 3 s per turn end to end, first token under 1 s from cache hits

## Stories from what broke (told as engineering lessons)

1. The Bedrock API reported a model as ACTIVE while the documented model card
   recorded its end of life. Lesson: documentation beats API fields for lifecycle
   planning; identifiers live in config so a retirement is one line.
2. Llama 3.3 rejected direct model ids; it only runs through its inference
   profile. The config first design made that a one line fix.
3. The numeric guard originally counted digits inside citation markers as claim
   numbers and rejected honest sentences. Tests caught it before shipping.
4. A restricted role could still answer from wrong domain evidence because
   retrieval was non empty. The rule is now fail closed: if the strongest
   unrestricted evidence lies outside the role's visible set, deny.

## Likely Humanli questions

- How would this handle 10,000 documents? Batch contextualization off the
  request path, per document idempotent ingestion, index version cache
  invalidation, and the interface accepts a hosted reranker without code change.
- How is this different from Amazon Knowledge Bases? Knowledge Bases gives
  managed retrieval; the grounding contract here (sentence verification, refusal
  taxonomy, attribution benchmark) is the differentiating layer on top of any
  retriever.
- What breaks at scale first? CPU rerank latency; it is a config switch to a
  hosted reranker.
- How do you know the verifier itself is not hallucinating? The attribution
  micro benchmark measures judge precision and recall against labeled pairs, and
  the numeric guard handles the class of errors where numbers disagree.
