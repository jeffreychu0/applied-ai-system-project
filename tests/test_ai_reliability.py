"""
test_ai_reliability.py
======================
Comprehensive AI reliability evaluation for the PawPal++ agent.

Covers four dimensions:
  1. Automated checks    -- pass/fail assertions on agent behaviour and state mutations
  2. Confidence scoring  -- a second model call rates each reply (0-10)
  3. Logging             -- all inputs, outputs, scores, and errors saved to log + JSON
  4. Human evaluation    -- markdown report generated for peer/instructor review

Run (requires OPENAI_API_KEY in .env):
    pytest tests/test_ai_reliability.py -v -s

Reports saved to: tests/reports/
"""
from __future__ import annotations

import json
import logging
import os
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, time as dt_time
from pathlib import Path
from typing import Callable, Optional

import pytest
from dotenv import load_dotenv
from openai import OpenAI

_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))
load_dotenv(_ROOT / ".env")

from agent import DEFAULT_MODEL, run_agent_turn
from pawpal_system import Owner, Pet, Task

# ---------------------------------------------------------------------------
# Logging — writes to both console and a timestamped file
# ---------------------------------------------------------------------------
REPORTS_DIR = Path(__file__).parent / "reports"
REPORTS_DIR.mkdir(exist_ok=True)

_ts = datetime.now().strftime("%Y%m%d_%H%M%S")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    handlers=[
        logging.FileHandler(REPORTS_DIR / f"ai_reliability_{_ts}.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("ai_reliability")

# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class CaseResult:
    name: str
    prompt: str
    reply: str
    passed: bool
    reason: str
    confidence: Optional[float]   # 0.0 – 1.0  (None if scoring call failed)
    error: Optional[str]
    duration_s: float

# ---------------------------------------------------------------------------
# Shared owner factory — every test case gets a fresh, identical owner
# ---------------------------------------------------------------------------

def _make_owner() -> Owner:
    o = Owner(name="Jordan")
    mochi = Pet(name="Mochi", age=2)
    mochi.assign_task(Task(name="Morning Walk",      duration=0.5,  priority=5,
                           frequency="daily",   scheduled_time=dt_time(8, 0)))
    mochi.assign_task(Task(name="Heartworm Pill",    duration=0.1,  priority=4,
                           frequency="monthly", scheduled_time=dt_time(8, 10)))
    mochi.assign_task(Task(name="Obedience Training",duration=1.0,  priority=3,
                           frequency="weekly"))
    miso = Pet(name="Miso", age=5)
    miso.assign_task(Task(name="Feeding",     duration=0.1,  priority=5,
                          frequency="daily",  scheduled_time=dt_time(7, 30)))
    miso.assign_task(Task(name="Brush Coat",  duration=0.25, priority=2,
                          frequency="weekly"))
    o.add_pet(mochi)
    o.add_pet(miso)
    return o

# ---------------------------------------------------------------------------
# Confidence scoring — separate evaluator call, best-effort
# ---------------------------------------------------------------------------

def _get_confidence(client: OpenAI, prompt: str, reply: str) -> Optional[float]:
    """
    Ask the model to rate the reply's accuracy and helpfulness (0-10).
    Returns a 0.0-1.0 float, or None if the call fails.
    """
    if not reply:
        return 0.0
    try:
        resp = client.chat.completions.create(
            model=DEFAULT_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You evaluate AI assistant responses for accuracy and helpfulness. "
                        "Reply with a single integer from 0 to 10 — nothing else."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Question asked: {prompt}\n\n"
                        f"AI response: {reply}\n\n"
                        "Rate accuracy and helpfulness 0-10 (10 = excellent). Integer only."
                    ),
                },
            ],
            max_tokens=5,
            temperature=0,
        )
        raw = resp.choices[0].message.content.strip().split()[0]
        score = float("".join(c for c in raw if c.isdigit() or c == "."))
        return round(min(max(score / 10.0, 0.0), 1.0), 2)
    except Exception as exc:
        log.warning(f"Confidence scoring failed: {exc}")
        return None

# ---------------------------------------------------------------------------
# Pre-setup helpers (mutate owner before the agent runs)
# ---------------------------------------------------------------------------

def _complete_all_daily(owner: Owner) -> None:
    """Mark every daily task complete so reset_recurring has something to do."""
    for pet in owner.pets:
        for task in pet.tasks:
            if task.frequency == "daily":
                task.mark_complete()

# ---------------------------------------------------------------------------
# Check functions  (reply: str, owner: Owner) -> (passed: bool, reason: str)
# ---------------------------------------------------------------------------

def _chk_pet_listing(reply: str, owner: Owner):
    ok = "mochi" in reply.lower() and "miso" in reply.lower()
    return ok, ("Both Mochi and Miso named in reply"
                if ok else f"Missing pet name — reply: {reply[:120]}")


def _chk_task_creation(reply: str, owner: Owner):
    mochi = owner.find_pet_by_name("Mochi")
    ok = mochi is not None and any("bath" in t.name.lower() for t in mochi.tasks)
    return ok, ("Bath task added to Mochi"
                if ok else "Bath task not found in Mochi's task list")


