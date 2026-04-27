# -*- coding: utf-8 -*-
import os
from dotenv import load_dotenv
load_dotenv()

import streamlit as st
from datetime import date, time
from pawpal_system import Owner, Pet, Task, Scheduler

try:
    from openai import OpenAI as _OpenAI
    from agent import run_agent_turn
    _AGENT_AVAILABLE = True
except ImportError:
    _AGENT_AVAILABLE = False

st.set_page_config(page_title="PawPal+", page_icon="🐾", layout="wide")
st.title("🐾 PawPal+")

# ------------------------------------------------------------------
# Session-state vault
# ------------------------------------------------------------------
if "owner" not in st.session_state:
    st.session_state.owner = Owner(name="Jordan")

if "pets_initialized" not in st.session_state:
    default_pet = Pet(name="Mochi", age=2)
    st.session_state.owner.add_pet(default_pet)
    st.session_state.pets_initialized = True

owner: Owner = st.session_state.owner

# ------------------------------------------------------------------
# Sidebar — owner info & pet management
# ------------------------------------------------------------------
with st.sidebar:
    st.header("Owner")
    new_name = st.text_input("Owner name", value=owner.name)
    if new_name != owner.name:
        owner.name = new_name

    st.divider()
    st.subheader("Pets")

    # Add pet
    with st.expander("Add a pet"):
        new_pet_name = st.text_input("Name", key="new_pet_name")
        new_pet_age  = st.number_input("Age (years)", min_value=0, max_value=30,
                                        value=1, key="new_pet_age")
        if st.button("Add pet"):
            if new_pet_name.strip():
                owner.add_pet(Pet(name=new_pet_name.strip(), age=int(new_pet_age)))
                st.success(f"Added {new_pet_name}!")
                st.rerun()
            else:
                st.warning("Enter a pet name first.")

    # List pets with remove option
    for p in list(owner.pets):
        col_a, col_b = st.columns([3, 1])
        with col_a:
            pending = len(p.pending_tasks)
            total   = len(p.tasks)
            st.markdown(f"**{p.name}** (age {p.age}) — {pending}/{total} pending")
        with col_b:
            if len(owner.pets) > 1 and st.button("✕", key=f"rmpet_{p.id}"):
                owner.remove_pet(p.id)
                st.rerun()

    st.divider()
    st.subheader("Active pet")
    pet_names = [p.name for p in owner.pets]
    # Keep selection valid after removes
    if "active_pet_name" not in st.session_state or \
            st.session_state.active_pet_name not in pet_names:
        st.session_state.active_pet_name = pet_names[0]

    chosen_name = st.selectbox("Select pet", pet_names,
                                index=pet_names.index(st.session_state.active_pet_name))
    st.session_state.active_pet_name = chosen_name
    pet: Pet = owner.find_pet_by_name(chosen_name)

# ------------------------------------------------------------------
# Tabs
# ------------------------------------------------------------------
tab_tasks, tab_schedule, tab_filter, tab_conflicts, tab_ai = st.tabs(
    ["📋 Tasks", "📅 Schedule", "🔍 Filter & Sort", "⚠️ Conflicts", "🤖 AI Assistant"]
)

