# TasteMatch — Claude Code Instructions

## 🎯 Project
Agentic menu analyzer. Given any restaurant or coffee shop (name / URL / address /
menu image), autonomously retrieves its menu and scores it against a personal taste profile.

Built by @1MansiS · github.com/1MansiS/tastematch

---

## 🐍 Python Environment

- Always run Python commands inside the `.venv` virtual environment
- Activate with `source .venv/bin/activate` before any `python`, `pytest`, or `pip` command
- When chaining shell commands, prefix with `source .venv/bin/activate &&`

---

## 🏗️ Architecture Rules (never break these)

- LLM layer is ALWAYS swappable via `llm/factory.py` — never import a provider directly in agent code
- All LLM outputs must be validated through Pydantic models in `models/`
- Agent retrieval must handle failures gracefully — always return a confidence score, never crash
- No LangChain or LangGraph in v1 — raw Python + Anthropic tool-use patterns only
- All I/O must be async — use `httpx`, not `requests`
- Use `Rich` for all terminal output — never use `print()`
- Type hints on every function signature
- Venue type detection lives in `agent/venue_detector.py` — matcher loads the
  correct profile section based on detected type; never hardcode venue assumptions
  in matcher or parser

---

## 🧪 Testing Rules

- Write unit tests for every new function or module before marking it done
- Tests live in `tests/` mirroring source structure:
  - `agent/retrieval.py` → `tests/test_retrieval.py`
  - `llm/factory.py` → `tests/test_llm_factory.py`
- Use `pytest` with `pytest-asyncio` for async tests
- Mock all external API calls — no real network calls in unit tests
- Every test file must cover at minimum:
  - Happy path
  - Failure / fallback path
  - Edge case (empty response, malformed input, unknown venue type)
- After writing any new code, ask: "Have I written tests for this?"
- Do not mark a feature complete until its tests pass

---

## 📝 README Rules

- After every meaningful code change, update `README.md` immediately
- Keep these sections current:
  - **Build Roadmap** — check off completed items
  - **Supported Input Types** — if a new input type is added
  - **Supported Providers** — if a new LLM provider is added
  - **Future Venue Types** — if scope discussion changes
  - **Project Structure** — if new files or folders are added
- README must always accurately describe the current state of the code

---

## 🔖 Commit Reminders

Remind me to consider a public commit after any of the following:

- A new module or file is working and tested
- A new input type is supported end-to-end
- A new LLM provider is integrated
- A new venue type is supported (detector + matcher + profile section)
- A retrieval strategy is added or improved
- A Pydantic model is finalized
- Tests are written and passing for a feature
- README is updated to reflect a new capability

**Use this format:**

```
📌 Commit checkpoint — resume signal

What's working  : [brief description]
Tests           : [passing / count]
README          : [updated / not needed]

Suggested message : "[type]: [short description]"
Suggested tag     : vX.X  (if version milestone)
```

**Commit message conventions:**
- `feat:`     new capability
- `fix:`      bug fix
- `refactor:` restructure without behavior change
- `test:`     tests added or updated
- `docs:`     README or documentation only
- `chore:`    config, deps, tooling

---

## 📦 Current Phase

**v0.1 — Core Pipeline**
- URL input → web_fetch → LLM parse → match verdict
- Food profile section only
- CLI output with Rich

**Next: v0.2 — Vision Support**
- Menu image / PDF → Vision OCR → parse

---

## 🔌 Provider Config (defaults)

```json
{
  "llm": {
    "provider": "ollama",
    "text_model": "llama3.1:8b",
    "vision_model": "llama3.2-vision:11b",
    "base_url": "http://localhost:11434"
  }
}
```

---

## 📁 Folder Structure (keep in sync with code)

```
tastematch/
├── CLAUDE.md
├── README.md
├── config.json
├── profile.json
├── requirements.txt
├── agent/
│   ├── router.py
│   ├── venue_detector.py
│   ├── retrieval.py
│   ├── parser.py
│   ├── matcher.py
│   └── verdict.py
├── llm/
│   ├── base.py
│   ├── anthropic.py
│   ├── gemini.py
│   ├── ollama.py
│   └── factory.py
├── tools/
│   ├── web_fetch.py
│   ├── pdf_extract.py
│   ├── vision_ocr.py
│   ├── places_lookup.py
│   └── search.py
├── models/
│   ├── profile.py
│   ├── menu.py
│   └── verdict.py
└── tests/
    ├── test_retrieval.py
    ├── test_parser.py
    ├── test_matcher.py
    ├── test_venue_detector.py
    └── test_llm_factory.py
```

---

## 🔭 Future Scope (design for, don't build yet)

Keep this in mind when making architectural decisions:
- `profile.json` sections must remain independently loadable per venue type
- The verdict output schema must remain stable
- No venue-type-specific logic should leak into `retrieval.py` or `parser.py`
- New venue types (beer, ice cream, etc.) must require zero agent code changes

---

## 🚫 Never Do

- Import a specific LLM provider outside of `llm/` directory
- Use `requests` — always use `httpx` async
- Use `print()` — always use `Rich` console
- Return raw LLM string output without Pydantic validation
- Hardcode venue type assumptions outside of `venue_detector.py`
- Mark a feature done without passing tests
- Let README drift from actual code state
- Add LangChain or LangGraph in v1
