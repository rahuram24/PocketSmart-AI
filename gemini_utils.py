import json
import os
from google import genai
from google.genai import types
from .mock_catalog import CATALOG

_client = None

def get_client():
    global _client
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        return None
    if _client is None:
        _client = genai.Client(api_key=key)
    return _client

def catalog_text(planner: str) -> str:
    return json.dumps(CATALOG.get(planner, []), indent=2)

def build_prompt(planner: str, data: dict) -> str:
    common = f"""
You are PocketSmart AI, a budget planning assistant.
Planner: {planner}
User input:
{json.dumps(data, indent=2)}

Use only the supplied mock catalog as the source of named platforms/products.
Do not claim that you live-scraped Amazon, Flipkart, IKEA, Swiggy, Zomato, or OYO.
Create practical recommendations that stay within the user's stated budget.

Return:
1. A short budget allocation.
2. 3-6 recommended options.
3. Estimated price for each.
4. Platform.
5. Why it fits.
6. A final total estimate.
Use Indian Rupees (₹).
"""
    if planner == "home":
        common += "\nFocus on room, style, quantities/items, and value for money."
    elif planner == "party":
        common += "\nFocus on guest count, event type, venue, food, decoration, and entertainment."
    else:
        common += "\nFocus on occasion, style, budget, and outfit/color compatibility if an image is supplied."
    common += "\nMock catalog:\n" + catalog_text(planner)
    return common

def fallback(planner: str, data: dict) -> str:
    budget = float(data.get("budget", 0))
    rows = CATALOG.get(planner, [])[:4]
    lines = [f"AI service is not configured, so these are fallback suggestions for a ₹{budget:,.0f} budget."]
    for r in rows:
        lines.append(f"- {r['name']} — ₹{r['price']:,} — {r['platform']}")
    lines.append("Add GEMINI_API_KEY to enable personalized Gemini recommendations.")
    return "\n".join(lines)

def generate_recommendations(planner: str, data: dict, image_bytes=None, image_mime=None) -> str:
    client = get_client()
    if client is None:
        return fallback(planner, data)

    prompt = build_prompt(planner, data)
    contents = [prompt]

    if image_bytes and image_mime:
        contents.append(types.Part.from_bytes(data=image_bytes, mime_type=image_mime))

    model = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
    try:
        response = client.models.generate_content(
            model=model,
            contents=contents,
        )
        text = getattr(response, "text", None)
        return text.strip() if text else fallback(planner, data)
    except Exception as exc:
        # Keep the demo usable if the API is unavailable or quota is exceeded.
        return fallback(planner, data) + f"\n\nGemini connection note: {type(exc).__name__}"