def _chk_task_completion(reply: str, owner: Owner):
    mochi = owner.find_pet_by_name("Mochi")
    ok = mochi is not None and any(
        t.name.lower() == "morning walk" and t.complete for t in mochi.tasks
    )
    return ok, ("Morning Walk marked complete"
                if ok else "Morning Walk not marked complete in state")


def _chk_schedule(reply: str, owner: Owner):
    ok = any(w in reply.lower() for w in ["schedule", "task", "walk", "feeding", "no task"])
    return ok, ("Schedule content present in reply"
                if ok else f"No schedule content — reply: {reply[:120]}")


def _chk_conflicts(reply: str, owner: Owner):
    ok = any(w in reply.lower()
             for w in ["conflict", "overlap", "no conflict", "detected", "schedule"])
    return ok, ("Conflict result communicated"
                if ok else f"No conflict info — reply: {reply[:120]}")


def _chk_unknown_pet(reply: str, owner: Owner):
    charlie_created = owner.find_pet_by_name("Charlie") is not None
    flagged = any(w in reply.lower()
                  for w in ["not found", "mochi", "miso", "which", "available"])
    ok = not charlie_created and flagged
    return ok, ("Agent flagged unknown pet and listed alternatives"
                if ok else f"Agent may have silently ignored unknown pet — reply: {reply[:120]}")


def _chk_task_removal(reply: str, owner: Owner):
    mochi = owner.find_pet_by_name("Mochi")
    still_there = mochi is not None and any(
        t.name.lower() == "heartworm pill" for t in mochi.tasks
    )
    ok = not still_there
    return ok, ("Heartworm Pill successfully removed"
                if ok else "Heartworm Pill still present in Mochi's task list")


def _chk_summary(reply: str, owner: Owner):
    ok = "mochi" in reply.lower() and "miso" in reply.lower()
    return ok, ("Both pets present in summary"
                if ok else f"Missing pets in summary — reply: {reply[:120]}")


def _chk_add_pet(reply: str, owner: Owner):
    ok = owner.find_pet_by_name("Buddy") is not None
    return ok, ("Buddy added to owner's pet list"
                if ok else "Buddy not found in owner's pets after agent reply")


def _chk_reset(reply: str, owner: Owner):
    ok = any(w in reply.lower() for w in ["reset", "recurring", "pending", "task"])
    return ok, ("Reset confirmation found in reply"
                if ok else f"No reset confirmation — reply: {reply[:120]}")

# ---------------------------------------------------------------------------
# Test-case table
# (name, prompt, pre_setup | None, check_fn)
# ---------------------------------------------------------------------------

CASES: list[tuple] = [
    (
        "pet_listing",
        "What pets do I have?",
        None,
        _chk_pet_listing,
    ),
    (
        "task_creation",
        "Add a weekly bath task for Mochi, 30 minutes, priority 3.",
        None,
        _chk_task_creation,
    ),
    (
        "task_completion",
        "Mark Mochi's morning walk as done.",
        None,
        _chk_task_completion,
    ),
    (
        "schedule_generation",
        "What tasks are scheduled for today?",
        None,
        _chk_schedule,
    ),
    (
        "conflict_detection",
        "Are there any scheduling conflicts today?",
        None,
        _chk_conflicts,
    ),
    (
        "unknown_pet_handling",
        "Add a daily walk for Charlie.",
        None,
        _chk_unknown_pet,
    ),
    (
        "task_removal",
        "Remove the heartworm pill task from Mochi.",
        None,
        _chk_task_removal,
    ),
    (
        "full_summary",
        "Give me a full summary of all my pets and their tasks.",
        None,
        _chk_summary,
    ),
    (
        "add_pet",
        "Add a new pet named Buddy, age 4.",
        None,
        _chk_add_pet,
    ),
    (
        "reset_recurring",
        "Reset all recurring tasks for today.",
        _complete_all_daily,   # pre-setup: mark daily tasks done first
        _chk_reset,
    ),
]

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def ai_client():
    key = os.environ.get("OPENAI_API_KEY", "")
    if not key:
        pytest.skip("OPENAI_API_KEY not set — skipping AI reliability tests")
    return OpenAI(api_key=key)


@pytest.fixture(scope="module")
def report():
    """Accumulate results across all cases; write reports on teardown."""
    results: list[CaseResult] = []
    yield results
    _write_reports(results)

