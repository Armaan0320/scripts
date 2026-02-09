from flask import Flask, request, jsonify
from dotenv import load_dotenv
from flask_cors import CORS
from openai import OpenAI
import json
import os
import re

load_dotenv()
app = Flask(__name__)
#CORS(app, supports_credentials=True, origins=["http://localhost:4200"])
CORS(app, supports_credentials=True, origins=["*"])
openai_key = os.getenv("api_key")
client = OpenAI(api_key=openai_key)

# loading rules
with open("src/rules.json", "r", encoding="utf-8") as f:
    content_rules = json.load(f)

CONTENT_TYPE_RULES = content_rules["CONTENT_TYPE_RULES"]
CONTENT_TONE_RULES = content_rules["CONTENT_TONE_RULES"]

# spoken words per minute assumptions
SPOKEN_WPM = {
    "video":160,
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

def format_content_type_rules(rule_dict: dict) -> str:
    lines = []
    for k, v in rule_dict.items():
        if isinstance(v, list):
            lines.append(f"{k.replace('_',' ').title()}: {', '.join(v)}")
        else:
            lines.append(f"{k.replace('_',' ').title()}: {v}")
    return "\n".join(lines)

def build_prompt(
    topic,
    content_type,
    tones,
    language,
    duration,
    unit
):
    duration_seconds = duration * 60 if unit == "minutes" else duration
    assumed_wpm = SPOKEN_WPM.get(content_type, 120)
    total_words = int((duration_seconds / 60) * assumed_wpm)

    ct_rules = format_content_type_rules(CONTENT_TYPE_RULES[content_type])
    tone_rules = "\n".join(
        f"- {t}: {CONTENT_TONE_RULES[t]}" for t in tones
    )

    return f"""
You are a senior spoken-content architect.

STRICT OUTPUT RULES:
- Output valid JSON only
- No markdown
- No explanations
- No extra text

CONTENT DETAILS:
Topic: {topic}
Content Type: {content_type}
Language: {language}
Tones: {tones}
Target Duration: {duration_seconds} seconds
Assumed Spoken Speed: {assumed_wpm} WPM
Target Total Words: {total_words}

CONTENT TYPE RULES:
{ct_rules}

TONE RULES:
{tone_rules}

TIMING RULES:
- Spoken content, not written
- Expand ideas verbally
- Plan segments before writing
- Match word counts per segment (±3%)
- Final segment must end exactly at {duration_seconds} seconds

OUTPUT JSON SCHEMA:
{{
  "title": "",
  "summary": "",
  "segments": [
    {{
      "start_time": "00:00",
      "end_time": "00:00",
      "target_word_count": 0,
      "script": ""
    }}
  ]
}}
"""

def transform_for_frontend(model_output: dict) -> dict:
    segments = [
        {
            "start_time": seg.get("start_time", "00:00"),
            "end_time": seg.get("end_time", "00:00"),
            "script_data": seg.get("script", "")
        }
        for seg in model_output.get("segments", [])
    ]

    return {
        "title": model_output.get("title", ""),
        "summary": model_output.get("summary", ""),
        "data": segments
    }

def normalize_content_type(value: str) -> str:
    return (
        value.strip()
        .lower()
        .replace("-", " ")
        .replace("_", " ")
        .replace("  ", " ")
    )
NORMALIZED_CONTENT_TYPE_MAP = {
    k.replace("_", " ").lower(): k
    for k in CONTENT_TYPE_RULES.keys()
}
def normalize_tone(t: str) -> str:
    return t.strip().lower()

@app.route("/generate", methods=["POST"])
def generate_script():
    try:
        data = request.json or {}
        print("[INFO] Request data:", data)
        topic = data.get("topic")

        raw_content_type = data.get("content_type", "")

        normalized_ct = normalize_content_type(raw_content_type)

        content_type = NORMALIZED_CONTENT_TYPE_MAP.get(normalized_ct)


        tones = [normalize_tone(t) for t in data.get("tones", [])]


        language = data.get("language", "English")
        duration = int(data.get("duration", 5))
        unit = data.get("unit", "minutes")

        if not topic or not content_type:
            return jsonify({
                "error": f"Invalid content_type: {raw_content_type}"
            }), 400

        for t in tones:
            if t not in CONTENT_TONE_RULES:
                return jsonify({"error": f"Invalid tone: {t}"}), 400

        prompt = build_prompt(
            topic, content_type, tones, language, duration, unit
        )

        response = client.responses.create(
            model="gpt-5.2",
            input=[
                {
                    "role": "system",
                    "content": (
                        "You are a senior spoken-content architect. "
                        "You MUST output valid JSON only. "
                        "No markdown. No explanations. No extra text."
                    )
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
        )

        raw_text = response.output_text.strip()

        try:
            model_output = json.loads(raw_text)
        except json.JSONDecodeError:
            return jsonify({"error": "Invalid JSON from model"}), 500

        frontend_response = transform_for_frontend(model_output)
        print("[INFO] Frontend response:", frontend_response)
        return jsonify(frontend_response), 200

    except Exception as e:
        print("[ERROR]", e)
        return jsonify({"error": str(e)}), 500



# --------------------------------------------------
# MAIN
# --------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5003, debug=False)
