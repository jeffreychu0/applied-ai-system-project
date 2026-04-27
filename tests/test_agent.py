"""
test_agent.py
=============
Reliability tests for the PawPal+ AI assistant.

Unit tests (no API key required — fast):
    pytest tests/test_agent.py

Integration tests (require ANTHROPIC_API_KEY — calls live Claude API):
    pytest tests/test_agent.py -m integration

Unit tests cover every tool executor function directly.
Integration tests send real prompts to Claude and verify the agent
calls the correct tools and produces sensible state mutations.
"""
import os
import sys
from datetime import date, time

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent import FUNCTION_DECLARATIONS, TOOL_NAMES, execute_tool, run_agent_turn
from pawpal_system import Owner, Pet, Task


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def owner():
    """Owner with two pets and a handful of tasks."""
    o = Owner(name="Test")
    mochi = Pet(name="Mochi", age=2)
    mochi.assign_task(
        Task(
            name="Morning Walk",
            duration=0.5,
            priority=5,
            frequency="daily",
            scheduled_time=time(8, 0),
        )
    )
    mochi.assign_task(
        Task(
            name="Heartworm Pill",
            duration=0.1,
            priority=4,
            frequency="monthly",
            scheduled_time=time(8, 10),
        )
    )
    miso = Pet(name="Miso", age=5)
    miso.assign_task(
        Task(
            name="Feeding",
            duration=0.1,
            priority=5,
            frequency="daily",
            scheduled_time=time(7, 30),
        )
    )
    o.add_pet(mochi)
    o.add_pet(miso)
    return o


@pytest.fixture
def single_pet_owner():
    """Owner with exactly one pet — used to test removal guard."""
    o = Owner(name="Solo")
    o.add_pet(Pet(name="Only", age=3))
    return o


# ---------------------------------------------------------------------------
# Tool executor — unit tests
# ---------------------------------------------------------------------------

class TestListPets:
    def test_shows_all_pet_names(self, owner):
        result = execute_tool("list_pets", {}, owner)
        assert "Mochi" in result
        assert "Miso" in result

    def test_shows_task_counts(self, owner):
        result = execute_tool("list_pets", {}, owner)
        assert "/" in result  # "pending/total" format

    def test_empty_owner_message(self):
        result = execute_tool("list_pets", {}, Owner(name="Empty"))
        assert "no pets" in result.lower()


class TestGetPetTasks:
    def test_shows_task_names(self, owner):
        result = execute_tool("get_pet_tasks", {"pet_name": "Mochi"}, owner)
        assert "Morning Walk" in result
        assert "Heartworm Pill" in result

    def test_includes_metadata(self, owner):
        result = execute_tool("get_pet_tasks", {"pet_name": "Mochi"}, owner)
        assert "daily" in result
        assert "0.5" in result

    def test_pet_not_found_lists_available(self, owner):
        result = execute_tool("get_pet_tasks", {"pet_name": "Rex"}, owner)
        assert "not found" in result.lower()
        assert "Mochi" in result or "Miso" in result

    def test_pet_with_no_tasks(self, owner):
        owner.add_pet(Pet(name="Buddy", age=1))
        result = execute_tool("get_pet_tasks", {"pet_name": "Buddy"}, owner)
        assert "no tasks" in result.lower()


