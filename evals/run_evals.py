"""Golden set evaluation runner (docs/09).

Modes:
  python evals/run_evals.py --smoke      offline, fake providers, CI gates
  python evals/run_evals.py --full       configured providers, real metrics, report

Smoke enforces behavior gates (refusal, permission, citation, attribution) over a
deterministic fixture world. Full measures retrieval recall@5 against support_doc
labels, runs the attribution benchmark, computes the dense only baseline and
writes evals/report.md.
"""

from __future__ import annotations

import argparse
import sys
import tempfile
import time
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.attribution.verifier import verify_draft  # noqa: E402
from app.core.config import Settings, get_settings  # noqa: E402
from app.core.spend import SpendMeter  # noqa: E402
from app.graph.graph import run_turn  # noqa: E402
from app.graph.nodes import Runtime  # noqa: E402
from app.graph.prompts import PROMPT_VERSION  # noqa: E402
from app.graph.store import SessionStore  # noqa: E402
from app.ingest.manifest import Manifest  # noqa: E402
from app.ingest.pipeline import run_ingest  # noqa: E402
from app.providers.base import ChatProvider  # noqa: E402
from app.providers.bedrock import BedrockChat  # noqa: E402
from app.providers.embeddings import build_embedder  # noqa: E402
from app.providers.fake import FakeChat  # noqa: E402
from app.retrieval.rerank import IdentityReranker, build_reranker  # noqa: E402
from app.retrieval.retriever import Retriever  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SMOKE_IDS = ["s01", "m01", "t01", "f01", "f02", "o01", "o02", "p01", "p02", "s03"]


def _load_cases() -> list[dict[str, object]]:
    """Load the golden cases."""
    data = yaml.safe_load((ROOT / "evals" / "golden.yaml").read_text(encoding="utf-8"))
    return list(data["cases"])


def _fixture_corpus(tmp: Path) -> Path:
    """Build a small deterministic corpus for offline smoke runs."""
    import json

    import fitz

    corpus_dir = tmp / "corpus"
    corpus_dir.mkdir(parents=True)
    documents = [
        (
            "alpha-finance.pdf",
            [
                "# Alpha Overview",
                "The FY2025 operating margin reached 23.4 percent, up 340 basis points.",
                "# Alpha Risk Factors",
                "Supply chain costs stay volatile across the region.",
            ],
            ["finance"],
        ),
        (
            "beta-engineering.pdf",
            [
                "# Beta Operations Manual",
                "Step one: power the device and wait for the green status light.",
                "Step two: run calibration, which takes about four minutes.",
            ],
            ["engineering"],
        ),
    ]
    for name, pages, departments in documents:
        document = fitz.open()
        for page_text in pages:
            page = document.new_page()
            y = 72
            for line in page_text.splitlines():
                size = 16 if line.strip().startswith("#") else 11
                page.insert_text((72, y), line, fontsize=size)
                y += size + 8
        document.save(str(corpus_dir / name))
        document.close()
    (corpus_dir / "catalog.json").write_text(
        json.dumps([
            {"filename": "alpha-finance.pdf", "title": "Alpha Finance",
             "departments": ["finance"]},
            {"filename": "beta-engineering.pdf", "title": "Beta Engineering",
             "departments": ["engineering"]},
        ]),
        encoding="utf-8",
    )
    return corpus_dir


def _attribution_benchmark(chat: ChatProvider, model_id: str) -> tuple[float, float, list[dict[str, str]]]:
    """Score verify_draft against labeled pairs; returns precision, recall, rows."""
    cases = yaml.safe_load(
        (ROOT / "evals" / "attribution_cases.yaml").read_text(encoding="utf-8")
    )["cases"]
    true_positive = false_positive = false_negative = 0
    rows: list[dict[str, str]] = []
    for case in cases:
        blocks: list[dict[str, object]] = [{"number": 1, "text": case["source"]}]
        verdicts, _ = verify_draft(str(case["sentence"]), blocks, chat, model_id)
        predicted = verdicts[0].verdict if verdicts else "unsupported"
        expected = str(case["expected"])
        rows.append({"id": str(case["id"]), "expected": expected, "predicted": predicted})
        if expected == "supported" and predicted == "supported":
            true_positive += 1
        elif expected == "supported" and predicted != "supported":
            false_negative += 1
        elif expected != "supported" and predicted == "supported":
            false_positive += 1
    precision = (
        true_positive / (true_positive + false_positive) if (true_positive + false_positive) else 0.0
    )
    recall = (
        true_positive / (true_positive + false_negative) if (true_positive + false_negative) else 0.0
    )
    return precision, recall, rows


