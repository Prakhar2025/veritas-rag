# 04. Data Design

## Corpus

The demo corpus is a set of public PDF reports chosen for variety of structure and vocabulary, because retrieval quality claims mean nothing on homogeneous documents.

| Slot | Document type | Why it is included |
|---|---|---|
| 1 | Annual report of a listed Indian company | Long, sectioned, tables with financial figures |
| 2 | Financial statements section | Numbers, units, fiscal year phrasing |
| 3 | Regulatory or policy circular | Formal definitions, numbered clauses, exact terms |
| 4 | Technical whitepaper | Dense terminology, diagrams described in text |
| 5 | Operations manual | Step lists, procedures, cross references |
| 6 | Business or industry report | Narrative prose, market vocabulary |

Documents are stored under `data/corpus/` and committed so the repository is runnable on clone. Each file stays well under 20 MB so the repository clone stays fast. A fetch script records the source URL, license and retrieval date for every document.

## Ingestion stages

1. **Extract.** Parse each PDF with a layout aware extractor that preserves page numbers and heading structure, producing page mapped blocks.
2. **Chunk.** Build section aware chunks from heading boundaries. Small chunks target roughly 300 tokens with 15 percent overlap; parent chunks cover the enclosing section up to about 1200 tokens. Small chunks are what gets embedded; parents are what the generator reads (small to big retrieval, doc 05).
3. **Contextualize.** One cheap model call per chunk writes a one or two sentence blurb describing what this chunk contains and where it sits in the document. The blurb is prepended at embedding time, which anchors ambiguous chunks ("the margin improved by 340 basis points") to their document context. This follows the contextual retrieval approach published by Anthropic, which reports materially lower retrieval failure rates from this step.
4. **Embed and index.** Small chunk plus blurb is embedded and written to the vector index; the same text is tokenized into the BM25 index; metadata goes to a JSONL sidecar.
5. **Idempotency check.** The document SHA-256 is computed before any work. If the hash already exists in the index manifest, ingestion skips the document and reports it as unchanged. Re ingesting after edits creates a new version and retires the old chunks.

## Record schemas

**Document record**

```json
{
  "doc_id": "sha256 prefix",
  "sha256": "full hash",
  "title": "FY2025 Annual Report",
  "source_url": "https://...",
  "pages": 214,
  "departments": ["finance", "general"],
  "ingested_at": "2026-11-14T09:00:00Z"
}
```

**Chunk record**

```json
{
  "chunk_id": "doc_id:seq",
  "doc_id": "sha256 prefix",
  "page_start": 41,
  "page_end": 41,
  "section_path": "5. Financial Review / 5.2 Operating Margin",
  "text": "chunk body text",
  "context_blurb": "what this chunk contains and where it sits",
  "parent_id": "doc_id:parent_seq",
  "departments": ["finance"]
}
```

**Session record** (SQLite): session id, created at, message rows with role, content, citations and trace reference.

**Cache record**: normalized question embedding, question text, assembled answer, source ids, created at, index version.

## Storage layout

```
data/
  corpus/            committed PDFs + SOURCES.md
  indexes/
    manifest.json    documents, hashes, versions, config fingerprint
    faiss/           vector index and id map
    bm25/            tokenized corpus artifact
    meta/chunks.jsonl  chunk records, append only
    parents.jsonl      parent chunk texts
  cache/
  traces/            request traces, one JSONL per day
```

The manifest carries an index version that increments on every ingestion that changes content. Cache entries store the version that produced them; a new version invalidates the cache in one comparison. This is the discipline that keeps re ingestion safe.