class TestCreateTask:
    def test_task_is_added_to_pet(self, owner):
        mochi = owner.find_pet_by_name("Mochi")
        initial = len(mochi.tasks)
        execute_tool(
            "create_task",
            {
                "pet_name": "Mochi",
                "name": "Bath Time",
                "duration": 0.5,
                "priority": 3,
                "frequency": "weekly",
            },
            owner,
        )
        assert len(mochi.tasks) == initial + 1

    def test_task_attributes_are_correct(self, owner):
        execute_tool(
            "create_task",
            {
                "pet_name": "Mochi",
                "name": "Evening Walk",
                "duration": 0.75,
                "priority": 4,
                "frequency": "daily",
                "scheduled_time": "18:30",
            },
            owner,
        )
        mochi = owner.find_pet_by_name("Mochi")
        task = next(t for t in mochi.tasks if t.name == "Evening Walk")
        assert task.duration == 0.75
        assert task.priority == 4
        assert task.frequency == "daily"
        assert task.scheduled_time == time(18, 30)

    def test_result_confirms_creation(self, owner):
        result = execute_tool(
            "create_task",
            {
                "pet_name": "Mochi",
                "name": "Bath Time",
                "duration": 0.5,
                "priority": 3,
                "frequency": "weekly",
            },
            owner,
        )
        assert "Bath Time" in result

    def test_pet_not_found(self, owner):
        result = execute_tool(
            "create_task",
            {
                "pet_name": "Ghost",
                "name": "Walk",
                "duration": 0.5,
                "priority": 3,
                "frequency": "daily",
            },
            owner,
        )
        assert "not found" in result.lower()


class TestCompleteTask:
    def test_marks_task_complete(self, owner):
        execute_tool(
            "complete_task",
            {"pet_name": "Mochi", "task_name": "Morning Walk"},
            owner,
        )
        mochi = owner.find_pet_by_name("Mochi")
        task = next(t for t in mochi.tasks if t.name == "Morning Walk")
        assert task.complete

    def test_case_insensitive_match(self, owner):
        result = execute_tool(
            "complete_task",
            {"pet_name": "Mochi", "task_name": "morning walk"},
            owner,
        )
        assert "complete" in result.lower()

    def test_daily_task_spawns_next(self, owner):
        mochi = owner.find_pet_by_name("Mochi")
        initial = len(mochi.tasks)
        execute_tool(
            "complete_task",
            {"pet_name": "Mochi", "task_name": "Morning Walk"},
            owner,
        )
        assert len(mochi.tasks) == initial + 1

    def test_already_complete_message(self, owner):
        mochi = owner.find_pet_by_name("Mochi")
        walk = next(t for t in mochi.tasks if t.name == "Morning Walk")
        walk.mark_complete()
        result = execute_tool(
            "complete_task",
            {"pet_name": "Mochi", "task_name": "Morning Walk"},
            owner,
        )
        assert "already" in result.lower()

    def test_task_not_found(self, owner):
        result = execute_tool(
            "complete_task",
            {"pet_name": "Mochi", "task_name": "Nonexistent"},
            owner,
        )
        assert "not found" in result.lower()

    def test_pet_not_found(self, owner):
        result = execute_tool(
            "complete_task",
            {"pet_name": "Ghost", "task_name": "Walk"},
            owner,
        )
        assert "not found" in result.lower()


class TestRemoveTask:
    def test_task_is_removed(self, owner):
        mochi = owner.find_pet_by_name("Mochi")
        initial = len(mochi.tasks)
        execute_tool(
            "remove_task",
            {"pet_name": "Mochi", "task_name": "Morning Walk"},
            owner,
        )
        assert len(mochi.tasks) == initial - 1

    def test_result_confirms_removal(self, owner):
        result = execute_tool(
            "remove_task",
            {"pet_name": "Mochi", "task_name": "Morning Walk"},
            owner,
        )
        assert "removed" in result.lower()

    def test_task_not_found(self, owner):
        result = execute_tool(
            "remove_task",
            {"pet_name": "Mochi", "task_name": "Nonexistent"},
            owner,
        )
        assert "not found" in result.lower()

    def test_pet_not_found(self, owner):
        result = execute_tool(
            "remove_task",
            {"pet_name": "Ghost", "task_name": "Walk"},
            owner,
        )
        assert "not found" in result.lower()


class TestAddPet:
    def test_pet_is_added(self, owner):
        initial = len(owner.pets)
        execute_tool("add_pet", {"name": "Buddy", "age": 3}, owner)
        assert len(owner.pets) == initial + 1

    def test_pet_is_findable_by_name(self, owner):
        execute_tool("add_pet", {"name": "Buddy", "age": 3}, owner)
        assert owner.find_pet_by_name("Buddy") is not None

    def test_result_confirms_addition(self, owner):
        result = execute_tool("add_pet", {"name": "Buddy", "age": 3}, owner)
        assert "Buddy" in result


