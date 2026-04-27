"""
pawpal_system.py
================
Core domain model for the PawPal++ pet care scheduling application.

Classes:
    Task      -- A single pet care activity.
    Pet       -- A pet with its own list of Tasks.
    Owner     -- An owner who manages one or more Pets.
    Schedule  -- A single-day ordered view of Tasks.
    Scheduler -- Cross-pet task retrieval and schedule generation.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import List, Optional, Tuple
from uuid import UUID, uuid4

# Maps frequency strings to urgency order (lower = higher urgency).
# Used as a sort tiebreaker: a daily task outranks a weekly one at
# equal priority.
_FREQ_ORDER = {"daily": 0, "weekly": 1, "monthly": 2, "as_needed": 3}


@dataclass
class Task:
    """A single pet care activity.

    Attributes:
        id (UUID): Auto-generated unique identifier.
        name (str): Short label for the task (e.g. "Morning Walk").
        description (str): Longer explanation of what the task involves.
        duration (float): Expected time to complete the task, in hours.
        priority (int): Importance ranking from 1 (lowest) to 5 (highest).
        frequency (str): How often the task recurs. One of:
            ``"daily"``, ``"weekly"``, ``"monthly"``, or ``"as_needed"``.
        complete (bool): Whether the task has been completed.
    """

    id: UUID = field(default_factory=uuid4)
    name: str = ""
    description: str = ""
    duration: float = 0.0        # hours
    priority: int = 1            # 1 (low) .. 5 (high)
    frequency: str = "daily"     # "daily" | "weekly" | "monthly" | "as_needed"
    complete: bool = False
    start_date: date = field(default_factory=date.today)  # anchor day for recurrence
    scheduled_time: Optional[time] = None                 # wall-clock start time, if assigned

    def next_occurrence(self) -> Optional[Task]:
        """Return a new Task for the next scheduled occurrence of this task.

        Copies all attributes except ``id`` (fresh UUID), ``complete``
        (always ``False``), and ``start_date`` (advanced by one period):

        - ``"daily"``    -- ``start_date + 1 day``
        - ``"weekly"``   -- ``start_date + 7 days``
        - ``"monthly"``  -- returns ``None`` (no auto-spawn)
        - ``"as_needed"``-- returns ``None`` (no auto-spawn)

        Returns:
            Task: A new incomplete Task anchored to the next occurrence,
            or ``None`` if this frequency does not auto-recur.
        """
        if self.frequency == "daily":
            next_start = self.start_date + timedelta(days=1)
        elif self.frequency == "weekly":
            next_start = self.start_date + timedelta(weeks=1)
        else:
            return None
        return Task(
            name=self.name,
            description=self.description,
            duration=self.duration,
            priority=self.priority,
            frequency=self.frequency,
            start_date=next_start,
            scheduled_time=self.scheduled_time,
        )

    def mark_complete(self) -> None:
        """Mark this task as completed.

        Sets ``complete`` to ``True``. Has no effect if the task is
        already complete.
        """
        self.complete = True

    def mark_incomplete(self) -> None:
        """Reset this task to incomplete.

        Sets ``complete`` to ``False``. Useful for re-scheduling a task
        on a new day or after an accidental completion.
        """
        self.complete = False

    def update(self, *, name: Optional[str] = None, description: Optional[str] = None,
               duration: Optional[float] = None, priority: Optional[int] = None,
               frequency: Optional[str] = None) -> None:
        """Update one or more fields on this task in place.

        Only keyword arguments that are explicitly passed (i.e. not
        ``None``) are applied, so callers can change a single field
        without touching the rest.

        Args:
            name (str, optional): New short label for the task.
            description (str, optional): New detailed description.
            duration (float, optional): New expected duration in hours.
            priority (int, optional): New priority ranking (1–5).
            frequency (str, optional): New recurrence frequency string.
        """
        if name is not None:
            self.name = name
        if description is not None:
            self.description = description
        if duration is not None:
            self.duration = duration
        if priority is not None:
            self.priority = priority
        if frequency is not None:
            self.frequency = frequency

    def __str__(self) -> str:
        """Return a human-readable one-line summary of this task.

        Returns:
            str: A string in the form
            ``"[pending] Walk (priority=5, 0.5h, daily)"``.
        """
        status = "done" if self.complete else "pending"
        return f"[{status}] {self.name} (priority={self.priority}, {self.duration}h, {self.frequency})"


@dataclass
class Pet:
    """A pet with its own list of care tasks.

    Attributes:
        id (UUID): Auto-generated unique identifier.
        name (str): The pet's name (e.g. "Buddy").
        age (int): The pet's age in years.
        tasks (List[Task]): All tasks assigned to this pet.
    """

    id: UUID = field(default_factory=uuid4)
    name: str = ""
    age: int = 0
    tasks: List[Task] = field(default_factory=list)

    def assign_task(self, task: Task) -> None:
        """Append a task to this pet's task list.

        Args:
            task (Task): The task to assign.
        """
        self.tasks.append(task)

    def get_task(self, task_id: UUID) -> Optional[Task]:
        """Look up a task by its unique identifier.

        Args:
            task_id (UUID): The id of the task to find.

        Returns:
            Task: The matching task, or ``None`` if not found.
        """
        return next((t for t in self.tasks if t.id == task_id), None)

    def complete_task(self, task_id: UUID) -> bool:
        """Mark a task as complete and schedule the next occurrence.

        After marking the task complete, calls :meth:`Task.next_occurrence`.
        If a next occurrence is returned (``"daily"`` and ``"weekly"``
        frequencies), the new Task is appended to this pet's task list so
        the recurring duty is never lost.

        Args:
            task_id (UUID): The id of the task to complete.

        Returns:
            bool: ``True`` if the task was found and marked complete,
            ``False`` if no task with that id exists.
        """
        task = self.get_task(task_id)
        if task:
            task.mark_complete()
            next_task = task.next_occurrence()
            if next_task is not None:
                self.tasks.append(next_task)
            return True
        return False

    def uncomplete_task(self, task_id: UUID) -> bool:
        """Reset a task back to incomplete.

        Args:
            task_id (UUID): The id of the task to reset.

        Returns:
            bool: ``True`` if the task was found and reset,
            ``False`` if no task with that id exists.
        """
        task = self.get_task(task_id)
        if task:
            task.mark_incomplete()
            return True
        return False

    def remove_task(self, task_id: UUID) -> bool:
        """Remove a task from this pet's task list.

        Args:
            task_id (UUID): The id of the task to remove.

        Returns:
            bool: ``True`` if the task was found and removed,
            ``False`` if no task with that id exists.
        """
        for i, task in enumerate(self.tasks):
            if task.id == task_id:
                del self.tasks[i]
                return True
        return False

    @property
    def pending_tasks(self) -> List[Task]:
        """All incomplete tasks assigned to this pet.

        Returns:
            List[Task]: Tasks where ``complete`` is ``False``.
        """
        return [t for t in self.tasks if not t.complete]

    def __str__(self) -> str:
        """Return a human-readable summary of this pet and its task counts.

        Returns:
            str: A string in the form ``"Buddy (age 3) — 2/3 tasks pending"``.
        """
        total = len(self.tasks)
        pending = len(self.pending_tasks)
        return f"{self.name} (age {self.age}) — {pending}/{total} tasks pending"


@dataclass
class Owner:
    """An owner who manages one or more pets.

    Attributes:
        id (UUID): Auto-generated unique identifier.
        name (str): The owner's display name.
        pets (List[Pet]): All pets registered under this owner.
    """

    id: UUID = field(default_factory=uuid4)
    name: str = ""
    pets: List[Pet] = field(default_factory=list)

    def add_pet(self, pet: Pet) -> None:
        """Register a new pet under this owner.

        Args:
            pet (Pet): The pet to add.
        """
        self.pets.append(pet)

    def get_pet(self, pet_id: UUID) -> Optional[Pet]:
        """Look up a pet by its unique identifier.

        Args:
            pet_id (UUID): The id of the pet to find.

        Returns:
            Pet: The matching pet, or ``None`` if not found.
        """
        return next((p for p in self.pets if p.id == pet_id), None)

    def find_pet_by_name(self, pet_name: str) -> Optional[Pet]:
        """Find the first pet whose name matches exactly (case-sensitive).

        Args:
            pet_name (str): The name to search for.

        Returns:
            Pet: The first matching pet, or ``None`` if not found.
        """
        return next((p for p in self.pets if p.name == pet_name), None)

    def remove_pet(self, pet_id: UUID) -> bool:
        """Remove a pet from this owner's pet list.

        Args:
            pet_id (UUID): The id of the pet to remove.

        Returns:
            bool: ``True`` if the pet was found and removed,
            ``False`` if no pet with that id exists.
        """
        for i, pet in enumerate(self.pets):
            if pet.id == pet_id:
                del self.pets[i]
                return True
        return False

    def all_tasks(self) -> List[Task]:
        """Aggregate every task across all of this owner's pets.

        Returns:
            List[Task]: A flat list of all tasks, in pet-registration order.
        """
        return [task for pet in self.pets for task in pet.tasks]

    def all_pending_tasks(self) -> List[Task]:
        """Aggregate every incomplete task across all of this owner's pets.

        Returns:
            List[Task]: A flat list of tasks where ``complete`` is ``False``.
        """
        return [task for pet in self.pets for task in pet.pending_tasks]

    def __str__(self) -> str:
        """Return a human-readable summary of this owner.

        Returns:
            str: A string in the form ``"Owner: Alex — 2 pet(s)"``.
        """
        return f"Owner: {self.name} — {len(self.pets)} pet(s)"


@dataclass
class Schedule:
    """A single-day ordered view of tasks.

    Tasks are stored as added and sorted on demand via ``generate()``.

    Attributes:
        day (date): The calendar date this schedule applies to.
        task_list (List[Task]): Tasks included in this schedule.
    """

    day: date
    task_list: List[Task] = field(default_factory=list)

    def add_task(self, task: Task) -> None:
        """Add a task to this day's schedule.

        Args:
            task (Task): The task to include.
        """
        self.task_list.append(task)

    def remove_task(self, task_id: UUID) -> bool:
        """Remove a task from this schedule by id.

        Args:
            task_id (UUID): The id of the task to remove.

        Returns:
            bool: ``True`` if the task was found and removed,
            ``False`` if no task with that id exists.
        """
        for i, task in enumerate(self.task_list):
            if task.id == task_id:
                del self.task_list[i]
                return True
        return False

    def generate(self) -> List[Task]:
        """Return tasks sorted for execution order.

        Sort key (in order of precedence):

        1. Incomplete tasks before complete tasks.
        2. Higher priority before lower priority.
        3. Shorter duration before longer duration (tie-breaker).

        Returns:
            List[Task]: A new sorted list; ``task_list`` is not modified.
        """
        return sorted(
            self.task_list,
            key=lambda t: (
                t.complete,
                -t.priority,
                _FREQ_ORDER.get(t.frequency, 4),
                t.duration,
                t.scheduled_time if t.scheduled_time is not None else time.max,
            ),
        )

    def clear(self) -> None:
        """Remove all tasks from this schedule."""
        self.task_list.clear()

    def time_conflicts(self) -> List[Tuple[Task, Task]]:
        """Return pairs of tasks whose scheduled time windows overlap.

        Only tasks with a ``scheduled_time`` set are compared. Two tasks
        conflict when their half-open intervals overlap:
        ``[start, start + duration)`` intersects ``[other_start, other_start + other_duration)``,
        which is true when ``a_start < b_end and b_start < a_end``.

        Tasks belonging to the same pet and tasks belonging to different
        pets are compared equally — the owner's time is the shared resource.

        Returns:
            List[Tuple[Task, Task]]: Each tuple holds the two conflicting
            Task objects in schedule order. Empty list if no overlaps exist
            or no tasks have a ``scheduled_time`` set.
        """
        timed = [t for t in self.task_list if t.scheduled_time is not None]
        pairs: List[Tuple[Task, Task]] = []
        _anchor = date.min  # fixed dummy date so datetime arithmetic works
        for i in range(len(timed)):
            for j in range(i + 1, len(timed)):
                a, b = timed[i], timed[j]
                a_start = datetime.combine(_anchor, a.scheduled_time)
                a_end   = a_start + timedelta(hours=a.duration)
                b_start = datetime.combine(_anchor, b.scheduled_time)
                b_end   = b_start + timedelta(hours=b.duration)
                if a_start < b_end and b_start < a_end:
                    pairs.append((a, b))
        return pairs

    def conflicts(self, daily_cap_hours: float = 24.0) -> List[str]:
        """Return a list of conflict descriptions for this schedule.

        Checks performed:

        1. Total task duration exceeds *daily_cap_hours*.
        2. Duplicate task names (case-insensitive) in the schedule.

        Args:
            daily_cap_hours (float): Maximum hours available in the day.
                Defaults to ``24.0``.

        Returns:
            List[str]: Human-readable conflict messages; empty if none.
        """
        issues: List[str] = []
        total = sum(t.duration for t in self.task_list)
        if total > daily_cap_hours:
            issues.append(
                f"Total duration {total:.1f}h exceeds daily cap of {daily_cap_hours:.1f}h"
            )
        seen: set = set()
        for task in self.task_list:
            key = task.name.lower()
            if key in seen:
                issues.append(f"Duplicate task name in schedule: '{task.name}'")
            seen.add(key)
        for task_a, task_b in self.time_conflicts():
            a_t = task_a.scheduled_time.strftime("%H:%M")
            b_t = task_b.scheduled_time.strftime("%H:%M")
            issues.append(
                f"Time overlap: '{task_a.name}' (@{a_t}, {task_a.duration}h) "
                f"conflicts with '{task_b.name}' (@{b_t}, {task_b.duration}h)"
            )
        return issues

    def __str__(self) -> str:
        """Return a formatted multi-line view of today's schedule.

        Returns:
            str: A header line followed by one indented line per task,
            sorted by ``generate()``.
        """
        lines = [f"Schedule for {self.day} ({len(self.task_list)} tasks):"]
        for task in self.generate():
            lines.append(f"  {task}")
        return "\n".join(lines)


@dataclass
class Scheduler:
    """The 'Brain' of PawPal++.

    Sits on top of an ``Owner`` and provides unified, cross-pet task
    retrieval, filtering, and schedule generation. All state lives in
    the owner's pets; ``Scheduler`` adds no state of its own.

    Attributes:
        owner (Owner): The owner whose pets and tasks are managed.
    """

    owner: Owner

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    def get_all_tasks(self) -> List[Task]:
        """Return every task across all of the owner's pets.

        Returns:
            List[Task]: Flat list of all tasks in pet-registration order.
        """
        return self.owner.all_tasks()

    def get_pending_tasks(self) -> List[Task]:
        """Return all incomplete tasks across all of the owner's pets.

        Returns:
            List[Task]: Flat list of tasks where ``complete`` is ``False``.
        """
        return self.owner.all_pending_tasks()

    def get_tasks_for_pet(self, pet_id: UUID) -> List[Task]:
        """Return all tasks belonging to a specific pet.

        Args:
            pet_id (UUID): The id of the pet to look up.

        Returns:
            List[Task]: The pet's task list, or an empty list if the pet
            is not found.
        """
        pet = self.owner.get_pet(pet_id)
        return pet.tasks if pet else []

    # ------------------------------------------------------------------
    # Filtering / organisation
    # ------------------------------------------------------------------

    def get_tasks_by_priority(self, min_priority: int = 1) -> List[Task]:
        """Return pending tasks at or above a minimum priority, sorted highest first.

        Args:
            min_priority (int): Inclusive lower bound on priority (1–5).
                Defaults to ``1`` (returns all pending tasks).

        Returns:
            List[Task]: Pending tasks with ``priority >= min_priority``,
            sorted in descending priority order.
        """
        return sorted(
            [t for t in self.get_pending_tasks() if t.priority >= min_priority],
            key=lambda t: -t.priority,
        )

    def get_tasks_by_frequency(self, frequency: str) -> List[Task]:
        """Return all tasks (complete or not) matching a frequency string.

        Args:
            frequency (str): One of ``"daily"``, ``"weekly"``,
                ``"monthly"``, or ``"as_needed"``.

        Returns:
            List[Task]: All tasks whose ``frequency`` equals the argument.
        """
        return [t for t in self.get_all_tasks() if t.frequency == frequency]

    def filter_tasks(
        self,
        pet_id: Optional[UUID] = None,
        status: Optional[bool] = None,
    ) -> List[Task]:
        """Return tasks filtered by pet and/or completion status.

        Both filters are optional and can be combined. Passing neither
        argument returns every task across all pets.

        Args:
            pet_id (UUID, optional): When provided, only tasks belonging
                to this pet are considered.
            status (bool, optional): ``True`` → complete tasks only;
                ``False`` → incomplete tasks only; ``None`` → both.

        Returns:
            List[Task]: Tasks matching all supplied filters.
        """
        tasks = self.get_tasks_for_pet(pet_id) if pet_id is not None else self.get_all_tasks()
        if status is not None:
            tasks = [t for t in tasks if t.complete == status]
        return tasks

    # ------------------------------------------------------------------
    # Schedule building
    # ------------------------------------------------------------------

    def build_schedule(self, day: date) -> Schedule:
        """Build a :class:`Schedule` for *day* from all pending tasks.

        Frequency rules applied when deciding whether a pending task is
        included in the schedule:

        - ``"daily"``    -- always included.
        - ``"weekly"``   -- included when ``day.weekday()`` matches
          today's weekday (so the same day-of-week each week).
        - ``"monthly"``  -- included when ``day.day`` matches today's
          day-of-month.
        - ``"as_needed"``-- always included (the task itself signals
          it is needed by being incomplete).

        Args:
            day (date): The calendar date to build the schedule for.

        Returns:
            Schedule: A new ``Schedule`` object populated with the
            relevant pending tasks.
        """
        schedule = Schedule(day=day)
        for task in self.get_pending_tasks():
            if task.frequency == "daily":
                schedule.add_task(task)
            elif task.frequency == "weekly" and day.weekday() == task.start_date.weekday():
                schedule.add_task(task)
            elif task.frequency == "monthly" and day.day == task.start_date.day:
                schedule.add_task(task)
            elif task.frequency == "as_needed":
                schedule.add_task(task)
        return schedule

    def reset_recurring_tasks(self, day: date) -> int:
        """Reset completed recurring tasks that are due again on *day*.

        Only tasks whose recurrence period has rolled over are touched:

        - ``"daily"``    -- always reset (fires every new day).
        - ``"weekly"``   -- reset when *day*'s weekday matches the task's
          ``start_date`` weekday.
        - ``"monthly"``  -- reset when *day*'s day-of-month matches the
          task's ``start_date`` day-of-month.
        - ``"as_needed"``-- never auto-reset; the owner marks manually.

        Args:
            day (date): The date representing the current scheduling day.

        Returns:
            int: Number of tasks reset to incomplete.
        """
        count = 0
        for task in self.get_all_tasks():
            if not task.complete:
                continue
            if task.frequency == "daily":
                task.mark_incomplete()
                count += 1
            elif task.frequency == "weekly" and day.weekday() == task.start_date.weekday():
                task.mark_incomplete()
                count += 1
            elif task.frequency == "monthly" and day.day == task.start_date.day:
                task.mark_incomplete()
                count += 1
        return count

    def detect_conflicts(self, day: date, daily_cap_hours: float = 24.0) -> List[str]:
        """Detect scheduling conflicts for *day*.

        Builds the schedule for *day* and delegates to
        :meth:`Schedule.conflicts` for conflict analysis. Includes both
        duration-cap/duplicate checks and any time-window overlaps.

        Args:
            day (date): The date to inspect.
            daily_cap_hours (float): Hour budget for the day (default 24.0).

        Returns:
            List[str]: Human-readable conflict messages; empty if none.
        """
        return self.build_schedule(day).conflicts(daily_cap_hours)

    def find_time_conflicts(self, day: date) -> List[Tuple[Task, Task]]:
        """Return all time-overlapping task pairs scheduled for *day*.

        Builds the schedule for *day* and delegates to
        :meth:`Schedule.time_conflicts`. Useful when callers need the
        actual Task objects rather than formatted strings.

        Tasks from the same pet and from different pets are compared; the
        owner's time is the shared resource being checked.

        Args:
            day (date): The date to inspect.

        Returns:
            List[Tuple[Task, Task]]: Pairs of overlapping tasks. Empty
            list if no conflicts exist or no tasks have a
            ``scheduled_time`` set.
        """
        return self.build_schedule(day).time_conflicts()

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    def summary(self) -> str:
        """Build a multi-line status overview for all pets and their tasks.

        Returns:
            str: A formatted string listing each pet, its tasks with
            status, and a total pending/total count at the end.
        """
        lines = [f"=== PawPal++ Summary for {self.owner.name} ==="]
        for pet in self.owner.pets:
            lines.append(f"  {pet}")
            for task in pet.tasks:
                lines.append(f"    {task}")
        total = len(self.get_all_tasks())
        pending = len(self.get_pending_tasks())
        lines.append(f"Total: {pending} pending / {total} tasks")
        return "\n".join(lines)