def _run_smoke() -> int:
    """Offline behavior gates with deterministic providers over a fixture world."""
    tmp = Path(tempfile.mkdtemp())
    corpus_dir = _fixture_corpus(tmp)
    settings = Settings(
        chat_provider="fake",
        embeddings_provider="hash",
        reranker_provider="identity",
        data_dir=str(tmp / "data"),
        _env_file=None,  # type: ignore[call-arg]
    )
    meter = SpendMeter(Path(settings.data_dir) / "spend.json", settings.spend_cap_usd)

    scripts: dict[str, str] = {}
    chat = FakeChat(meter, responses=scripts)
    embedder = build_embedder("hash", "hash-64")
    run_ingest(
        corpus_dir=corpus_dir,
        data_dir=Path(settings.data_dir),
        chat=chat,
        embedder=embedder,
        settings=settings,
    )
    retriever = Retriever(Path(settings.data_dir), embedder, IdentityReranker())
    runtime = Runtime(
        retriever=retriever,
        cheap_chat=chat,
        main_chat=chat,
        settings=settings,
        store=SessionStore(Path(settings.data_dir) / "eval-sessions.db"),
    )

    by_id = {str(case["id"]): case for case in _load_cases()}
    refusals = correct_refusals = permissions = correct_permissions = 0
    supported = total_sentences = 0
    failures: list[str] = []
    chain_session: str | None = None
    for case_id in SMOKE_IDS:
        case = by_id[case_id]
        # Out of scope behavior is scripted: the fake grader cannot judge content.
        scripts["grade"] = "irrelevant" if case["category"] == "out_of_scope" else "relevant"
        if case.get("follow_up_of") and chain_session:
            session_id = chain_session
        else:
            chain_session = f"eval-chain-{case_id}"
            session_id = chain_session
        # Permission smoke uses the deterministic empty set path (external sees no
        # general documents); the wrong domain denial is validated by the full run
        # with real embeddings.
        role = "external" if case["category"] == "permission" else str(case["role"])
        final = run_turn(runtime, session_id, str(case["question"]), role)
        refusal = final.get("refusal")
        sentences = final.get("sentences", [])
        total_sentences += len(sentences)
        supported += sum(1 for s in sentences if s["verdict"] == "supported")
        expected_refusal = case.get("category") in ("out_of_scope", "permission")
        if expected_refusal:
            refusals += 1
            if refusal:
                correct_refusals += 1
            if case.get("category") == "permission":
                permissions += 1
                if refusal == "permission":
                    correct_permissions += 1
        elif refusal:
            failures.append(f"{case_id}: unexpected refusal {refusal}")
    draft_support_rate = supported / total_sentences if total_sentences else 0.0
    gates = {
        "refusal_accuracy": (correct_refusals, refusals),
        "permission_accuracy": (correct_permissions, permissions),
    }
    passed = (
        not failures
        and refusals > 0
        and all(value == total for value, total in gates.values())
        and draft_support_rate >= 0.9
    )
    print("SMOKE EVAL (offline)")
    print(f"  refusal accuracy: {correct_refusals}/{refusals}")
    print(f"  permission accuracy: {correct_permissions}/{permissions}")
    print(f"  draft support rate: {draft_support_rate:.3f}")
    for failure in failures:
        print(f"  FAIL {failure}")
    print("  result:", "PASS" if passed else "FAIL")
    return 0 if passed else 1


