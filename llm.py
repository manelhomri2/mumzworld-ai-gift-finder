import os

from dotenv import load_dotenv
from openai import APIConnectionError, APIStatusError, APITimeoutError, OpenAI, RateLimitError


load_dotenv()


client=OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY"),
)



CATEGORY_AR = {
    "Baby Care":  "منتج عناية بالطفل",
    "Clothing":   "قطعة ملابس",
    "Toys":       "لعبة",
    "Learning":   "منتج تعليمي",
    "Feeding":    "منتج تغذية",
    "Health":     "منتج صحي",
    "Safety":     "منتج سلامة",
}

AGE_AR = {
    "0-6 months":  "من 0 إلى 6 أشهر",
    "6-12 months": "من 6 إلى 12 شهراً",
    "1-3 years":   "من سنة إلى 3 سنوات",
    "3-5 years":   "من 3 إلى 5 سنوات",
}

REASON_AR = {
    "Baby Care":  "منتج عناية يومية عالي الجودة، يساعد على الحفاظ على صحة وراحة طفلك.",
    "Clothing":   "قطعة ملابس مريحة وعملية، تمنح طفلك الدفء والأناقة في آنٍ واحد.",
    "Toys":       "لعبة ممتعة تحفّز حواس طفلك وتدعم نموّه في هذه المرحلة العمرية.",
    "Learning":   "أداة تعليمية رائعة تنمّي مهارات طفلك وتشجّعه على الاستكشاف.",
    "Feeding":    "منتج تغذية موثوق يجعل أوقات الطعام أسهل وأكثر متعةً للطفل والأم.",
    "Health":     "منتج صحي ضروري يساعد على متابعة صحة طفلك بشكل يومي.",
    "Safety":     "منتج سلامة ضروري يمنحك راحة البال ويحمي طفلك أثناء اللعب والحركة.",
}

REASON_EN = {
    "Baby Care":  "A high-quality daily care essential that keeps your baby healthy, clean, and comfortable.",
    "Clothing":   "A comfortable, practical clothing piece that keeps your baby warm and stylish.",
    "Toys":       "A fun toy that stimulates your baby's senses and supports development at this age.",
    "Learning":   "A great learning tool that nurtures your baby's curiosity and growing skills.",
    "Feeding":    "A reliable feeding product that makes mealtimes easier and more enjoyable for mom and baby.",
    "Health":     "An essential health product for monitoring and caring for your baby day to day.",
    "Safety":     "A must-have safety product that gives you peace of mind while your baby explores and plays.",
}


def _build_answer(products: list[dict], lang: str) -> str:
    """Build a polished answer directly from product data — no LLM needed for reasons."""
    if not products:
        if lang == "ar":
            return "لم نجد منتجات تناسب ميزانيتك ومتطلبات العمر. جرّب رفع الميزانية قليلاً!"
        return "We couldn't find any products within your budget and age range. Try increasing your budget a little!"

    header = "🎁 توصيات الهدايا\n" if lang == "ar" else "🎁 Gift Recommendations\n"
    lines = [header]

    for p in products:
        name     = p.get("name", "")
        category = p.get("category", "")
        age      = p.get("age", "")
        price    = p.get("price", "N/A")

        if lang == "ar":
            ar_name   = CATEGORY_AR.get(category, name)
            ar_age    = AGE_AR.get(age, age)
            ar_reason = REASON_AR.get(category, "منتج رائع مناسب لهذه المرحلة العمرية.")
            lines.append(f"• {ar_name} ({category} — {ar_age}) — {price} درهم")
            lines.append(f"  {ar_reason}\n")
        else:
            reason = REASON_EN.get(category, "A great product perfectly suited for this age range.")
            lines.append(f"• {name} ({category} — {age}) — {price} AED")
            lines.append(f"  {reason}\n")

    return "\n".join(lines)


def _fallback_answer(products, lang="en"):
    return _build_answer(products, lang)


def generate_answer(user, products, lang="en"):
    # If no products matched, skip the LLM entirely — calling it here would
    # produce a hallucinated intro celebrating products that don't exist.
    if not products:
        return _build_answer(products, lang)

    # For small/free models that struggle with consistent Arabic output,
    # we build the structured part ourselves and only ask the LLM for
    # a short warm intro sentence.
    # We tell the LLM exactly how many products were found so it cannot
    # misread numbers in the query (e.g. "5 AED") as age or product count.
    count = len(products)
    if lang == "ar":
        language_instruction = "أجب باللغة العربية الفصحى فقط. لا تكتب أي كلمة بالإنجليزية."
        intro_instruction = f"اكتب جملة ترحيبية قصيرة وودية تمهيداً لقائمة تضم {count} منتج مقترح (جملة واحدة فقط، بدون قائمة)."
    else:
        language_instruction = "Respond ONLY in English. Do not write any Arabic."
        intro_instruction = f"Write one short, warm, friendly opening sentence introducing the {count} gift recommendation(s) below (one sentence only, no list, no product details)."

    prompt = f"""You are a warm baby gift advisor at Mumzworld.

{language_instruction}

{intro_instruction}

User request: {user}
"""

    try:
        response = client.chat.completions.create(
            model="meta-llama/llama-3.1-8b-instruct",
            temperature=0.4,
            messages=[{"role": "user", "content": prompt}],
        )
        intro = response.choices[0].message.content.strip()
    except (APIConnectionError, APITimeoutError, RateLimitError, APIStatusError, Exception):
        intro = ""

    structured = _build_answer(products, lang)
    return f"{intro}\n\n{structured}" if intro else structured
