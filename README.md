# Mumzworld AI Gift Finder

**Track A — AI Engineering Intern**

A natural-language gift recommender for Mumzworld shoppers. A parent types something like *"thoughtful gift for a friend with a 6-month-old, under 200 AED"* and the system returns a curated shortlist with reasoning, in English or Arabic. It combines a filter-first RAG pipeline (FAISS semantic search over a product catalog, hard-filtered by parsed price and age constraints) with a deterministic bilingual answer builder that guarantees no hallucinated product details — the LLM only contributes a warm intro sentence, all product facts come directly from the catalog.

**Loom walkthrough (3 min):** 
https://www.loom.com/share/8bcb9a62cd3d4c069866bf8aff780516

## Quick Start

```bash
pip install -r requirements.txt
```

Add your key to `.env`:

```env
OPENROUTER_API_KEY=your_key_here
```

Run the server:

```bash
uvicorn app:app --reload
```

Open the UI: [http://127.0.0.1:8000](http://127.0.0.1:8000)

Or call the API directly:

```bash
curl "http://127.0.0.1:8000/recommend?query=gift+for+6+month+baby+under+200+AED&lang=en"
```

---

## How It Works

```
User query
    │
    ▼
rag.py — parse price + age filters → semantic search (FAISS) → top-k products
    │
    ▼
llm.py — LLM writes a warm intro sentence → structured answer built from real data
    │
    ▼
JSON response { answer, sources, number_of_products }
```

### Why RAG before LLM?

The LLM never invents product details. All product names, prices, categories, and age ranges come directly from the catalog — the LLM only contributes a short intro sentence. This eliminates hallucination of product facts.

### Why FAISS + filter, not pure semantic search?

Pure semantic search would return products outside the user's budget or wrong age group. We hard-filter by price and age first, then run semantic search only within that candidate pool. This keeps results grounded in the actual query constraints.

### Why OpenRouter free models?

This is a demo project. Free models on OpenRouter are sufficient for generating a single intro sentence. The structured answer is built deterministically from data, so model quality has minimal impact on correctness.

---

## Project Structure

| File | Purpose |
|---|---|
| `app.py` | FastAPI routes — GET and POST `/recommend` |
| `rag.py` | Price/age parsing, FAISS semantic search, relevance filtering |
| `llm.py` | LLM intro generation + deterministic bilingual answer builder |
| `data/products.json` | Product catalog (generated demo data) |
| `generate_data.py` | Script that generated the catalog |
| `EVALS.md` | Evaluation cases and expected outputs |
| `TRADEOFFS.md` | Architecture decisions and known limitations |

---

## API

### `GET /recommend` or `POST /recommend`

| Parameter | Type | Description |
|---|---|---|
| `query` | string | Natural language query in English or Arabic |
| `lang` | string | `en` (default) or `ar` |

**Response:**

```json
{
  "answer": "Here are some great options...\n• Toys Product (Toys — 0-6 months) — 150 AED\n  ...",
  "number_of_products": 3,
  "sources": [
    { "id": 19, "name": "Toys Product", "category": "Toys", "age": "0-6 months", "price": 150 }
  ]
}
```

**When nothing matches:**

```json
{
  "answer": "We couldn't find any products within your budget and age range.",
  "number_of_products": 0,
  "sources": []
}
```

---

## Known Failure Modes

See `TRADEOFFS.md` for full details. Short version:

- Budget detection relies on regex — unusual phrasing like "spend around 200" may not parse
- Product names in the demo catalog are synthetic ("Toys Product 45") — a real catalog would have real names
- Free LLM tier can be slow (5–20s) or temporarily rate-limited
- Arabic queries must contain at least one recognized keyword — fully novel phrasing may be rejected

---

## Tooling

**Models and harnesses used:**

- **OpenRouter + `meta-llama/llama-3.1-8b-instruct`** — used for the LLM intro sentence only. Free tier. Chosen because the structured answer is built deterministically, so model quality has low impact on correctness.
- **Kiro (AI coding assistant in VS Code)** — used throughout for pair-coding: scaffolding the FastAPI routes, iterating on the regex price/age parser, writing the FAISS candidate-pool pattern, and drafting documentation. Worked well for code generation and refactoring.
- **`all-MiniLM-L6-v2` via `sentence-transformers`** — embedding model for FAISS. Not an LLM — a local model, no API call needed.

**How they were used:**

- Kiro was used in pair-coding mode: I described the intent, reviewed every suggestion, and overruled it several times — notably on the LLM architecture (Kiro initially generated a full LLM-generation approach; I stepped in to redesign it as a deterministic builder after seeing the first hallucinated price).
- The Arabic keyword filter and the relevance threshold for off-topic rejection were both written by hand after the agent's initial version silently returned irrelevant products on off-topic queries.
- Prompt iteration for the LLM intro was done manually — the agent-generated prompt produced mixed-language output on Arabic queries until the explicit `"لا تكتب أي كلمة بالإنجليزية"` instruction was added.

**What worked:** Code scaffolding, boilerplate, documentation drafting, regex pattern generation.

**What didn't:** The agent's first architecture used the LLM to generate the full answer including product details — this hallucinated prices and ages. I replaced it with the deterministic builder. The agent also initially skipped the filter-first pattern and ran semantic search on the full catalog, which ignored budget constraints.

**Key prompt that shaped the output** (in `llm.py`):
```
أجب باللغة العربية الفصحى فقط. لا تكتب أي كلمة بالإنجليزية.
اكتب جملة ترحيبية قصيرة وودية تمهيداً لقائمة الهدايا المقترحة (جملة واحدة فقط، بدون قائمة).
```
This was the version that finally produced clean Arabic-only intros without English leakage.
