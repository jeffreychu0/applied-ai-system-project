"""
main.py
=======
PawPal++ demo: one owner, two pets, three tasks each.
Exercises every feature in pawpal_system.py.
"""
from datetime import date, time
from pawpal_system import Task, Pet, Owner, Scheduler

# ---------------------------------------------------------------------------
# Setup: owner, pets, tasks
# ---------------------------------------------------------------------------
owner = Owner(name="Jordan")

mochi = Pet(name="Mochi", age=2)   # dog
miso  = Pet(name="Miso",  age=5)   # cat
owner.add_pet(mochi)
owner.add_pet(miso)

# Mochi's three tasks -- mix of frequencies, priorities, and scheduled times
walk = Task(
    name="Morning Walk",
    description="30-minute walk around the block",
    duration=0.5, priority=5, frequency="daily",
    scheduled_time=time(8, 0),
)
pill = Task(
    name="Heartworm Pill",
    description="Monthly heartworm prevention tablet",
    duration=0.1, priority=4, frequency="monthly",
    scheduled_time=time(8, 10),   # intentionally overlaps walk to demo conflict detection
)
training = Task(
    name="Obedience Training",
    description="Weekly 60-minute training session at the park",
    duration=1.0, priority=3, frequency="weekly",
    scheduled_time=time(10, 0),
)
mochi.assign_task(walk)
mochi.assign_task(pill)
mochi.assign_task(training)

# Miso's three tasks
feeding = Task(
    name="Feeding",
    description="Half a can of wet food, morning and evening",
    duration=0.1, priority=5, frequency="daily",
    scheduled_time=time(7, 30),
)
brush = Task(
    name="Brush Coat",
    description="Weekly brushing to reduce shedding",
    duration=0.25, priority=2, frequency="weekly",
)
vet = Task(
    name="Vet Checkup",
    description="Annual wellness exam -- book when overdue",
    duration=1.5, priority=4, frequency="as_needed",
)
miso.assign_task(feeding)
miso.assign_task(brush)
miso.assign_task(vet)

scheduler = Scheduler(owner=owner)
today = date.today()

# ---------------------------------------------------------------------------
# 1. Today's schedule  (build_schedule + generate)
# ---------------------------------------------------------------------------
print("=" * 56)
print("  Today's Schedule")
print("=" * 56)
schedule = scheduler.build_schedule(today)
for task in schedule.generate():
    t_str = f" @{task.scheduled_time.strftime('%H:%M')}" if task.scheduled_time else ""
    status = "done" if task.complete else "pending"
    print(f"  [{status}] {task.name} (p{task.priority}, {task.duration}h, {task.frequency}{t_str})")

# ---------------------------------------------------------------------------
# 2. Conflict detection  (detect_conflicts)
# ---------------------------------------------------------------------------
print("\n" + "=" * 56)
print("  Conflict Detection")
print("=" * 56)
conflicts = scheduler.detect_conflicts(today)
if conflicts:
    for msg in conflicts:
        print(f"  ! {msg}")
else:
    print("  No conflicts.")

# ---------------------------------------------------------------------------
# 3. Time-conflict pairs  (find_time_conflicts)
# ---------------------------------------------------------------------------
print("\n" + "=" * 56)
print("  Time-Conflict Pairs")
print("=" * 56)
pairs = scheduler.find_time_conflicts(today)
if pairs:
    for a, b in pairs:
        at = a.scheduled_time.strftime("%H:%M")
        bt = b.scheduled_time.strftime("%H:%M")
        print(f"  '{a.name}' (@{at}, {a.duration}h)  x  '{b.name}' (@{bt}, {b.duration}h)")
else:
    print("  None.")

# ---------------------------------------------------------------------------
# 4. Filter tasks  (filter_tasks)
# ---------------------------------------------------------------------------
print("\n" + "=" * 56)
print("  Mochi's Tasks")
print("=" * 56)
for t in scheduler.filter_tasks(pet_id=mochi.id):
    print(f"  {t}")

print("\n" + "=" * 56)
print("  All Pending Tasks")
print("=" * 56)
for t in scheduler.filter_tasks(status=False):
    print(f"  {t}")

# ---------------------------------------------------------------------------
# 5. Complete a task  (complete_task auto-spawns next occurrence)
# ---------------------------------------------------------------------------
print("\n" + "=" * 56)
print("  Complete 'Morning Walk'  ->  next occurrence auto-created")
print("=" * 56)
mochi.complete_task(walk.id)
print(f"  Completed:  {walk}")
print(f"  Spawned:    {mochi.tasks[-1]}")
print(f"  Mochi now has {len(mochi.tasks)} tasks ({len(mochi.pending_tasks)} pending)")

# ---------------------------------------------------------------------------
# 6. Reset recurring tasks  (reset_recurring_tasks)
# ---------------------------------------------------------------------------
print("\n" + "=" * 56)
print("  Reset Recurring Tasks")
print("=" * 56)
n = scheduler.reset_recurring_tasks(today)
print(f"  {n} recurring task(s) reset to pending.")
print(f"  Morning Walk status after reset: {'done' if walk.complete else 'pending'}")

# ---------------------------------------------------------------------------
# 7. Full summary  (summary)
# ---------------------------------------------------------------------------
print("\n" + "=" * 56)
print("  Summary")
print("=" * 56)
print(scheduler.summary())