# ══════════════════════════════════════════════════════════════════
# TAB 1 — Tasks
# ══════════════════════════════════════════════════════════════════
with tab_tasks:
    st.subheader(f"{pet.name}'s Tasks")

    # ---- Add task form ----
    with st.expander("Add a task", expanded=True):
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            task_title = st.text_input("Title", value="Morning walk", key="t_title")
        with c2:
            duration = st.number_input("Duration (hours)", min_value=0.1,
                                        max_value=24.0, value=0.5, step=0.1, key="t_dur")
        with c3:
            priority = st.selectbox("Priority (1=low, 5=high)", [1, 2, 3, 4, 5],
                                     index=4, key="t_pri")
        with c4:
            frequency = st.selectbox("Frequency",
                                      ["daily", "weekly", "monthly", "as_needed"],
                                      key="t_freq")

        desc = st.text_input("Description (optional)", key="t_desc")

        use_time = st.checkbox("Set a scheduled time")
        sched_time = None
        if use_time:
            tc1, tc2 = st.columns(2)
            with tc1:
                s_hour = st.number_input("Hour (0-23)", min_value=0, max_value=23,
                                          value=8, key="t_hour")
            with tc2:
                s_min = st.number_input("Minute", min_value=0, max_value=59,
                                         value=0, step=5, key="t_min")
            sched_time = time(int(s_hour), int(s_min))

        if st.button("Add task", key="btn_add_task"):
            pet.assign_task(Task(
                name=task_title,
                description=desc,
                duration=float(duration),
                priority=priority,
                frequency=frequency,
                scheduled_time=sched_time,
            ))
            st.success(f"Added '{task_title}' to {pet.name}'s tasks.")
            st.rerun()

    # ---- Task list ----
    if pet.tasks:
        show_done = st.checkbox("Show completed tasks", value=True)
        visible = pet.tasks if show_done else pet.pending_tasks

        if not visible:
            st.info("No matching tasks.")
        else:
            for task in visible:
                col1, col2, col3, col4 = st.columns([5, 1, 1, 1])
                with col1:
                    status = "✅" if task.complete else "🔲"
                    time_str = (f" @{task.scheduled_time.strftime('%H:%M')}"
                                if task.scheduled_time else "")
                    desc_str = f" — *{task.description}*" if task.description else ""
                    st.markdown(
                        f"{status} **{task.name}**{desc_str}  \n"
                        f"`{task.duration}h` · priority `{task.priority}` · "
                        f"`{task.frequency}`{time_str}"
                    )
                with col2:
                    label = "Undo" if task.complete else "Done"
                    if st.button(label, key=f"toggle_{task.id}"):
                        if task.complete:
                            pet.uncomplete_task(task.id)
                        else:
                            pet.complete_task(task.id)
                        st.rerun()
                with col3:
                    if st.button("Remove", key=f"remove_{task.id}"):
                        pet.remove_task(task.id)
                        st.rerun()
                with col4:
                    # Show next-occurrence badge
                    if not task.complete and task.frequency in ("daily", "weekly"):
                        nxt = task.next_occurrence()
                        if nxt:
                            st.caption(f"next: {nxt.start_date}")
    else:
        st.info("No tasks yet. Add one above.")

# ══════════════════════════════════════════════════════════════════
# TAB 2 — Schedule
# ══════════════════════════════════════════════════════════════════
with tab_schedule:
    st.subheader("Generate Schedule")

    sched_date = st.date_input("Schedule date", value=date.today())
    daily_cap  = st.slider("Daily hour budget", min_value=1.0, max_value=24.0,
                            value=8.0, step=0.5)

    col_gen, col_reset = st.columns(2)
    with col_gen:
        gen_clicked = st.button("Generate schedule", key="btn_gen")
    with col_reset:
        reset_clicked = st.button("Reset recurring tasks for today", key="btn_reset")

    if reset_clicked:
        scheduler = Scheduler(owner=owner)
        n = scheduler.reset_recurring_tasks(date.today())
        st.success(f"Reset {n} recurring task(s) to pending.")
        st.rerun()

    if gen_clicked:
        scheduler = Scheduler(owner=owner)
        schedule  = scheduler.build_schedule(sched_date)
        ordered   = schedule.generate()

        if ordered:
            total_h = sum(t.duration for t in ordered)
            st.success(
                f"Schedule for **{sched_date}** — {len(ordered)} task(s) "
                f"/ **{total_h:.1f}h** total"
            )
            for task in ordered:
                status   = "✅" if task.complete else "🔲"
                time_str = (f" @{task.scheduled_time.strftime('%H:%M')}"
                            if task.scheduled_time else "")
                pet_name = next(
                    (p.name for p in owner.pets if any(t.id == task.id for t in p.tasks)),
                    "?"
                )
                st.markdown(
                    f"{status} **{task.name}** &nbsp; "
                    f"*{pet_name}* &nbsp; "
                    f"`priority {task.priority}` &nbsp; "
                    f"`{task.duration}h` &nbsp; "
                    f"`{task.frequency}`{time_str}"
                )
        else:
            st.info("No pending tasks match this date's schedule.")

    st.divider()
    st.subheader("Scheduler Summary")
    if st.button("Show summary"):
        scheduler = Scheduler(owner=owner)
        st.text(scheduler.summary())

