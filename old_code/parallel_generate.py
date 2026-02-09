import os
import json

from concurrent.futures import ThreadPoolExecutor, as_completed
from openai import OpenAI


from dotenv import load_dotenv
load_dotenv()
import os
api_key = os.getenv("api_key")
client = OpenAI(api_key= api_key) 



def build_outline_prompt(
    topic,
    content_type,
    tones,
    language,
    duration,
    unit,
    content_type_rules,
    tone_rules,
    wpm
):
    duration_seconds = duration * 60 if unit == "minutes" else duration

    return f"""
    STRICT RULES:
    - Output valid JSON only

    TASK:
    Create a spoken-content OUTLINE with strict timing accuracy.

    CONTENT TYPE RULES:
    {json.dumps(content_type_rules, indent=2)}

    TONE RULES:
    {json.dumps(tone_rules, indent=2)}

    TIMING CONSTRAINTS:
    - Total Duration: {duration_seconds} seconds
    - Assumed Speed: {wpm} words per minute
    - Word counts must match timing
    - Final segment MUST end exactly at {duration_seconds} seconds

OUTPUT JSON:
{{
  "title": "",
  "summary": "",
  "global_constraints": {{
    "tones": [],
    "style": "spoken",
    "pace_wpm": 0,
    "delivery": "natural, conversational"
  }},
  "segments": [
    {{
      "segment_id": 1,
      "start_time": "00:00",
      "end_time": "00:00",
      "target_word_count": 0,
      "objective": ""
    }}
  ]
}}


    """


def generate_outline(payload):
    response = client.responses.create(
        model="gpt-5-mini",
        input=[
            {"role": "system", "content": "Output valid JSON only."},
            {
                "role": "user",
                "content": build_outline_prompt(
                    topic=payload["topic"],
                    content_type=payload["content_type"],
                    tones=payload["tones"],
                    language=payload["language"],
                    duration=payload["duration"],
                    unit=payload["unit"],
                    content_type_rules=payload["content_type_rules"],
                    tone_rules=payload["tone_rules"],
                    wpm=payload["wpm"],
                )
            }
        ],
    )

    return json.loads(response.output_text)


def build_segment_prompt(
    topic,
    language,
    segment,
    global_constraints
):
    return f"""
STRICT RULES:
- Output valid JSON only

GLOBAL CONSTRAINTS:
- Tones: {", ".join(global_constraints["tones"])}
- Delivery style: {global_constraints["delivery"]}
- Pace: {global_constraints["pace_wpm"]} WPM

SEGMENT OBJECTIVE:
{segment["objective"]}

TIMING:
Start: {segment["start_time"]}
End: {segment["end_time"]}
Maximum words: {segment["target_word_count"]}

TASK:
Write spoken dialogue for this segment only.

HARD RULE:
- Do NOT exceed maximum words

OUTPUT JSON:
{{
  "segment_id": {segment["segment_id"]},
  "script": ""
}}
"""



def generate_segment(segment, shared_data):
    response = client.responses.create(
        model="gpt-5-mini",
        input=[
            {"role": "system", "content": "Output valid JSON only."},
            {
                "role": "user",
                "content": build_segment_prompt(
                    **shared_data,
                    segment=segment
                )
            }
        ],
    )

    return json.loads(response.output_text)

def generate_all_segments(outline, shared_data):
    results = []

    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = [
            executor.submit(generate_segment, seg, shared_data)
            for seg in outline["segments"]
        ]

        for future in as_completed(futures):
            results.append(future.result())

    # restore order
    results.sort(key=lambda x: x["segment_id"])
    return results


def merge_final(outline, scripts):
    merged = []

    for meta, script in zip(outline["segments"], scripts):
        merged.append({
            "start_time": meta["start_time"],
            "end_time": meta["end_time"],
            "target_word_count": meta["target_word_count"],
            "script": script["script"]
        })

    return {
        "title": outline["title"],
        "summary": outline["summary"],
        "segments": merged
    }
