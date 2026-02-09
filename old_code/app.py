from flask import Flask, request, Response, stream_with_context
from concurrent.futures import ThreadPoolExecutor, as_completed
import json

from parallel_generate import (
    generate_outline,
    generate_segment,
    merge_final
)

from rules import (
    CONTENT_TYPE_RULES,
    CONTENT_TONE_RULES,
    SPOKEN_WPM,
    normalize_content_type,
    normalize_tones,
    NORMALIZED_CONTENT_TYPE_MAP
)

app = Flask(__name__)
@app.route("/generate-stream", methods=["POST"])
def generate_stream():
    data = request.json

    # ---------- Normalize Content Type ----------
    normalized_ct = normalize_content_type(data["content_type"])
    content_type_key = NORMALIZED_CONTENT_TYPE_MAP.get(normalized_ct)

    if not content_type_key:
        return {"error": f"Invalid content_type: {data['content_type']}"}, 400

    # ---------- Normalize Tones ----------
    try:
        tones = normalize_tones(data["tones"])
    except ValueError as e:
        return {"error": str(e)}, 400

    def event_stream():
        yield "event: status\ndata: Generating outline...\n\n"
        wpm = SPOKEN_WPM.get(content_type_key, 120)

        outline_payload = {
            "topic": data["topic"],
            "content_type": content_type_key,
            "tones": tones,
            "language": data["language"],
            "duration": data["duration"],
            "unit": data["unit"],

            # 🔥 ADD THESE
            "content_type_rules": CONTENT_TYPE_RULES[content_type_key],
            "tone_rules": {t: CONTENT_TONE_RULES[t] for t in tones},
            "wpm": wpm,
        }


        outline = generate_outline(outline_payload)

        yield f"event: outline\ndata: {json.dumps(outline)}\n\n"

        shared_data = {
            "topic": data["topic"],
            "language": data["language"],
            "global_constraints": outline["global_constraints"],
        }



        results = []
        with ThreadPoolExecutor(max_workers=6) as executor:
            futures = {
                executor.submit(generate_segment, seg, shared_data): seg
                for seg in outline["segments"]
            }

            for future in as_completed(futures):
                result = future.result()
                results.append(result)
                yield f"event: segment_done\ndata: {json.dumps(result)}\n\n"

        results.sort(key=lambda x: x["segment_id"])
        final_json = merge_final(outline, results)

        yield "event: final\ndata: " + json.dumps(final_json) + "\n\n"

    return Response(
        stream_with_context(event_stream()),
        mimetype="text/event-stream"
    )
if __name__ == "__main__":
    app.run(port=5003, debug=True)
