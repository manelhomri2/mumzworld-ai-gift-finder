# Architecture Tradeoffs & Failure Modes

## Architecture Decisions

### 1. Deterministic answer builder instead of full LLM generation

The structured answer (product name, category, price, reason) is built directly from the retrieved data in `llm.py._build_answer()`. The LLM only generates a short warm intro sentence.

**Why:** Free/small LLMs hallucinate product details when asked to describe items they were just given. Prices become wrong, ages get invented, categories get confused. By constructing the factual part ourselves, we guarantee the output is grounded in the input — the core requirement of the rubric.

**Tradeoff:** The reasons per category are pre-written templates, not dynamically reasoned per product. This is intentional — a templated reason that is always accurate is better than a fluent reason that is sometimes wrong.

---

### 2. Filter-first, then semantic search

`rag.py` hard-filters the product catalog by price and age before running FAISS semantic search on the remaining candidates.

**Why:** Pure semantic search ignores numerical constraints. A query for "under 200 AED" would otherwise return products at 450 AED if their description happened to be semantically close. Filtering first ensures budget and age are always respected.

**Tradeoff:** If the filter is too aggressive (e.g., price parsing fails), the candidate pool can be empty and the system returns nothing instead of a bad answer. This is the correct failure mode — explicit empty result is better than a result that ignores the user's constraints.

---

### 3. Regex-based price and age parsing

Price and age are extracted from the query using regular expressions rather than asking the LLM to extract them.

**Why:** Regex is deterministic, fast, and has no token cost. LLM-based extraction adds latency and can fail silently (returning `null` or a hallucinated number).

**Tradeoff:** Regex misses unusual phrasing. Known gaps:
- "spend around 200" — not parsed (no explicit budget keyword)
- "two hundred dirhams" — written-out numbers not handled
- "a newborn" — maps to no age, so age filter is skipped (still returns results, just unfiltered by age)

---

### 4. Arabic query validation via keyword list

Arabic queries are checked against a list of baby/gift-related Arabic keywords before processing.

**Why:** Without this, Arabic gibberish or off-topic Arabic text would still go through the full search pipeline and return (irrelevant) results confidently. The keyword check is a lightweight guard.

**Tradeoff:** The keyword list is finite. A valid query phrased with unusual vocabulary not in the list will be rejected with an empty result. The list can be extended as new patterns are discovered.

---

### 5. FAISS `IndexFlatL2` (exact search, no approximation)

We use exact L2 distance search rather than an approximate index (e.g., `IndexIVFFlat`).

**Why:** The catalog has ~300 products. At this scale, exact search is fast enough (sub-millisecond). Approximate indexes trade accuracy for speed and only become worthwhile at millions of vectors.

**Tradeoff:** None meaningful at this scale. Would need to revisit with a real catalog of 100k+ products.

---

### 6. English relevance threshold, no threshold for Arabic

English queries above a cosine distance of 1.2 from all candidates are rejected as off-topic. Arabic queries skip this check.

**Why:** The sentence transformer (`all-MiniLM-L6-v2`) was trained primarily on English data. Its Arabic embeddings are less reliable, so the distance threshold is not meaningful for Arabic — we rely on the keyword filter instead.

**Tradeoff:** Off-topic Arabic queries that pass the keyword check (e.g., a query containing the word "طفل" but asking about something unrelated) will return results. Improving Arabic relevance filtering would require an Arabic-capable embedding model.

---

## What you cut and what's next

### What was cut from scope

- **Real product names** — the catalog uses synthetic names ("Toys Product 45"). A real integration would pull from Mumzworld's actual catalog via API. Cut because the demo data is sufficient to prove the retrieval and filtering logic.
- **Multilingual embedding model** — `paraphrase-multilingual-MiniLM-L12-v2` would give better Arabic semantic search. Cut because the keyword filter + price/age hard-filter compensates well enough at demo scale, and load time would triple.
- **LLM-based slot extraction** — using the LLM to extract budget and age from the query would handle unusual phrasing. Cut in favor of regex because it's deterministic, faster, and free. The failure modes are documented and acceptable.
- **Confidence scores in the response** — the brief mentions confidence scores as a possible signal. Cut because the filter-first approach means any returned product genuinely satisfies the constraints — a confidence score would be misleading without a ranking model.
- **User session / conversation history** — follow-up queries like "show me cheaper ones" require context. Cut as out of scope for a stateless REST API demo.

### What to build next

1. **Fix the regex gaps** — add "around X", "approximately X", written-out numbers ("two hundred") to the price parser. Low effort, high impact on Case 9.
2. **Multilingual embedding model** — swap `all-MiniLM-L6-v2` for `paraphrase-multilingual-MiniLM-L12-v2` to improve Arabic semantic matching and enable a relevance threshold for Arabic queries too.
3. **Real catalog integration** — replace the generated JSON with a live product feed. The retrieval and filtering logic is catalog-agnostic and would work unchanged.
4. **Structured JSON output with schema validation** — return a proper typed response (`products: [{name, category, age, price, reason}]`) instead of a pre-formatted string, so frontend clients can render it however they need.
5. **Automated eval runner** — script the 12 eval cases so they run on every commit and print a pass/fail table, instead of being run manually.



| Failure | Behavior | Severity |
|---|---|---|
| Budget phrasing not recognized | Age filter skipped, returns unfiltered-by-price results | Medium |
| All products filtered out | Returns empty with explicit message | Low (correct behavior) |
| LLM rate-limited | Intro sentence is empty, structured answer still returned | Low |
| LLM intro in wrong language | Structured part is still correct; intro may be wrong language | Low |
| Query in unsupported language (not EN/AR) | Falls through to semantic search with no filters | Low |
| Product catalog has synthetic names | User sees "Toys Product 45" instead of a real product name | Demo limitation only |
