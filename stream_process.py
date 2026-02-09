import os
import json

from concurrent.futures import ThreadPoolExecutor, as_completed
from openai import OpenAI



from dotenv import load_dotenv
load_dotenv()
import os
api_key = os.getenv("api_key")
client = OpenAI(api_key= api_key) 

import time

def retry_generate_segment(
    segment,
    shared_data,
    context,
    max_retries=3,
    retry_delay=0.8
):
    last_error = None
    repair_comment = ""

    for attempt in range(1, max_retries + 1):
        try:
            # pass repair comment via context
            context_with_retry = dict(context) 
            context_with_retry["retry_attempt"] = attempt
            context_with_retry["repair_comment"] = repair_comment

            result = generate_segment(
                segment,
                shared_data,
                context_with_retry
            )

            # HARD validation
            if not result or not isinstance(result, dict):
                raise ValueError("Empty or non-JSON output")

            if "segment_id" not in result or "script" not in result:
                raise ValueError("Missing required JSON fields")

            if not result["script"].strip():
                raise ValueError("Script text is empty")

            return result 

        except Exception as e:
            last_error = e

            repair_comment = (
                f"The previous attempt failed with this error:\n"
                f"{str(e)}\n\n"
                f"You MUST fix this error and output ONLY valid JSON."
            )

            print(
                f"[RETRY] Segment {segment['segment_id']} "
                f"attempt {attempt}/{max_retries} failed"
            )

            time.sleep(retry_delay)

    # All retries failed
    raise RuntimeError(
        f"Segment {segment['segment_id']} failed after {max_retries} retries: {last_error}"
    )


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
    # 1️⃣ Fast path (most common)
    if hasattr(response, "output_text") and response.output_text:
        return response.output_text.strip()

    texts = []

    # 2️⃣ Structured output
    if hasattr(response, "output") and response.output:
        for message in response.output:
            content = getattr(message, "content", [])
            for block in content:
                # tolerate missing type
                if hasattr(block, "text"):
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
    repair_block = ""
    if context.get("repair_comment"):
        repair_block = f"""
        IMPORTANT FIX REQUIRED:
        {context["repair_comment"]}"""

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

{repair_block}

OUTPUT JSON:
{{
  "segment_id": {segment["segment_id"]},
  "script": ""
}}
"""
def generate_segment(segment, shared_data, context):
    try:
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
            ]
        )

    except Exception as e:
        print("🔥 GPT REQUEST FAILED")
        print("Segment:", segment["segment_id"])
        print("Error:", repr(e))
        raise RuntimeError(f"OpenAI call failed: {e}") from e

    raw_text = extract_output_text(response)

    print(f"🧠 RAW GPT OUTPUT (segment {segment['segment_id']}):")
    print(raw_text[:600])

    if not raw_text:
        raise RuntimeError("Empty segment output")

    try:
        return json.loads(raw_text)
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"Invalid JSON in segment {segment['segment_id']}:\n{raw_text}"
        ) from e



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
