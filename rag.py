import re
import json
import faiss
import numpy as np

from sentence_transformers import SentenceTransformer


# all-MiniLM-L6-v2: lightweight English-first model, fast enough for a demo catalog.
# A multilingual model (e.g. paraphrase-multilingual-MiniLM-L12-v2) would improve
# Arabic semantic matching but is ~3x slower to load.
model = SentenceTransformer("all-MiniLM-L6-v2")

products = json.load(open("data/products.json"))

# Build one text string per product for embedding.
# We combine name + description so the vector captures both the category label
# and the descriptive context (age suitability, use case).
texts = []
for p in products:
    texts.append(p["name"] + " " + p["description"])

vectors = model.encode(texts)
dimension = vectors.shape[1]

# IndexFlatL2: exact nearest-neighbour search using L2 (Euclidean) distance.
# Fine for ~300 products. Would need IndexIVFFlat or HNSW at 100k+ products.
index = faiss.IndexFlatL2(dimension)
index.add(np.array(vectors))


# Maps age bucket labels to (min_months, max_months) ranges.
# Used to filter products to the age group implied by the query.
AGE_BUCKETS = {
    "0-6 months":  (0, 6),
    "6-12 months": (6, 12),
    "1-3 years":   (12, 36),
    "3-5 years":   (36, 60),
}

# Arabic keywords that signal a baby/gift-related query.
# If an Arabic query contains none of these, it's likely off-topic and we return [].
# This is a lightweight guard against confident answers on out-of-scope Arabic input.
ARABIC_RELEVANT_KEYWORDS = {
    "هدية", "هدايا", "اشتري", "أشتري", "أريد", "ابحث", "اقتراح", "اقترح",
    "أحتاج", "احتاج", "أفضل", "منتج", "منتجات", "سعر", "ميزانية",
    "طفل", "طفلة", "طفلي", "رضيع", "مولود", "بيبي", "ابني", "ابنتي",
    "بنتي", "ولدي", "أطفال",
    "أشهر", "شهر", "سنة", "سنتين", "سنوات", "عمر",
    "ألعاب", "لعبة", "ملابس", "ملبس", "تعليم", "تغذية", "رعاية", "سلامة",
    "درهم", "دراهم",
}


def _clean_name(name: str) -> str:
    """Strip trailing catalog ID numbers: 'Clothing Product 109' → 'Clothing Product'."""
    return re.sub(r"\s+\d+$", "", name).strip()


def _is_relevant_arabic(query: str) -> bool:
    """Return True only if the Arabic query contains at least one baby/gift keyword."""
    words = re.findall(r"[\u0600-\u06FF]+", query)
    return any(w in ARABIC_RELEVANT_KEYWORDS for w in words)


def _parse_max_price(query: str) -> float | None:
    """
    Extract a budget ceiling from the query using regex.

    Handles patterns like:
      - "under 200 AED", "below 150 dhs", "budget of 300"
      - "200 AED or less", "max 250 dirhams"
      - Arabic: "أقل من 200 درهم", "بأقل من 150 درهم"

    Returns None if no budget is found — the caller skips price filtering in that case.
    """
    query_lower = query.lower()
    patterns = [
        r"(?:under|below|less\s+than|not\s+more\s+than|no\s+more\s+than|max(?:imum)?|within|up\s+to|budget\s+(?:of|is|:)?|cost(?:s|ing)?\s+(?:of|around|about)?|price(?:d)?\s+(?:at|of|around|about)?)\s*(?:aed|dhs?|dirhams?)?\s*(\d+(?:\.\d+)?)\s*(?:aed|dhs?|dirhams?)?",
        r"(\d+(?:\.\d+)?)\s*(?:aed|dhs?|dirhams?)\s*(?:or\s+less|max(?:imum)?|budget|only)?",
        r"(\d+(?:\.\d+)?)\s*(?:budget|max(?:imum)?)",
        r"(?:أقل\s*من|بأقل\s*من|لا\s*يتجاوز|تحت|بحد\s*أقصى|ميزانية)\s*(\d+(?:\.\d+)?)\s*(?:درهم|دره|د\.إ)?",
        r"(\d+(?:\.\d+)?)\s*(?:درهم|دره|د\.إ)",
    ]
    for pattern in patterns:
        match = re.search(pattern, query_lower)
        if match:
            return float(match.group(1))
    return None


