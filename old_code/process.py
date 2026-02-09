import os
import json

from concurrent.futures import ThreadPoolExecutor, as_completed
from openai import OpenAI



from dotenv import load_dotenv
load_dotenv()
import os
api_key = os.getenv("api_key")
client = OpenAI(api_key= api_key) 



def build_segment_context(outline, idx):
    prev_seg = outline["segments"][idx-1] if idx > 0 else None
    curr_seg = outline["segments"][idx]
    next_seg = outline["segments"][idx+1] if idx < len(outline["segments"]) - 1 else None

    return {
        "previous_covers": prev_seg["covers"] if prev_seg else [],
        "current_objective": curr_seg["objective"],
        "next_objective": next_seg["objective"] if next_seg else "",
        "segment_id": curr_seg["segment_id"]
    }

def build_outline_prompt(
    topic, content_type, tones, language, duration, unit
):
    duration_seconds = duration * 60 if unit == "minutes" else duration

    return f"""
STRICT RULES:
- Output valid JSON only
- No markdown, no explanations

TASK:
Create a spoken-content OUTLINE for ONE continuous script.

Each segment MUST:
- Cover a distinct part of the topic
- NOT repeat content from other segments
- Flow logically into the next segment

For each segment include:
- objective: one sentence describing its role in the full script
- covers: bullet list of concepts explained ONLY in that segment
### Timing Rules:
- Divide the script into logical spoken segments.
- Each segment must feel appropriate for its time window.
- The final segment MUST end exactly at {duration}:00 if unit is minutes.
- Use timestamps only as guidance, not approximation.
INPUT:
Topic: {topic}
Content Type: {content_type}
Tones: {tones}
Language: {language}
Total Duration: {duration_seconds} seconds

OUTPUT JSON:
{{
  "title": "",
  "summary": "",
  "segments": [
    {{
      "segment_id": 1,
      "start_time": "00:00",
      "end_time": "01:00",
      "target_word_count": 150,
      "objective": "",
      "covers": []
    }}
  ]
}}

Rules:
- Cover full duration
- Final segment MUST end exactly at {duration_seconds} seconds
"""

# def generate_outline(payload):
#     response = client.responses.create(
#         model="gpt-5-mini",
#         input=[
#             {"role": "system", "content": "Output valid JSON only."},
#             {"role": "user", "content": build_outline_prompt(**payload)}
#         ],
#     )

#     return json.loads(response.output_text)
def extract_output_text(response):
    texts = []

    for message in response.output:
        # each message has content blocks
        for block in message.content:
            if block.type == "output_text":
                texts.append(block.text)

    return "\n".join(texts).strip()

def generate_outline(payload):
    response = client.chat.completions.create(
        model="gpt-4.1",
        messages=[
            {
                "role": "system",
                "content": (
                    "You output ONLY valid JSON. "
                    "No markdown. No commentary. No explanations."
                )
            },
            {
                "role": "user",
                "content": build_outline_prompt(**payload)
            }
        ],
        temperature=0.2
    )

    text = response.choices[0].message.content.strip()

    if not text:
        raise RuntimeError("Outline generation failed: empty response")

    return json.loads(text)



def build_segment_prompt(
    topic,
    content_type,
    tones,
    language,
    segment,
    context
):
    intro_rule = (
        "You MAY introduce the topic briefly."
        if context["segment_id"] == 1
        else "Do NOT introduce the topic or greet the audience."
    )

    outro_rule = (
        "You MAY conclude the script."
        if context["next_objective"] == ""
        else "Do NOT conclude. Smoothly transition toward the next segment."
    )

    return f"""
STRICT RULES:
- Output valid JSON only
- No markdown
- No explanations

YOU ARE WRITING PART {context["segment_id"]} OF ONE CONTINUOUS SCRIPT.

PREVIOUSLY COVERED TOPICS (DO NOT REPEAT):
{json.dumps(context["previous_covers"], indent=2)}

CURRENT SEGMENT OBJECTIVE:
{context["current_objective"]}

NEXT SEGMENT WILL COVER:
{context["next_objective"]}

TIMING CONSTRAINTS:
Start: {segment["start_time"]}
End: {segment["end_time"]}
Maximum words: {segment["target_word_count"]}

STYLE RULES:
- Spoken, natural flow
- Maintain tone continuity
- No recaps
- No restarting the topic

SPECIAL RULES:
- {intro_rule}
- {outro_rule}

OUTPUT JSON:
{{
  "segment_id": {segment["segment_id"]},
  "script": ""
}}
"""
def generate_segment(segment, shared_data, context):
    response = client.responses.create(
        model="gpt-5-mini",
        input=[
            {"role": "system", "content": "Output valid JSON only."},
            {
                "role": "user",
                "content": build_segment_prompt(
                    **shared_data,
                    segment=segment,
                    context=context
                )
            }
        ],
    )

    return json.loads(response.output_text)


# def generate_all_segments(outline, shared_data):
#     results = []

#     with ThreadPoolExecutor(max_workers=6) as executor:
#         futures = []
#         for idx, seg in enumerate(outline["segments"]):
#             context = build_segment_context(outline, idx)
#             futures.append(
#                 executor.submit(generate_segment, seg, shared_data, context)
#             )

#         for future in as_completed(futures):
#             results.append(future.result())

#     # restore order
#     results.sort(key=lambda x: x["segment_id"])
#     return results


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
