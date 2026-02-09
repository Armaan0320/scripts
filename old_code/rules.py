# rules.py
import json

with open("src/rules.json", "r", encoding="utf-8") as f:
    content_rules = json.load(f)

CONTENT_TYPE_RULES = content_rules["CONTENT_TYPE_RULES"]
CONTENT_TONE_RULES = content_rules["CONTENT_TONE_RULES"]

SPOKEN_WPM = {
    "video":150,
    "ted_talk": 120,
    "podcast": 110,
    "speech": 135,
    "presentation": 140,
    "standup_comedy": 105,
    "narration": 120,
    "monologue": 110,
    "debate": 145,
    "interview": 115,
    "skit": 130
}

FRONTEND_TONE_MAP = {
    "education": "informative",
    "educational": "informative",
    "motivational": "inspirational",
    "motivation": "inspirational",
    "promotion": "persuasive",
    "promotional": "persuasive",
    "funny": "humorous",
    "humor": "humorous",
    "humorous": "humorous",
    "dramatic": "dramatic",
    "casual": "casual",
    "professional": "professional",
    "conversational": "conversational",
    "storytelling": "storytelling",
    "neutral": "neutral",
    "persuasive": "persuasive",
    "authoritative": "authoritative",
}

def normalize_content_type(value: str) -> str:
    return (
        value.strip()
        .lower()
        .replace("-", " ")
        .replace("_", " ")
    )

NORMALIZED_CONTENT_TYPE_MAP = {
    k.replace("_", " ").lower(): k
    for k in CONTENT_TYPE_RULES.keys()
}

def normalize_tones(raw_tones):
    tones = []
    for t in raw_tones:
        key = t.strip().lower()
        mapped = FRONTEND_TONE_MAP.get(key)
        if not mapped:
            raise ValueError(f"Invalid tone: {t}")
        tones.append(mapped)
    return tones