class TestRemovePet:
    def test_pet_is_removed(self, owner):
        initial = len(owner.pets)
        execute_tool("remove_pet", {"name": "Miso"}, owner)
        assert len(owner.pets) == initial - 1

    def test_result_confirms_removal(self, owner):
        result = execute_tool("remove_pet", {"name": "Miso"}, owner)
        assert "removed" in result.lower()

    def test_cannot_remove_last_pet(self, single_pet_owner):
        result = execute_tool("remove_pet", {"name": "Only"}, single_pet_owner)
        assert "cannot" in result.lower() or "last" in result.lower()

    def test_pet_not_found(self, owner):
        result = execute_tool("remove_pet", {"name": "Ghost"}, owner)
        assert "not found" in result.lower()


class TestGetSchedule:
    def test_returns_schedule_string(self, owner):
        result = execute_tool("get_schedule", {}, owner)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_includes_daily_tasks(self, owner):
        result = execute_tool("get_schedule", {}, owner)
        # Morning Walk and Feeding are daily — always in schedule
        assert "Morning Walk" in result or "Feeding" in result

    def test_specific_date_in_output(self, owner):
        result = execute_tool("get_schedule", {"date": "2026-06-15"}, owner)
        assert "2026-06-15" in result

    def test_empty_schedule_message(self):
        o = Owner(name="Empty")
        o.add_pet(Pet(name="NoTasks", age=1))
        result = execute_tool("get_schedule", {}, o)
        assert "no tasks" in result.lower()


class TestDetectConflicts:
    def test_returns_string(self, owner):
        result = execute_tool("detect_conflicts", {}, owner)
        assert isinstance(result, str)

    def test_detects_overlap(self):
        """Two tasks that obviously overlap should produce a conflict report."""
        o = Owner(name="Conflict")
        p = Pet(name="Dog", age=1)
        p.assign_task(
            Task(name="Walk", duration=1.0, priority=5, frequency="daily",
                 scheduled_time=time(8, 0))
        )
        p.assign_task(
            Task(name="Training", duration=1.0, priority=4, frequency="daily",
                 scheduled_time=time(8, 30))
        )
        o.add_pet(p)
        result = execute_tool("detect_conflicts", {}, o)
        assert "conflict" in result.lower() or "overlap" in result.lower()

    def test_no_conflicts_clean(self):
        o = Owner(name="Clean")
        p = Pet(name="Dog", age=1)
        p.assign_task(
            Task(name="Walk", duration=0.5, priority=5, frequency="daily",
                 scheduled_time=time(8, 0))
        )
        o.add_pet(p)
        result = execute_tool("detect_conflicts", {"daily_cap_hours": 24.0}, o)
        assert "no conflicts" in result.lower()


class TestGetSummary:
    def test_includes_owner_name(self, owner):
        result = execute_tool("get_summary", {}, owner)
        assert "Test" in result

    def test_includes_all_pets(self, owner):
        result = execute_tool("get_summary", {}, owner)
        assert "Mochi" in result
        assert "Miso" in result

    def test_includes_task_names(self, owner):
        result = execute_tool("get_summary", {}, owner)
        assert "Morning Walk" in result


class TestResetRecurring:
    def test_resets_completed_daily_task(self, owner):
        mochi = owner.find_pet_by_name("Mochi")
        walk = next(t for t in mochi.tasks if t.name == "Morning Walk")
        walk.mark_complete()
        execute_tool("reset_recurring_tasks", {}, owner)
        assert not walk.complete

    def test_returns_count_message(self, owner):
        mochi = owner.find_pet_by_name("Mochi")
        mochi.tasks[0].mark_complete()
        result = execute_tool("reset_recurring_tasks", {}, owner)
        assert "Reset" in result

    def test_no_completed_tasks_returns_zero(self, owner):
        result = execute_tool("reset_recurring_tasks", {}, owner)
        assert "0" in result