# ---------------------------------------------------------------------------
# Parametrised test
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name,prompt,setup,check", CASES, ids=[c[0] for c in CASES])
def test_ai_case(name, prompt, setup, check, ai_client, report):
    owner = _make_owner()
    if setup:
        setup(owner)

    log.info("-" * 60)
    log.info(f"[{name}] PROMPT: {prompt}")

    t0 = time.perf_counter()
    reply = ""
    error = None

    try:
        reply, _ = run_agent_turn(prompt, [], owner, ai_client)
        log.info(f"[{name}] REPLY : {reply[:200]}")
    except Exception as exc:
        error = str(exc)
        log.error(f"[{name}] Agent turn raised: {exc}")

    duration = round(time.perf_counter() - t0, 2)

    # --- automated check -----------------------------------------------
    try:
        if error:
            passed, reason = False, f"Agent error: {error}"
        else:
            passed, reason = check(reply, owner)
    except Exception as exc:
        passed, reason = False, f"Check function raised: {exc}"
        log.error(f"[{name}] Check function error: {exc}")

    # --- confidence scoring --------------------------------------------
    confidence = _get_confidence(ai_client, prompt, reply)
    conf_str = f"{confidence * 10:.1f}/10" if confidence is not None else "n/a"

    result = CaseResult(
        name=name, prompt=prompt, reply=reply,
        passed=passed, reason=reason,
        confidence=confidence, error=error,
        duration_s=duration,
    )
    report.append(result)

    status = "PASS" if passed else "FAIL"
    log.info(f"[{name}] {status} | confidence={conf_str} | {duration}s | {reason}")

    assert passed, f"[{name}] FAILED — {reason}"

# ---------------------------------------------------------------------------
# Report writer
# ---------------------------------------------------------------------------

def _write_reports(results: list[CaseResult]) -> None:
    if not results:
        log.warning("No results to report.")
        return

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    total    = len(results)
    passed_n = sum(1 for r in results if r.passed)
    failed_n = total - passed_n
    confs    = [r.confidence for r in results if r.confidence is not None]
    avg_conf = round(sum(confs) / len(confs) * 10, 1) if confs else None

    # ── JSON log ──────────────────────────────────────────────────────────────
    json_path = REPORTS_DIR / f"ai_reliability_{ts}.json"
    json_path.write_text(
        json.dumps(
            {
                "generated": datetime.now().isoformat(),
                "model": DEFAULT_MODEL,
                "summary": {
                    "total": total,
                    "passed": passed_n,
                    "failed": failed_n,
                    "avg_confidence_out_of_10": avg_conf,
                },
                "results": [asdict(r) for r in results],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    log.info(f"JSON log  -> {json_path}")

    # ── Markdown report ───────────────────────────────────────────────────────
    md_path  = REPORTS_DIR / f"ai_reliability_{ts}.md"
    conf_disp = f"{avg_conf}/10" if avg_conf is not None else "n/a"

    lines = [
        "# PawPal++ AI Reliability Report",
        f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  ",
        f"**Model:** `{DEFAULT_MODEL}`",
        "",
        "---",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Total cases | {total} |",
        f"| Passed | {passed_n} |",
        f"| Failed | {failed_n} |",
        f"| Average confidence | {conf_disp} |",
        "",
        "---",
        "",
        "## Results Table",
        "",
        "| # | Test | Result | Confidence | Duration | Reason |",
        "|---|------|--------|------------|----------|--------|",
    ]
    for i, r in enumerate(results, 1):
        icon = "PASS" if r.passed else "FAIL"
        conf = f"{r.confidence * 10:.1f}/10" if r.confidence is not None else "n/a"
        lines.append(
            f"| {i} | `{r.name}` | {icon} | {conf} | {r.duration_s}s | {r.reason} |"
        )

    lines += [
        "",
        "---",
        "",
        "## Detailed Results",
        "",
    ]
    for r in results:
        status = "PASS" if r.passed else "FAIL"
        conf   = f"{r.confidence * 10:.1f}/10" if r.confidence is not None else "n/a"
        lines += [
            f"### {r.name}",
            "",
            f"| Field | Value |",
            f"|-------|-------|",
            f"| Status | **{status}** |",
            f"| Confidence | {conf} |",
            f"| Duration | {r.duration_s}s |",
            f"| Check result | {r.reason} |",
        ]
        if r.error:
            lines.append(f"| Error | `{r.error}` |")
        lines += [
            "",
            f"**Prompt:** {r.prompt}",
            "",
            "**Reply:**",
            "```",
            r.reply or "(no reply — see error above)",
            "```",
            "",
        ]

    lines += [
        "---",
        "",
        "## Human Evaluation",
        "",
        "_Complete this section after reviewing the Detailed Results above._",
        "",
        f"**Reviewer:** ___________________  **Date:** ___________________",
        "",
        "| # | Test | Human Rating (1-5) | Notes |",
        "|---|------|--------------------|-------|",
    ]
    for i, r in enumerate(results, 1):
        lines.append(f"| {i} | `{r.name}` | | |")

    lines += [
        "",
        "**Rating scale:** 1 = completely wrong, 3 = acceptable, 5 = excellent",
        "",
        "**Overall assessment:**",
        "",
        "> _Write your overall evaluation of the AI assistant here._",
        "",
        "**What worked well:**",
        "",
        "> ",
        "",
        "**What needs improvement:**",
        "",
        "> ",
    ]

    md_path.write_text("\n".join(lines), encoding="utf-8")
    log.info(f"Markdown  -> {md_path}")

    # ── Console banner ────────────────────────────────────────────────────────
    log.info("=" * 60)
    log.info(f"  RELIABILITY RESULT: {passed_n}/{total} passed | avg confidence {conf_disp}")
    log.info("=" * 60)
