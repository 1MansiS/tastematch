# 🍽️ TasteMatch

![Status](https://img.shields.io/badge/status-active%20development-brightgreen)
![Python](https://img.shields.io/badge/python-3.11+-blue)
![License](https://img.shields.io/badge/license-MIT-green)

> *Give it any restaurant or café. It tells you how well it matches your personal taste profile.*

TasteMatch is an agentic menu analyzer that autonomously retrieves a venue's menu —
from any source, in any format — and scores it against your personal taste profile.

Designed for any venue type. v1.0 covers **restaurants** and **coffee shops**.

**Status**: 🚧 Active Development · **Author**: [@1MansiS](https://1mansis.github.io)

---

## 🎯 What It Does

```
Input:  Venue name / URL / address / menu image
           │
           ▼
        Detects venue type (restaurant, coffee shop, ...)
           │
           ▼
        Autonomously finds and fetches the menu
        (tries multiple strategies, recovers from failures)
           │
           ▼
        Parses items regardless of format
        (HTML, PDF, image, plain text)
           │
           ▼
        Matches against the relevant section of your taste profile
           │
           ▼
Output: Match score + item breakdown + confidence rating
```

### Example Output — Restaurant

```
🟢 TasteMatch: Strong match — Dishoom, London

✅  11 vegetarian options (of 28 total dishes)
🫘  High protein hits : Lentil Dahl, Paneer Tikka, House Black Daal
🌍  Cuisine match     : Indian ✅  Middle Eastern ✅
⚠️  Watch out         : 3 dishes contain eggs
💡  Best picks        : Mujaddara, Paneer Tikka, Chaat Papdi

📊  Confidence : High  (full menu from official website)
📍  Source     : dishoom.com/menus
```

### Example Output — Coffee Shop

```
🟢 TasteMatch: Good match — Monmouth Coffee, London

☕  Brew methods  : Pour over ✅  Espresso ✅  Filter ✅
🌱  Milk options  : Oat ✅  Almond ✅
🥐  Food menu     : Yes — pastries, sourdough toast
🏷️  Vibe          : Artisan ✅  Independent ✅
⚠️  Watch out     : Limited seating, cash only

📊  Confidence : Medium (menu from Google Maps listing)
📍  Source     : Google Maps
```

---

## 🏗️ Architecture

### Agent Design Philosophy

TasteMatch is built around one core insight:
**menus live everywhere, in every format, behind unpredictable barriers.**
A fixed pipeline breaks. An agent that decides, retries, and recovers doesn't.

```
┌──────────────────────────────────────────────────────────────────┐
│                         INPUT LAYER                              │
│                                                                  │
│   Name + City      URL           Address       Image / PDF       │
└───────────────────────────┬──────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────────┐
│                       INPUT ROUTER                               │
│   Classifies input type → routes to correct retrieval strategy   │
└───────────────────────────┬──────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────────┐
│                   VENUE TYPE DETECTOR                            │
│                                                                  │
│   Infers type from name, content, or Google Places category      │
│   restaurant | coffee_shop | (beer_bar | ice_cream | ... later)  │
│   → selects the matching section of your taste profile           │
└───────────────────────────┬──────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────────┐
│                MENU RETRIEVAL AGENT  ← 🤖 Core agent loop        │
│                                                                  │
│  Strategy 1: Direct URL fetch → parse HTML                       │
│      ↓ fails?                                                    │
│  Strategy 2: Google Places → find website → find menu page       │
│      ↓ fails / partial?                                          │
│  Strategy 3: Tavily search → "[venue] menu site:yelp.com"        │
│      ↓ only image/PDF found?                                     │
│  Strategy 4: Vision OCR → extract text from image/PDF           │
│      ↓ still low confidence?                                     │
│  Strategy 5: Flag uncertainty → return low-confidence verdict    │
│                                                                  │
│  At each step: agent DECIDES whether result is good enough       │
│  to proceed or whether to try the next strategy.                 │
└───────────────────────────┬──────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────────┐
│                       MENU PARSER                                │
│   LLM extracts structured items from raw content:                │
│   { name, description, category, tags, ingredients }             │
└───────────────────────────┬──────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────────┐
│                     PROFILE MATCHER                              │
│                                                                  │
│   Loads the relevant profile section for detected venue type:    │
│   restaurant  → profile.food                                     │
│   coffee_shop → profile.coffee                                   │
│   Matches items, flags warnings, scores the venue                │
└───────────────────────────┬──────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────────┐
│                     VERDICT GENERATOR                            │
│                                                                  │
│   Produces: match score, best picks, warnings, confidence level  │
│   Confidence reflects source quality + menu completeness         │
│   Agent flags uncertainty — never hallucinates menu items        │
└──────────────────────────────────────────────────────────────────┘
```

---

## 🔌 Swappable LLM Design

TasteMatch is provider-agnostic. Configure your preferred LLM in `config.json`.
Swap providers without changing a single line of agent code.

**1. Set your provider in `config.json`:**

```json
{
  "llm": {
    "provider": "groq",
    "text_model": "llama-3.1-8b-instant",
    "vision_model": "llama-3.2-11b-vision-preview"
  }
}
```

**2. Add your API key to `.env`** (copy from `.env.example`):

```bash
cp .env.example .env
# then edit .env and fill in the key for your chosen provider
```

```
# .env
GROQ_API_KEY=gsk_...        # if provider = groq
GEMINI_API_KEY=AIza...      # if provider = gemini
```

Only the key for your active provider needs to be set. The file is gitignored — never commit it.

### Supported Providers

| Provider | Text Model | Vision Model | Cost | Key needed |
|----------|-----------|--------------|------|------------|
| `groq` | llama-3.1-8b-instant | llama-3.2-11b-vision-preview | Free tier | `GROQ_API_KEY` |
| `gemini` | gemini-1.5-flash | gemini-1.5-flash | Free tier | `GEMINI_API_KEY` |
| `ollama` | llama3.1:8b | llama3.2-vision:11b | Free | none (local) |
| `anthropic` | claude-sonnet-4-6 | claude-sonnet-4-6 | ~$0.02/scan | `ANTHROPIC_API_KEY` |

> **For free cloud**: `groq` or `gemini` — no credit card required
> **For local/offline**: `ollama` — no key needed
> **For best quality**: `anthropic`

### Provider Abstraction

```
tastematch/
└── llm/
    ├── base.py       ← Abstract LLMProvider interface
    ├── anthropic.py  ← Claude implementation
    ├── gemini.py     ← Gemini implementation
    ├── ollama.py     ← Ollama implementation
    └── factory.py    ← Reads config, instantiates correct provider
```

All providers expose the same two methods:
```python
await provider.complete(prompt: str) -> str
await provider.vision(prompt: str, image: bytes) -> str
```

Agent code never imports a specific provider — only the factory.

---

## 👤 Taste Profile

A portable, versionable JSON file — yours to own and share.
Each venue type gets its own section. The agent loads only the relevant
section per scan. Adding future venue types requires zero agent code changes.

```json
{
  "profile_name": "Mansi",

  "food": {
    "diet_type": "vegetarian",
    "must_have": [],
    "nice_to_have": ["high protein", "middle eastern", "mediterranean"],
    "loved_ingredients": ["lentils", "halloumi", "chickpeas", "paneer", "falafel"],
    "avoid_ingredients": ["eggs", "gelatin", "rennet"],
    "avoid_vibes": ["heavy cream", "butter-heavy"],
    "allergens": [],
    "intolerances": []
  },

  "coffee": {
    "interested_in": ["artisan", "single origin", "pour over", "flat white"],
    "milk_preference": "oat",
    "wants_food_menu": true,
    "food_preferences": ["baked goods", "pastries", "sourdough"],
    "avoid": ["chains", "pod coffee", "flavored syrups"]
  }

  // future venue types slot in here — no agent changes required
  // "beer": { ... }
  // "ice_cream": { ... }
  // "wine": { ... }
}
```

### No Dietary Restriction Required — Profile Is Fully General

```json
{
  "profile_name": "Jake",
  "food": {
    "diet_type": "none",
    "must_have": ["turkey"],
    "loved_ingredients": ["smoked meats", "bbq"],
    "allergens": ["gluten"]
  }
}
```

```json
{
  "profile_name": "Sarah",
  "food": {
    "diet_type": "gluten-free",
    "loved_ingredients": ["rice noodles", "tofu", "miso"],
    "allergens": ["gluten", "tree nuts"],
    "intolerances": ["lactose"]
  }
}
```

---

## 📥 Supported Input Types

| Input | Example | How it's handled |
|-------|---------|-----------------|
| Name + city | `"Dishoom, London"` | Google Places → website → menu |
| Direct URL | `"https://dishoom.com/menus"` | web_fetch → parse |
| Address | `"7 Boundary St, London"` | Google Places → website → menu |
| Menu image | `menu.jpg` | Vision OCR → extract |
| Menu PDF | `menu.pdf` | pdfplumber → extract, Vision fallback |
| Raw text | pasted menu text | Direct LLM parse |

---

## 🛠️ Tech Stack

```
Python 3.11+

# Agent orchestration
Pure Python + Anthropic tool-use patterns  ← v1 (no framework)
LangGraph                                  ← v2

# LLM (swappable)
anthropic · google-generativeai · ollama

# Menu retrieval
httpx · beautifulsoup4 · pdfplumber

# Place lookup
googlemaps · tavily-python

# Validation & output
pydantic · rich
```

> No LangChain in v1 — raw Python first. Understanding the agent loop
> before abstracting it produces better code and better resume signal.

---

## 📁 Project Structure

```
tastematch/
│
├── README.md
├── CLAUDE.md                      ← Claude Code session instructions
├── config.json                    ← LLM provider + API keys
├── profile.json                   ← Your personal taste profile
├── requirements.txt
│
├── agent/
│   ├── router.py                  ← Classifies input type
│   ├── venue_detector.py          ← restaurant vs coffee_shop vs ...
│   ├── retrieval.py               ← 🤖 Core agent loop (multi-strategy)
│   ├── parser.py                  ← Raw content → structured items
│   ├── matcher.py                 ← Items × profile section → score
│   └── verdict.py                 ← Final output + confidence
│
├── llm/
│   ├── base.py                    ← Abstract LLMProvider interface
│   ├── anthropic.py
│   ├── gemini.py
│   ├── ollama.py
│   └── factory.py                 ← Instantiates correct provider
│
├── tools/
│   ├── web_fetch.py               ← Async HTML scraping
│   ├── pdf_extract.py             ← PDF → text
│   ├── vision_ocr.py              ← Image → text via vision model
│   ├── places_lookup.py           ← Google Places API
│   └── search.py                  ← Tavily fallback search
│
├── models/
│   ├── profile.py                 ← Pydantic: taste profile schema
│   ├── menu.py                    ← Pydantic: parsed menu schema
│   └── verdict.py                 ← Pydantic: output schema
│
└── tests/
    ├── test_retrieval.py
    ├── test_parser.py
    ├── test_matcher.py
    ├── test_venue_detector.py
    └── test_llm_factory.py
```

---

## 🚀 Build Roadmap

### v0.1 — Core Pipeline ✅
- [x] URL input → web_fetch → LLM parse → match verdict
- [x] Food profile section, basic matching
- [x] CLI output with Rich formatting
- [x] Multi-strategy retrieval with fallbacks (json-ld → Next.js RSC → __NEXT_DATA__ → trafilatura → Playwright → BeautifulSoup)
- [x] Confidence scoring based on source quality
- [x] Venue type detection (restaurant vs coffee shop)
- [x] Coffee profile section + coffee-aware parser and matcher

### v0.2 — Vision Support
- [ ] Menu image → Vision OCR → parse
- [ ] PDF menu via pdfplumber + Vision fallback

### v0.3 — Name / Address Input
- [ ] Venue name / address → auto-find menu via Google Places + Tavily search

### v0.4 — Profile Polish
- [ ] Full profile generalization (any diet, any preference)
- [ ] Allergen and intolerance warnings
- [ ] Ingredient-level loved/avoided matching

### v1.0 — OSS Release
- [ ] All providers swappable (Anthropic / Gemini / Ollama)
- [ ] Example profiles (vegetarian, gluten-free, no restrictions, coffee-only)
- [ ] Full README + CONTRIBUTING.md
- [ ] GitHub Actions CI
- [ ] Project page live at 1mansis.github.io/projects/tastematch

---

### 🔭 Future Venue Types (v2.0+ — community driven)
> Profile schema and agent loop are already designed to support these.
> Adding a new venue type = new profile section + venue detector rule only.

- Beer bars & bottle shops (`profile.beer`)
- Ice cream & dessert shops (`profile.ice_cream`)
- Bakeries (`profile.bakery`)
- Wine bars (`profile.wine`)
- Any venue with a menu

---

## 🔑 API Keys

You only need a key for the provider you're using.

| Provider | Where to get it | Free tier | Credit card needed |
|----------|----------------|-----------|-------------------|
| Groq | console.groq.com | ~14,400 req/day | No |
| Gemini | aistudio.google.com | 1,500 req/day | No |
| Anthropic | console.anthropic.com | ~$0.02/scan | Yes |
| Ollama | local — no key needed | Unlimited | No |

**Never put keys in `config.json`** — use `.env` only (it's gitignored).

Other services used in later versions:

| Service | Purpose | Free Tier |
|---------|---------|-----------|
| Google Cloud | Places API (v0.3+) | $200/mo credit |
| Tavily | Fallback search (v0.3+) | 1,000 req/mo |

---

## 💻 Hardware

| Setup | Minimum | Recommended |
|-------|---------|-------------|
| Cloud API (Anthropic/Gemini) | Any machine | Any machine |
| Local via Ollama | 8GB RAM | 16GB RAM |
| Vision models locally | 12GB RAM | 16GB RAM (Apple Silicon ideal) |

> Apple Silicon M-series Macs are particularly well-suited — unified memory
> means the full RAM pool is available to the model, unlike x86 machines
> where GPU VRAM is the bottleneck.

---

## 🤝 Contributing

The modular design means contributions are naturally scoped:
- New LLM provider → add `llm/yourprovider.py`
- New input type → add `tools/your_source.py`
- New venue type → add profile section + venue detector rule
- New output format → add formatter to `verdict.py`

None of these touch the core agent loop. See `CONTRIBUTING.md` for details.

---

*Built by [@1MansiS](https://1mansis.github.io)*
