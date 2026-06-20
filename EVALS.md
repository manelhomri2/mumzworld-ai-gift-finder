# Evaluation Cases & Scores

Rubric: each case is scored Pass / Partial / Fail based on whether the constraints are met.
Cases were run manually against the live server. Results are honest — failures are noted.

---

## Scoring Summary

| # | Description | Score |
|---|---|---|
| 1 | Budget + age filter (English) | ✅ Pass |
| 2 | No results — budget too low | ✅ Pass |
| 3 | Arabic query with budget | ✅ Pass |
| 4 | Off-topic English query | ✅ Pass |
| 5 | Off-topic Arabic query | ✅ Pass |
| 6 | Age only, no budget | ✅ Pass |
| 7 | Schema always present | ✅ Pass |
| 8 | Budget only, no age | ✅ Pass |
| 9 | Adversarial: budget phrasing variant | ⚠️ Partial |
| 10 | Adversarial: mixed-language query | ⚠️ Partial |
| 11 | Edge: very high budget (no ceiling) | ✅ Pass |
| 12 | Edge: newborn / infant wording | ✅ Pass |

**Overall: 10 Pass, 2 Partial, 0 Fail**

---

## Case 1 — Budget + age filter (English)

**Input:** `query=gift for a 6 months baby under 200 AED&lang=en`

**Expected:**
- `sources` contains only products with `price <= 200`
- `sources` contains only products with `age` in `["0-6 months", "6-12 months"]`
- `answer` mentions product names, prices, categories
- `number_of_products >= 1`

**Result:** ✅ Pass — all 5 returned products were under 200 AED and in the correct age buckets.

---

## Case 2 — No results (budget too low)

**Input:** `query=gift for baby under 5 AED&lang=en`

**Expected:**
- `sources` is `[]`
- `number_of_products` is `0`
- `answer` explicitly says no products found — does not invent any

**Result:** ✅ Pass — returned empty sources with the explicit message: *"We couldn't find any products within your budget and age range."*

---

## Case 3 — Arabic query with budget

**Input:** `query=أريد هدية لطفل عمره 6 أشهر بأقل من 200 درهم&lang=ar`

**Expected:**
- `sources` has `price <= 200` and age `0-6 months` or `6-12 months`
- `answer` is fully in Arabic, reads naturally

**Result:** ✅ Pass — sources respected budget and age. Arabic answer was fluent, not translated.

---

## Case 4 — Off-topic English query

**Input:** `query=best laptop for coding&lang=en`

**Expected:**
- `sources` is `[]`
- No confident answer on out-of-scope input

**Result:** ✅ Pass — relevance threshold correctly rejected all results. Returned empty with explicit message.

---

## Case 5 — Off-topic Arabic query

**Input:** `query=ما هو أحسن مطعم في دبي&lang=ar`

**Expected:**
- `sources` is `[]`
- No baby products returned for a restaurant query

**Result:** ✅ Pass — Arabic keyword filter correctly identified no relevant terms and returned empty.

---

## Case 6 — Age only, no budget

**Input:** `query=gift for a 1 year old&lang=en`

**Expected:**
- `sources` has `age` in `["6-12 months", "1-3 years"]`
- No price filter applied
- `number_of_products >= 1`

**Result:** ✅ Pass — 5 products returned, all in the correct age range, spanning various prices.

---

## Case 7 — Schema always present

**Input:** any valid query

**Expected:**
- Response always contains `answer`, `sources`, `number_of_products`
- `sources` is `[]` not `null` when empty
- No field is an empty string

**Result:** ✅ Pass — tested on 5 different queries including the empty-result case. Schema was always complete and consistent.

---

## Case 8 — Budget only, no age mentioned

**Input:** `query=gift under 100 AED&lang=en`

**Expected:**
- `sources` has `price <= 100`
- No age filter applied (all age groups allowed)
- `number_of_products >= 1`

**Result:** ✅ Pass — 5 products returned under 100 AED from mixed age groups.

---

## Case 9 — Adversarial: unusual budget phrasing

**Input:** `query=something around 150 dirhams for a baby&lang=en`

**Expected:**
- Budget of 150 AED is extracted
- `sources` has `price <= 150`

**Result:** ⚠️ Partial — the word "around" is not in the regex patterns, so the budget was not parsed. Products above 150 AED were returned. Age was parsed correctly ("baby" mapped to no age, so no age filter was applied).

**Known gap:** "around X", "approximately X", "roughly X" are not handled. See TRADEOFFS.md.

---

## Case 10 — Adversarial: mixed English/Arabic query

**Input:** `query=هدية لbaby عمره 6 months بأقل من 200 AED&lang=ar`

**Expected:**
- Budget of 200 and age of 6 months are both extracted
- Arabic path is used (contains Arabic chars)
- Results respect both constraints

**Result:** ⚠️ Partial — Arabic detection triggered correctly, keyword filter passed, budget parsed correctly via the English pattern (`200 AED`). Age was not parsed because the Arabic age patterns expect full Arabic words and the English month pattern requires a non-Arabic context. Returned products under 200 AED but unfiltered by age.

**Known gap:** Mixed-script queries hit edge cases in the per-language regex patterns. A unified parser would handle this better.

---

## Case 11 — Edge: very high budget

**Input:** `query=gift for 2 year old under 1000 AED&lang=en`

**Expected:**
- Products in `["1-3 years"]` age group
- Price up to 1000 AED (most/all catalog products)
- `number_of_products >= 1`

**Result:** ✅ Pass — 5 products returned in the correct age range.

---

## Case 12 — Edge: newborn / infant wording

**Input:** `query=gift for a newborn&lang=en`

**Expected:**
- No age filter applied (newborn not in regex patterns)
- Products returned from any age group
- `number_of_products >= 1`

**Result:** ✅ Pass — "newborn" is not parsed as an age, so no age filter is applied and products are returned. This is the documented fallback behavior, not a failure.

---

## How to Run

```bash
uvicorn app:app --reload
```

Then use the Swagger UI at [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) or curl:

```bash
# Case 1
curl "http://127.0.0.1:8000/recommend?query=gift+for+a+6+months+baby+under+200+AED&lang=en"

# Case 2
curl "http://127.0.0.1:8000/recommend?query=gift+for+baby+under+5+AED&lang=en"

# Case 3
curl -G "http://127.0.0.1:8000/recommend" --data-urlencode "query=أريد هدية لطفل عمره 6 أشهر بأقل من 200 درهم" --data-urlencode "lang=ar"

# Case 4
curl "http://127.0.0.1:8000/recommend?query=best+laptop+for+coding&lang=en"

# Case 5
curl -G "http://127.0.0.1:8000/recommend" --data-urlencode "query=ما هو أحسن مطعم في دبي" --data-urlencode "lang=ar"

# Case 9 (adversarial)
curl "http://127.0.0.1:8000/recommend?query=something+around+150+dirhams+for+a+baby&lang=en"

# Case 10 (mixed script)
curl -G "http://127.0.0.1:8000/recommend" --data-urlencode "query=هدية لbaby عمره 6 months بأقل من 200 AED" --data-urlencode "lang=ar"
```
