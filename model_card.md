# Model Card — PawPal+ AI Assistant

## Model Overview

| Field | Value |
|-------|-------|
| Model ID | `gpt-4o-mini` |
| Provider | OpenAI |
| API | OpenAI Chat Completions (tool use) |
| Integration file | `agent.py` |
| Interface | Streamlit chat tab (`app.py`) |

## Intended Use

PawPal+ uses `gpt-4o-mini` as the reasoning core of a conversational pet care scheduling assistant. The model's role is to interpret natural-language requests from a pet owner and translate them into structured tool calls that read or mutate a live in-memory data model (`Owner`, `Pet`, `Task`).

**Primary use cases:**
- Answering questions about registered pets and their tasks
- Creating, completing, and removing care tasks via natural language
- Generating and interpreting daily care schedules
- Detecting time conflicts between overlapping tasks
- Adding or removing pets from the owner's profile

**Out-of-scope uses:**
- General veterinary or medical advice
- Tasks unrelated to pet care scheduling
- Any use outside a single-session Streamlit context (no persistent memory across sessions)

## Architecture

The model operates inside a tool-use agentic loop (`run_agent_turn` in `agent.py`):

1. A system prompt is injected fresh on every turn, providing the current date and owner name.
2. The full conversation history is passed as context.
3. The model may call one or more tools (see table below) before producing a final reply.
4. Tool results are fed back to the model; the loop continues until `finish_reason == "stop"`.

The model never sees raw Python objects — only plain-text tool results returned by `execute_tool`.

## Tools

| Tool | Access | Description |
|------|--------|-------------|
| `list_pets` | Read | All pets with pending/total task counts |
| `get_pet_tasks` | Read | Full task list for one pet |
| `get_schedule` | Read | Prioritised schedule for a given date |
| `detect_conflicts` | Read | Hour-cap, duplicate, and time-overlap conflicts |
| `get_summary` | Read | Full text summary of all pets and tasks |
| `create_task` | Write | Add a new care task to a pet |
| `complete_task` | Write | Mark a task done; daily/weekly tasks auto-respawn |
| `remove_task` | Write | Permanently delete a task |
| `add_pet` | Write | Register a new pet |
| `remove_pet` | Write | Remove a pet (blocked if only one remains) |
| `reset_recurring_tasks` | Write | Reset completed recurring tasks to pending |

## System Prompt Constraints

The model is given explicit behavioural guidelines at the start of every turn:

- Always call `list_pets` or `get_pet_tasks` before referencing pet state — never guess.
- Infer sensible task defaults when the user's request is ambiguous (e.g., feeding → daily, priority 5).
- Confirm write actions briefly after completion.
- If a named pet is not found, list available pets and ask for clarification rather than creating a new one or failing silently.
- Be concise; do not restate information the user already knows.

## Performance (Reliability Test — 2026-04-27)

Evaluated via `tests/test_ai_reliability.py` against 10 parametrised test cases.

| Test | Result | Confidence | Duration |
|------|--------|------------|----------|
| pet_listing | PASS | — | 4.1s |
| task_creation | PASS | 8.0/10 | 3.6s |
| task_completion | PASS | 10.0/10 | 6.4s |
| schedule_generation | PASS | 8.0/10 | 4.1s |
| conflict_detection | PASS | 8.0/10 | 4.9s |
| unknown_pet_handling | PASS | 3.0/10 | 2.8s |
| task_removal | PASS | 10.0/10 | 5.0s |
| full_summary | PASS | 8.0/10 | 6.6s |
| add_pet | PASS | 10.0/10 | 2.3s |
| reset_recurring | PASS | 7.0/10 | 2.4s |

**10/10 automated checks passed. Average confidence: 7.2/10.**

Confidence scores are produced by a secondary `gpt-4o-mini` call that rates the primary response for accuracy and helpfulness on a 0–10 scale. The `unknown_pet_handling` case scored 3.0/10 on confidence despite passing the automated check, indicating the response is functionally correct but the evaluator found it less polished.

## Limitations

- **No persistent memory.** All state is held in Streamlit session state; closing the browser tab clears everything.
- **Single owner.** The system is scoped to one owner per session; multi-user scenarios are unsupported.
- **No veterinary knowledge.** The model does not have access to veterinary databases or medical guidelines — it schedules tasks as directed but cannot advise on health matters.
- **Tool-name case sensitivity.** `find_pet_by_name` performs an exact case-sensitive lookup; the model is instructed to call `list_pets` first to retrieve exact names, but may occasionally pass an incorrectly-cased name.
- **Latency.** Each turn requires at least one API round-trip (~2–7 s observed); complex requests that require multiple tool calls will be slower.
- **Cost.** Every message triggers one or more OpenAI API calls. High-volume or automated usage will incur charges.

## Ethical Considerations

- **Data privacy.** Pet and owner data entered into the app is sent to the OpenAI API as part of the prompt context. Users should not enter personally identifiable or sensitive information.
- **Hallucination risk.** The model is constrained by its system prompt to use tools rather than guess, but no LLM is immune to hallucination. All write actions (task creation, deletion) should be verified by the user in the manual tabs.
- **Bias.** `gpt-4o-mini` inherits any biases present in OpenAI's training data. These are unlikely to affect scheduling tasks but may surface in open-ended natural-language responses.

## Evaluation Method

Full automated reliability evaluation can be reproduced at any time:

```bash
pytest tests/test_ai_reliability.py -v -s
```

Reports (JSON + Markdown with human evaluation table) are written to `tests/reports/`.
The Markdown report includes a structured section for human rater scoring (1–5 per test case).

## Dependencies

| Package | Purpose |
|---------|---------|
| `openai>=1.0` | API client and tool-call parsing |
| `python-dotenv>=1.0` | Load `OPENAI_API_KEY` from `.env` |