class TestUnknownTool:
    def test_unknown_tool_returns_error(self, owner):
        result = execute_tool("does_not_exist", {}, owner)
        assert "unknown" in result.lower() or "does_not_exist" in result


# ---------------------------------------------------------------------------
# Tool schema sanity checks
# ---------------------------------------------------------------------------

class TestToolDefinitions:
    def test_all_declarations_have_required_fields(self):
        for fd in FUNCTION_DECLARATIONS:
            assert fd.name, f"FunctionDeclaration missing name: {fd}"
            assert fd.description, f"FunctionDeclaration missing description: {fd}"
            assert fd.parameters is not None, f"FunctionDeclaration missing parameters: {fd}"

    def test_tool_names_are_unique(self):
        assert len(TOOL_NAMES) == len(set(TOOL_NAMES)), "Duplicate tool names found"

    def test_expected_tools_present(self):
        expected = {
            "list_pets", "get_pet_tasks", "create_task", "complete_task",
            "remove_task", "add_pet", "remove_pet", "get_schedule",
            "detect_conflicts", "get_summary", "reset_recurring_tasks",
        }
        assert expected.issubset(set(TOOL_NAMES)), f"Missing tools: {expected - set(TOOL_NAMES)}"


# ---------------------------------------------------------------------------
# Integration tests — require ANTHROPIC_API_KEY
# ---------------------------------------------------------------------------

integration = pytest.mark.skipif(
    not os.environ.get("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY not set — skipping integration tests",
)


@integration
class TestAgentIntegration:
    """Live OpenAI API tests. Run with: pytest tests/test_agent.py -m integration"""

    @pytest.fixture(autouse=True)
    def _setup(self, owner):
        from openai import OpenAI
        self.owner = owner
        self.client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        self.history: list = []

    def _turn(self, msg: str) -> str:
        reply, self.history = run_agent_turn(
            msg, self.history, self.owner, self.client
        )
        return reply

    def test_agent_lists_pets(self):
        reply = self._turn("What pets do I have?")
        assert "Mochi" in reply or "Miso" in reply

    def test_agent_creates_task_from_natural_language(self):
        mochi = self.owner.find_pet_by_name("Mochi")
        initial = len(mochi.tasks)
        self._turn("Add a weekly grooming task for Mochi, 1 hour, medium priority.")
        assert len(mochi.tasks) > initial

    def test_agent_handles_unknown_pet_gracefully(self):
        reply = self._turn("Add a morning run for Rex.")
        # Agent must not silently do nothing — it should acknowledge the problem
        assert (
            "not found" in reply.lower()
            or "mochi" in reply.lower()
            or "miso" in reply.lower()
            or "which pet" in reply.lower()
        )

    def test_agent_generates_schedule(self):
        reply = self._turn("Show me today's schedule.")
        assert any(
            w in reply.lower()
            for w in ("schedule", "task", "walk", "feeding", "no tasks")
        )

    def test_agent_completes_task(self):
        self._turn("Mark Mochi's morning walk as done.")
        mochi = self.owner.find_pet_by_name("Mochi")
        walk = next(
            (t for t in mochi.tasks if t.name.lower() == "morning walk"), None
        )
        assert walk is not None and walk.complete

    def test_agent_detects_conflicts(self):
        reply = self._turn("Are there any scheduling conflicts today?")
        assert any(
            w in reply.lower()
            for w in ("conflict", "overlap", "no conflict", "schedule")
        )

    def test_agent_multi_turn_adds_to_previously_mentioned_pet(self):
        self._turn("How many tasks does Mochi have?")
        self._turn("Add a bath task to the same pet — 0.5 hours, weekly.")
        mochi = self.owner.find_pet_by_name("Mochi")
        assert any("bath" in t.name.lower() for t in mochi.tasks)
