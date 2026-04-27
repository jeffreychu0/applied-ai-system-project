"""
agent.py
========
PawPal++ AI assistant — OpenAI-powered chat agent with tool use.

The agent has read/write access to the owner's live pet data through
a set of named tools. `run_agent_turn` drives the agentic loop: it
keeps calling the model and executing tools until the model produces a
final text response.
"""
from __future__ import annotations

import json
from datetime import date
from datetime import time as dt_time
from typing import Optional

from openai import OpenAI

from pawpal_system import Owner, Pet, Scheduler, Task

# ---------------------------------------------------------------------------
# Tool definitions (OpenAI function-calling format)
# ---------------------------------------------------------------------------

TOOLS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "list_pets",
            "description": "List all pets with their age and pending/total task counts.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_pet_tasks",
            "description": (
                "Get all tasks for a named pet, including status, priority, "
                "duration, frequency, scheduled time, and description."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "pet_name": {
                        "type": "string",
                        "description": "Exact pet name (case-sensitive).",
                    }
                },
                "required": ["pet_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_task",
            "description": "Create a new care task and assign it to a pet.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pet_name":       {"type": "string"},
                    "name":           {"type": "string", "description": "Short task title."},
                    "description":    {"type": "string", "description": "Optional longer description."},
                    "duration":       {"type": "number", "description": "Duration in hours (e.g. 0.5 = 30 min)."},
                    "priority":       {"type": "integer", "minimum": 1, "maximum": 5, "description": "1=lowest, 5=highest."},
                    "frequency":      {"type": "string", "enum": ["daily", "weekly", "monthly", "as_needed"]},
                    "scheduled_time": {"type": "string", "description": "Optional start time in HH:MM (24 h)."},
                },
                "required": ["pet_name", "name", "duration", "priority", "frequency"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "complete_task",
            "description": (
                "Mark a task as complete for a pet. "
                "Daily/weekly tasks auto-spawn their next occurrence."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "pet_name":  {"type": "string"},
                    "task_name": {"type": "string", "description": "Matched case-insensitively."},
                },
                "required": ["pet_name", "task_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "remove_task",
            "description": "Permanently remove a task from a pet.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pet_name":  {"type": "string"},
                    "task_name": {"type": "string"},
                },
                "required": ["pet_name", "task_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_pet",
            "description": "Register a new pet under the owner.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "age":  {"type": "integer", "minimum": 0},
                },
                "required": ["name", "age"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "remove_pet",
            "description": "Remove a pet. Fails if the owner has only one pet left.",
            "parameters": {
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_schedule",
            "description": "Build and return the prioritised schedule for a given date.",
            "parameters": {
                "type": "object",
                "properties": {
                    "date":            {"type": "string", "description": "YYYY-MM-DD. Omit for today."},
                    "daily_cap_hours": {"type": "number", "description": "Daily hour budget. Default 8."},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "detect_conflicts",
            "description": (
                "Check the schedule for a given date for conflicts "
                "(over-budget hours, duplicate task names, time-window overlaps)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "date":            {"type": "string", "description": "YYYY-MM-DD. Omit for today."},
                    "daily_cap_hours": {"type": "number", "description": "Hour cap. Default 8."},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_summary",
            "description": "Return a full text summary of every pet and task.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "reset_recurring_tasks",
            "description": "Reset completed recurring tasks that are due again today.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
]

TOOL_NAMES = [t["function"]["name"] for t in TOOLS]

DEFAULT_MODEL = "gpt-4o-mini"


# ---------------------------------------------------------------------------
# Tool executor  (no dependency on AI provider)
# ---------------------------------------------------------------------------

def execute_tool(name: str, inputs: dict, owner: Owner) -> str:
    """Dispatch one tool call and return a plain-text result string."""
    try:
        if name == "list_pets":
            if not owner.pets:
                return "No pets registered."
            return "\n".join(
                f"- {p.name} (age {p.age}): "
                f"{len(p.pending_tasks)}/{len(p.tasks)} tasks pending"
                for p in owner.pets
            )

        elif name == "get_pet_tasks":
            pet = owner.find_pet_by_name(inputs["pet_name"])
            if not pet:
                available = [p.name for p in owner.pets]
                return (
                    f"Pet '{inputs['pet_name']}' not found. "
                    f"Available pets: {available}"
                )
            if not pet.tasks:
                return f"{pet.name} has no tasks."
            lines = [f"Tasks for {pet.name} (age {pet.age}):"]
            for t in pet.tasks:
                time_str = (
                    f" @{t.scheduled_time.strftime('%H:%M')}"
                    if t.scheduled_time
                    else ""
                )
                status = "done" if t.complete else "pending"
                desc = f" | {t.description}" if t.description else ""
                lines.append(
                    f"  [{status}] (p{t.priority}) {t.name} — "
                    f"{t.duration}h, {t.frequency}{time_str}{desc}"
                )
            return "\n".join(lines)

        elif name == "create_task":
            pet = owner.find_pet_by_name(inputs["pet_name"])
            if not pet:
                return f"Pet '{inputs['pet_name']}' not found."
            sched_time: Optional[dt_time] = None
            if inputs.get("scheduled_time"):
                h, m = map(int, inputs["scheduled_time"].split(":"))
                sched_time = dt_time(h, m)
            task = Task(
                name=inputs["name"],
                description=inputs.get("description", ""),
                duration=float(inputs["duration"]),
                priority=int(inputs["priority"]),
                frequency=inputs["frequency"],
                scheduled_time=sched_time,
            )
            pet.assign_task(task)
            time_part = (
                f" scheduled at {inputs['scheduled_time']}"
                if inputs.get("scheduled_time")
                else ""
            )
            return (
                f"Created task '{task.name}' for {pet.name}: "
                f"priority {task.priority}, {task.duration}h, "
                f"{task.frequency}{time_part}."
            )

        elif name == "complete_task":
            pet = owner.find_pet_by_name(inputs["pet_name"])
            if not pet:
                return f"Pet '{inputs['pet_name']}' not found."
            task = next(
                (t for t in pet.tasks if t.name.lower() == inputs["task_name"].lower()),
                None,
            )
            if not task:
                return f"Task '{inputs['task_name']}' not found for {pet.name}."
            if task.complete:
                return f"'{task.name}' is already marked complete."
            pet.complete_task(task.id)
            spawn = (
                " (next occurrence scheduled)"
                if task.frequency in ("daily", "weekly")
                else ""
            )
            return f"Marked '{task.name}' as complete for {pet.name}{spawn}."

        elif name == "remove_task":
            pet = owner.find_pet_by_name(inputs["pet_name"])
            if not pet:
                return f"Pet '{inputs['pet_name']}' not found."
            task = next(
                (t for t in pet.tasks if t.name.lower() == inputs["task_name"].lower()),
                None,
            )
            if not task:
                return f"Task '{inputs['task_name']}' not found for {pet.name}."
            pet.remove_task(task.id)
            return f"Removed task '{task.name}' from {pet.name}."

        elif name == "add_pet":
            new_pet = Pet(name=inputs["name"], age=int(inputs["age"]))
            owner.add_pet(new_pet)
            return f"Added pet '{new_pet.name}' (age {new_pet.age})."

        elif name == "remove_pet":
            if len(owner.pets) <= 1:
                return "Cannot remove the last remaining pet."
            pet = owner.find_pet_by_name(inputs["name"])
            if not pet:
                return f"Pet '{inputs['name']}' not found."
            owner.remove_pet(pet.id)
            return f"Removed pet '{inputs['name']}'."

        elif name == "get_schedule":
            day = (
                date.fromisoformat(inputs["date"])
                if inputs.get("date")
                else date.today()
            )
            cap = float(inputs.get("daily_cap_hours", 8.0))
            scheduler = Scheduler(owner=owner)
            ordered = scheduler.build_schedule(day).generate()
            if not ordered:
                return f"No tasks scheduled for {day}."
            total_h = sum(t.duration for t in ordered)
            lines = [
                f"Schedule for {day} — {len(ordered)} task(s), "
                f"{total_h:.1f}h total (cap: {cap}h):"
            ]
            for t in ordered:
                status = "✓" if t.complete else "○"
                time_str = (
                    f" @{t.scheduled_time.strftime('%H:%M')}"
                    if t.scheduled_time
                    else ""
                )
                lines.append(
                    f"  {status} [p{t.priority}] {t.name} "
                    f"({t.duration}h, {t.frequency}{time_str})"
                )
            return "\n".join(lines)

        elif name == "detect_conflicts":
            day = (
                date.fromisoformat(inputs["date"])
                if inputs.get("date")
                else date.today()
            )
            cap = float(inputs.get("daily_cap_hours", 8.0))
            issues = Scheduler(owner=owner).detect_conflicts(day, daily_cap_hours=cap)
            if not issues:
                return f"No conflicts detected for {day} (cap: {cap}h)."
            return f"{len(issues)} conflict(s) on {day}:\n" + "\n".join(
                f"  - {i}" for i in issues
            )

        elif name == "get_summary":
            return Scheduler(owner=owner).summary()

        elif name == "reset_recurring_tasks":
            n = Scheduler(owner=owner).reset_recurring_tasks(date.today())
            return f"Reset {n} recurring task(s) to pending."

        else:
            return f"Unknown tool '{name}'."

    except Exception as exc:
        return f"Tool '{name}' failed: {exc}"


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

_SYSTEM = """\
You are PawPal++, an AI assistant built into a pet care scheduling app.
You have live access to the owner's pet data through tools. Use tools \
proactively to read current state before answering questions about pets or tasks.

Available tools:
  Read  : list_pets, get_pet_tasks, get_schedule, detect_conflicts, get_summary
  Write : create_task, complete_task, remove_task, add_pet, remove_pet, reset_recurring_tasks

Guidelines:
- Always call list_pets or get_pet_tasks before referencing pets — never guess names.
- When creating tasks, infer sensible defaults (feeding → daily p5; vet → as_needed p4).
- Confirm write actions briefly after completing them.
- If a pet is not found, list the available pets and ask for clarification.
- Be concise. Do not restate information the user already knows.
- Today is {today}. Owner: {owner_name}.
"""


def _system_prompt(owner: Owner) -> str:
    return _SYSTEM.format(today=date.today().isoformat(), owner_name=owner.name)


# ---------------------------------------------------------------------------
# Agentic loop
# ---------------------------------------------------------------------------

def run_agent_turn(
    user_message: str,
    history: list,
    owner: Owner,
    client: OpenAI,
    model: str = DEFAULT_MODEL,
) -> tuple[str, list]:
    """Run one conversational turn through the tool-use agentic loop.

    Keeps calling the model and executing tools until finish_reason == "stop".

    Args:
        user_message: The new user message.
        history: Prior message dicts (not mutated). Does not include the
            system message — that is prepended fresh on every call.
        owner: Live Owner object — tools modify it in place.
        client: Authenticated OpenAI client.
        model: Model ID to use.

    Returns:
        (reply_text, updated_history) where updated_history includes all
        new assistant/tool messages appended after history.
    """
    # Prepend system message fresh each call so today's date stays current.
    api_messages = (
        [{"role": "system", "content": _system_prompt(owner)}]
        + list(history)
        + [{"role": "user", "content": user_message}]
    )
    updated_history = list(history) + [{"role": "user", "content": user_message}]

    while True:
        response = client.chat.completions.create(
            model=model,
            messages=api_messages,
            tools=TOOLS,
            tool_choice="auto",
        )

        choice = response.choices[0]

        # Build a serialisable assistant message dict.
        assistant_msg: dict = {
            "role": "assistant",
            "content": choice.message.content,
        }
        if choice.message.tool_calls:
            assistant_msg["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in choice.message.tool_calls
            ]

        api_messages.append(assistant_msg)
        updated_history.append(assistant_msg)

        if choice.finish_reason == "stop":
            return choice.message.content or "", updated_history

        if choice.finish_reason == "tool_calls":
            for tc in choice.message.tool_calls:
                result = execute_tool(
                    tc.function.name,
                    json.loads(tc.function.arguments),
                    owner,
                )
                tool_msg = {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result,
                }
                api_messages.append(tool_msg)
                updated_history.append(tool_msg)
        else:
            break

    return "", updated_history