# ══════════════════════════════════════════════════════════════════
# TAB 3 — Filter & Sort
# ══════════════════════════════════════════════════════════════════
with tab_filter:
    st.subheader("Filter & Sort Tasks")

    scheduler = Scheduler(owner=owner)

    fc1, fc2, fc3 = st.columns(3)
    with fc1:
        filter_pet = st.selectbox(
            "Pet",
            ["All pets"] + [p.name for p in owner.pets],
            key="f_pet"
        )
    with fc2:
        filter_status = st.selectbox(
            "Status",
            ["All", "Pending only", "Completed only"],
            key="f_status"
        )
    with fc3:
        filter_freq = st.selectbox(
            "Frequency",
            ["All", "daily", "weekly", "monthly", "as_needed"],
            key="f_freq"
        )

    min_pri = st.slider("Minimum priority", min_value=1, max_value=5, value=1, key="f_pri")

    # Build filtered list
    pet_id = None
    if filter_pet != "All pets":
        found = owner.find_pet_by_name(filter_pet)
        pet_id = found.id if found else None

    status_map = {"All": None, "Pending only": False, "Completed only": True}
    status_val = status_map[filter_status]

    tasks = scheduler.filter_tasks(pet_id=pet_id, status=status_val)

    if filter_freq != "All":
        tasks = [t for t in tasks if t.frequency == filter_freq]

    tasks = [t for t in tasks if t.priority >= min_pri]

    # Sort highest priority first
    tasks = sorted(tasks, key=lambda t: (-t.priority, t.duration))

    st.markdown(f"**{len(tasks)} task(s) matched**")
    if tasks:
        for task in tasks:
            status  = "✅" if task.complete else "🔲"
            time_str = (f" @{task.scheduled_time.strftime('%H:%M')}"
                        if task.scheduled_time else "")
            # Find which pet owns this task
            owner_pet_name = next(
                (p.name for p in owner.pets if any(t.id == task.id for t in p.tasks)),
                "?"
            )
            st.markdown(
                f"{status} **{task.name}** *({owner_pet_name})*  \n"
                f"`{task.duration}h` · priority `{task.priority}` · "
                f"`{task.frequency}`{time_str}"
            )
    else:
        st.info("No tasks match the selected filters.")

# ══════════════════════════════════════════════════════════════════
# TAB 4 — Conflicts
# ══════════════════════════════════════════════════════════════════
with tab_conflicts:
    st.subheader("Conflict Detection")

    conf_date = st.date_input("Check date", value=date.today(), key="conf_date")
    cap_hours  = st.slider("Daily hour cap", min_value=1.0, max_value=24.0,
                            value=8.0, step=0.5, key="conf_cap")

    if st.button("Detect conflicts"):
        scheduler = Scheduler(owner=owner)

        # General conflicts (duration cap + duplicates + time overlaps)
        issues = scheduler.detect_conflicts(conf_date, daily_cap_hours=cap_hours)

        if issues:
            st.error(f"**{len(issues)} conflict(s) found:**")
            for issue in issues:
                st.warning(issue)
        else:
            st.success("No conflicts detected for this day.")

        # Time-window overlap details
        st.divider()
        st.markdown("**Time-window overlaps**")
        time_pairs = scheduler.find_time_conflicts(conf_date)
        if time_pairs:
            for task_a, task_b in time_pairs:
                a_t = task_a.scheduled_time.strftime("%H:%M")
                b_t = task_b.scheduled_time.strftime("%H:%M")
                st.warning(
                    f"⏰ **{task_a.name}** starts at {a_t} ({task_a.duration}h) overlaps with "
                    f"**{task_b.name}** starting at {b_t} ({task_b.duration}h)"
                )
        else:
            st.info("No time-window overlaps (tasks need a scheduled time to be checked).")

# ══════════════════════════════════════════════════════════════════
# TAB 5 — AI Assistant
# ══════════════════════════════════════════════════════════════════
with tab_ai:
    st.subheader("PawPal+ AI Assistant")
    st.caption(
        "Ask questions or give commands in plain English — the assistant "
        "can read and modify your pets and tasks."
    )

    if not _AGENT_AVAILABLE:
        st.error(
            "The `openai` package is not installed. "
            "Run `pip install openai` and restart the app."
        )
    else:
        api_key = os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            st.warning(
                "Set the `OPENAI_API_KEY` environment variable and restart "
                "the app to enable the AI Assistant."
            )
        else:
            # Chat state
            if "chat_api_history" not in st.session_state:
                st.session_state.chat_api_history = []
            if "chat_display" not in st.session_state:
                st.session_state.chat_display = []

            # Render existing messages
            for msg in st.session_state.chat_display:
                with st.chat_message(msg["role"]):
                    st.markdown(msg["content"])

            # Accept new input
            if prompt := st.chat_input("Ask something or give a command…"):
                with st.chat_message("user"):
                    st.markdown(prompt)
                st.session_state.chat_display.append(
                    {"role": "user", "content": prompt}
                )

                client = _OpenAI(api_key=api_key)
                with st.chat_message("assistant"):
                    with st.spinner(""):
                        reply, new_history = run_agent_turn(
                            prompt,
                            st.session_state.chat_api_history,
                            owner,
                            client,
                        )
                    st.markdown(reply)

                st.session_state.chat_api_history = new_history
                st.session_state.chat_display.append(
                    {"role": "assistant", "content": reply}
                )
                # Rerun so tabs 1-4 re-render with any owner mutations from tool calls.
                st.rerun()

            # Clear button — only shown when there is history
            if st.session_state.chat_display:
                if st.button("Clear chat", key="clear_chat"):
                    st.session_state.chat_api_history = []
                    st.session_state.chat_display = []
                    st.rerun()
