# 01. Problem Statement

## Background

Organizations accumulate knowledge in documents: annual reports, financial statements, technical manuals, business policies and operational procedures. The information exists, but answering a specific question means a person opens multiple PDFs, scans dozens of pages, and assembles the answer by hand. At scale this is slow, inconsistent and error prone.

Naive chatbots do not fix this. A general purpose LLM asked about a private corpus does three predictable things: it answers from pretraining instead of the documents, it presents invented details with the same confidence as real ones, and it forgets the conversation two turns later. None of these failures are acceptable where the answer drives a decision.

## The problem

Build a retrieval augmented generation system that lets a user upload multiple PDF documents and ask questions in natural language, and that holds itself to an evidence standard:

1. Answers are grounded in the uploaded documents, never in model memory.
2. Every factual sentence carries a citation, and each citation resolves to a specific document and page range the user can open and check.
3. When the documents do not contain the answer, the system refuses explicitly instead of guessing.
4. Conversational context survives across turns, so follow up questions like "summarize that for a CFO" resolve without restating the question.
5. Document level access rules are enforced at retrieval time, so a restricted role cannot pull evidence from documents it is not allowed to see.

## Assignment requirements mapping

This project implements the Generative AI assignment: an intelligent multi document RAG system with chat history and conversational memory. The table maps each stated requirement to the place it is addressed.

| Assignment requirement | Where it is delivered |
|---|---|
| Upload multiple PDF documents | Ingestion service, data design (doc 04) |
| Retrieve relevant information across documents | Hybrid retrieval with fusion and reranking (doc 05) |
| Generate accurate, context aware responses with an LLM | Generation pipeline with model routing (docs 03, 06) |
| Answers grounded in the uploaded documents | Sentence level attribution gate (doc 06) |
| Relevant source references | Citation format with document, page range and section (doc 06) |
| Handle unavailable information gracefully | Refusal policy with explicit templates (doc 06) |
| Conversational context for follow up questions | Persistent session memory and query rewriting (docs 03, 06) |
| Test retrieval, question answering, references, history and memory | Golden set evaluation with refusal and permission cases (doc 09) |

## Success definition

The system is considered correct when, on the golden evaluation set:

- Every remaining sentence in every answer is supported by the chunk it cites.
- Retrieval finds the correct document and page for answerable questions at the recall target set in doc 09.
- Out of scope questions are refused, not answered.
- Restricted roles receive no evidence from documents outside their access list, and permission blocked questions return an explicit denial.
- Follow up questions resolve references from conversation history without the user repeating themselves.

## Guiding principle

Models propose, code decides. The LLM drafts, ranks and judges, but the decision to show a sentence, to attach a citation, or to refuse is made by deterministic code checking that sentence against evidence. Nothing unverifiable reaches the user.
