# Module 4 Submission: PawPal+ (Module 2 Project)

PawPal+ is a pet care scheduling tool implemented in Python, designed as a Streamlit app (entrypoint in `app.py`).
It helps pet owners manage pets, tasks, and daily schedule generation with priority handling.

<a href="final_app.png" target="_blank"><img src='final_app.png' title='PawPal App' width='' alt='PawPal App' class='center-block' /></a>.

## ✅ Implemented features

### Core domain objects (`pawpal_system.py`)
- `Owner` with:
  - `id: UUID`, `name: str`, `pets: List[Pet]`
  - `add_pet(pet: Pet)`
  - `get_pet(pet_id: UUID) -> Optional[Pet]`
  - `find_pet_by_name(pet_name: str) -> Optional[Pet]`
- `Pet` with:
  - `id: UUID`, `name: str`, `age: int`, `tasks: List[Task]`
  - `assign_task(task: Task)`
  - `get_task(task_id: UUID) -> Optional[Task]`
  - `complete_task(task_id: UUID) -> bool`
  - `uncomplete_task(task_id: UUID) -> bool`
  - `remove_task(task_id: UUID) -> bool`
- `Task` with:
  - `id: UUID`, `name: str`, `description: str`, `duration: float`, `priority: int`, `complete: bool`
  - `mark_complete()` / `mark_incomplete()`
  - `update(...)`
- `Schedule` with:
  - `day: date`, `task_list: List[Task]`
  - `add_task(task: Task)`
  - `remove_task(task_id: UUID) -> bool`
  - `generate() -> List[Task]` (priority-based sorting)
  - `clear()`

### Task operations
- Add/remove tasks by UUID for deterministic behavior (no duplicate name ambiguity)
- Mark tasks complete/uncomplete
- Update task details (name, description, duration, priority)

### Schedule generation
- Sort by uncompleted tasks first, then highest priority, then shorter duration
- Provides a simple base plan for a given day

## 🗺️ System Architecture

```mermaid
flowchart TD
    USER([👤 User])

    subgraph UI ["🖥️ Streamlit Frontend — app.py"]
        MANUAL["Tasks / Schedule /\nFilter / Conflicts Tabs\n\nManual CRUD"]
        CHATUI["🤖 AI Assistant Tab\nChat Interface"]
    end

    subgraph AGENT ["🤖 AI Agent — agent.py"]
        LOOP["Agentic Loop\nrun_agent_turn()"]
        EXEC["Tool Executor\nexecute_tool()"]
    end

    LLM[("☁️ OpenAI API\ngpt-4o-mini\nFunction Calling")]

    subgraph DOMAIN ["📦 Domain Model — pawpal_system.py"]
        STATE[("🗄️ Session State\nOwner · Pets · Tasks")]
        SCHED["Scheduler\nbuild_schedule()"]
        CONFLICT["Conflict Detector\ndetect_conflicts()"]
    end

    subgraph OUT ["📤 Output"]
        VIEW["Schedule · Task List\nConflict Report"]
        REPLY["AI Reply &\nAction Confirmation"]
    end

    subgraph TEST ["🧪 Testing & Human Evaluation"]
        UT_DOM["test_pawpal.py\n47 Domain Unit Tests"]
        UT_AGENT["test_agent.py\nTool Executor Tests"]
        IT["Integration Tests\nLive API Calls"]
        HUMAN_EVAL(["👤 Human Evaluator\nManual Validation"])
    end

    USER -->|"form input"| MANUAL
    USER -->|"chat message"| CHATUI

    MANUAL -->|"CRUD operations"| STATE
    CHATUI -->|"message + history"| LOOP

    LOOP -->|"system prompt + context"| LLM
    LLM -->|"function calls"| EXEC
    EXEC <-->|"reads / writes"| STATE
    EXEC -->|"tool result string"| LLM
    LLM -->|"final text reply"| LOOP

    STATE --> SCHED --> VIEW
    STATE --> CONFLICT --> VIEW
    LOOP --> REPLY

    VIEW --> USER
    REPLY --> USER

    STATE -..->|"domain tests"| UT_DOM
    EXEC -..->|"tool tests"| UT_AGENT
    LLM -..->|"end-to-end tests"| IT

    UT_DOM & UT_AGENT & IT -..->|"pass / fail"| HUMAN_EVAL
    HUMAN_EVAL -..->|"feedback loop"| LOOP
```

### Component summary

| Component | File | Role |
|---|---|---|
| **Streamlit UI** | `app.py` | Input forms, tab views, chat interface |
| **Domain Model** | `pawpal_system.py` | Owner / Pet / Task state; Scheduler; Conflict Detector |
| **AI Agent** | `agent.py` | Agentic loop, system prompt builder, tool executor |
| **OpenAI API** | *(external)* | LLM reasoning + function calling (gpt-4o-mini) |
| **Domain Tests** | `tests/test_pawpal.py` | 47 unit tests covering core domain logic |
| **Agent Tests** | `tests/test_agent.py` | Tool executor unit tests + live integration tests |
| **Human Evaluator** | *(manual)* | Reviews AI replies and integration test results |

## 📁 Project structure
- `app.py` - Streamlit UI + interaction layer
- `agent.py` - AI assistant agent (tool definitions, agentic loop)
- `pawpal_system.py` - domain + scheduler logic
- `tests/test_pawpal.py` - domain unit tests
- `tests/test_agent.py` - agent unit + integration tests
- `.env.example` - environment variable template
- `reflection.md` - design reflection and notes
- `requirements.txt` - dependencies

## 🚀 Quickstart

1. Create venv and install:

```bash
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -r requirements.txt
```

2. Set up your API key:

```bash
cp .env.example .env   # then paste your OpenAI key into .env
```

3. Run app:

```bash
streamlit run app.py
```

## 🧪 Testing

Run domain + agent unit tests (no API key required):

```bash
pytest tests/
```

Run integration tests against the live OpenAI API:

```bash
pytest tests/test_agent.py -m integration
```

## 🛠️ Future enhancements
- UI forms for task editing and deletion
- persistence layer (JSON/SQLite)
- constraints like maximum time block, availability windows
- explanation text for why schedule order was chosen
- multi-pet combined day planning