def _parse_age_months(query: str) -> int | None:
    """
    Extract the child's age from the query and convert it to months.

    Handles:
      - English: "6 months", "2 years old", "1-year-old"
      - Arabic: "6 أشهر", "سنتين", "3 سنوات"

    Returns None if no age is found — the caller skips age filtering in that case.
    """
    query_lower = query.lower()

    match = re.search(r"(\d+)\s*-?\s*months?\s*(?:old|baby|infant)?", query_lower)
    if match:
        return int(match.group(1))

    match = re.search(r"(\d+)\s*-?\s*years?\s*(?:old)?", query_lower)
    if match:
        return int(match.group(1)) * 12

    match = re.search(r"(\d+)\s*(?:أشهر|شهر|أشهراً|شهراً)", query)
    if match:
        return int(match.group(1))

    match = re.search(r"(\d+)\s*(?:سنة|سنوات|عام|أعوام)", query)
    if match:
        return int(match.group(1)) * 12

    # Written-out Arabic age words that can't be captured with a digit pattern
    arabic_year_words = {
        "سنتين": 24, "عامين": 24,
        "ثلاث سنوات": 36, "ثلاثة أعوام": 36,
        "أربع سنوات": 48, "خمس سنوات": 60,
    }
    for word, months in arabic_year_words.items():
        if word in query:
            return months

    return None


def _suitable_buckets(age_months: int) -> list[str]:
    """
    Return all age buckets that overlap with the given age in months.

    A 6-month-old baby falls in both "0-6 months" and "6-12 months",
    so we return both rather than restricting to one.
    Falls back to all buckets if nothing matches (shouldn't happen in practice).
    """
    suitable = []
    for bucket, (low, high) in AGE_BUCKETS.items():
        if low <= age_months <= high:
            suitable.append(bucket)
    return suitable if suitable else list(AGE_BUCKETS.keys())


def search(query: str, k: int = 5) -> list[dict]:
    """
    Return the top-k products most relevant to the query.

    Steps:
      1. Detect language and reject off-topic Arabic queries early.
      2. Parse budget and age from the query text.
      3. Hard-filter the catalog by price and age to build a candidate pool.
      4. Run FAISS semantic search within the candidate pool only.
      5. For English, reject results that exceed the relevance distance threshold.
      6. Return cleaned product dicts (numeric IDs stripped from names).

    Returns [] when no products match — never invents results.
    """
    is_arabic = bool(re.search(r"[\u0600-\u06FF]", query))

    # Reject off-topic / gibberish Arabic before doing any work
    if is_arabic and not _is_relevant_arabic(query):
        return []

    max_price  = _parse_max_price(query)
    age_months = _parse_age_months(query)

    # Build filtered candidate pool — only products that satisfy price + age constraints
    candidates = []
    for i, p in enumerate(products):
        if max_price is not None and p["price"] > max_price:
            continue
        if age_months is not None:
            if p["age"] not in _suitable_buckets(age_months):
                continue
        candidates.append((i, p))

    # If filtering wiped everything out, return empty rather than a wrong result
    if not candidates:
        return []

    # Build a temporary FAISS index over just the candidate vectors
    candidate_vectors = np.array([vectors[i] for i, _ in candidates])
    tmp_index = faiss.IndexFlatL2(dimension)
    tmp_index.add(candidate_vectors)

    q = model.encode([query])
    k_actual = min(k, len(candidates))
    D, I = tmp_index.search(q, k_actual)

    # For English queries: if the closest result is still semantically far
    # (distance > 1.2), the query is off-topic — return nothing instead of
    # confidently answering with irrelevant products.
    # We skip this threshold for Arabic because the English-first embedding model
    # produces unreliable distances for Arabic text.
    RELEVANCE_THRESHOLD = 1.2
    if not is_arabic and (len(D[0]) == 0 or D[0][0] > RELEVANCE_THRESHOLD):
        return []

    result = []
    seen = set()
    for dist, idx in zip(D[0], I[0]):
        # Skip results that are too semantically distant (English only)
        if not is_arabic and dist > RELEVANCE_THRESHOLD:
            continue
        product = candidates[idx][1]
        # Deduplicate by product ID (FAISS can return the same item twice in edge cases)
        if product["id"] not in seen:
            clean = dict(product)
            clean["name"] = _clean_name(product["name"])
            result.append(clean)
            seen.add(product["id"])

    return result