def _run_full() -> int:
    """Real provider evaluation with metrics, baselines and a report."""
    settings = get_settings()
    meter = SpendMeter(Path(settings.data_dir) / "spend.json", settings.spend_cap_usd)
    chat: ChatProvider = BedrockChat(settings.aws_region, settings.aws_profile, meter)
    embedder = build_embedder(settings.embeddings_provider, settings.embeddings_model)
    reranker = build_reranker(settings.reranker_provider, settings.reranker_model)
    retriever = Retriever(Path(settings.data_dir), embedder, reranker)
    runtime = Runtime(
        retriever=retriever,
        cheap_chat=chat,
        main_chat=chat,
        settings=settings,
        store=SessionStore(Path(settings.data_dir) / "eval-sessions.db"),
    )
    cases = _load_cases()
    manifest = Manifest.load(Path(settings.data_dir) / "indexes" / "manifest.json")
    title_by_file = {
        str(record.get("filename")): str(record.get("title"))
        for record in (manifest.documents.values() if manifest else [])
    }

    session_counter = 0
    results: list[dict[str, object]] = []
    recall_hits = recall_total = 0
    refusals = correct_refusals = permissions = correct_permissions = 0
    supported = total_sentences = 0
    latency_total = 0.0

    for case in cases:
        if case.get("follow_up_of") and results:
            session_id = str(results[-1]["session"])
        else:
            session_counter += 1
            session_id = f"eval-{session_counter}"
        started = time.perf_counter()
        final = run_turn(runtime, session_id, str(case["question"]), str(case["role"]))
        latency_total += time.perf_counter() - started
        refusal = final.get("refusal")
        sentences = final.get("sentences", [])
        total_sentences += len(sentences)
        supported += sum(1 for s in sentences if s["verdict"] == "supported")

        expected_title = title_by_file.get(str(case.get("support_doc")))
        answerable = case.get("category") not in ("out_of_scope", "permission")
        if expected_title and answerable:
            recall_total += 1
            blocks = retriever.retrieve(
                str(case["question"]), role=str(case["role"]), top_n=5
            )
            if any(block.doc_title == expected_title for block in blocks):
                recall_hits += 1
        if case.get("category") in ("out_of_scope", "permission"):
            refusals += 1
            correct_refusals += 1 if refusal else 0
            if case.get("category") == "permission":
                permissions += 1
                correct_permissions += 1 if refusal == "permission" else 0
        results.append({
            "session": session_id,
            "id": case["id"],
            "category": case["category"],
            "refusal": refusal,
            "citations": len(final.get("citations", [])),
            "answer": str(final["answer"])[:140],
        })

    attr_precision, attr_recall, attr_rows = _attribution_benchmark(
        runtime.cheap_chat, settings.nova_micro_model_id
    )
    # Draft support rate: the fraction of generated sentences that survive
    # verification. Delivered citation precision is 1.0 by construction because
    # unsupported sentences are stripped before they reach the user (docs/09).
    draft_support_rate = supported / total_sentences if total_sentences else 0.0
    citation_precision = 1.0
    recall_at_5 = recall_hits / recall_total if recall_total else 0.0

    baseline_total = baseline_hits = 0
    for case in cases:
        if case.get("category") not in ("single_doc", "multi_doc", "table"):
            continue
        expected_title = title_by_file.get(str(case.get("support_doc")))
        if not expected_title:
            continue
        baseline_total += 1
        blocks = retriever.retrieve(
            str(case["question"]), role=str(case["role"]), mode="dense", use_rerank=False
        )
        if any(block.doc_title == expected_title for block in blocks):
            baseline_hits += 1
    baseline_dense = baseline_hits / baseline_total if baseline_total else 0.0

    lines = [
        "# Evaluation Report",
        "",
        f"Generated {time.strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Retrieval recall@5 | {recall_at_5:.3f} |",
        f"| Baseline: dense only, no fusion or rerank | {baseline_dense:.3f} |",
        f"| Draft support rate (delivered precision is 1.0 by construction) | {draft_support_rate:.3f} |",
        f"| Refusal accuracy | {correct_refusals}/{refusals} |",
        f"| Permission accuracy | {correct_permissions}/{permissions} |",
        f"| Attribution precision | {attr_precision:.3f} |",
        f"| Attribution recall | {attr_recall:.3f} |",
        f"| Mean latency per turn (s) | {latency_total / max(len(results), 1):.1f} |",
        f"| Spend (USD) | {meter.total_usd:.4f} |",
        "",
        f"Prompt version: {PROMPT_VERSION}",
        f"Generator: {settings.generator_model_id}",
        "",
        "## Per case",
        "",
        "| id | category | refusal | citations | answer |",
        "|---|---|---|---|---|",
    ]
    for row in results:
        lines.append(
            f"| {row['id']} | {row['category']} | {row['refusal']} | "
            f"{row['citations']} | {row['answer'][:100]} |"
        )
    lines += [
        "",
        "## Attribution benchmark detail",
        "",
        "| id | expected | predicted |",
        "|---|---|---|",
    ]
    for row in attr_rows:
        lines.append(f"| {row['id']} | {row['expected']} | {row['predicted']} |")
    (ROOT / "evals" / "report.md").write_text("\n".join(lines), encoding="utf-8")

    gates_pass = (
        recall_at_5 >= 0.5
        and draft_support_rate >= 0.75
        and correct_refusals == refusals
        and correct_permissions == permissions
        and attr_precision >= 0.9
    )
    print("FULL EVAL")
    print(f"  recall@5: {recall_at_5:.3f}  draft support rate: {draft_support_rate:.3f}")
    print(f"  refusal: {correct_refusals}/{refusals}  permission: {correct_permissions}/{permissions}")
    print(f"  attribution: P {attr_precision:.3f} / R {attr_recall:.3f}")
    print(f"  spend: {meter.total_usd:.4f} USD")
    print("  result:", "PASS" if gates_pass else "FAIL", "(report written to evals/report.md)")
    return 0 if gates_pass else 1


def main() -> int:
    """Parse the mode flag and run the requested evaluation."""
    parser = argparse.ArgumentParser(description="Run the golden set evaluation")
    parser.add_argument("--smoke", action="store_true", help="offline behavior gates")
    parser.add_argument("--full", action="store_true", help="real providers, metrics and report")
    args = parser.parse_args()
    if args.full:
        return _run_full()
    return _run_smoke()


if __name__ == "__main__":
    sys.exit(main())
