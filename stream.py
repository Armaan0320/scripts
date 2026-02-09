from flask import Flask, request, Response, stream_with_context, jsonify
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from flask_cors import CORS

from stream_process import (
    generate_outline,
    generate_segment,
    retry_generate_segment,   # 🔥 ADD THIS
    build_segment_context,
    merge_final
)

app = Flask(__name__)
CORS(app, supports_credentials=True, origins=["*"])

def extract_output_text(response):
    texts = []

    for msg in response.output:
        if hasattr(msg, "content"):
            for block in msg.content:
                if block.type == "output_text":
                    texts.append(block.text)

    return "\n".join(texts).strip()


@app.route("/generate", methods=["POST"])
def generate_stream():
    try:
        data = request.json
        print("Received data:", data)
        topic = data.get('topic')
        content_type = data.get('content_type')
        language = data.get('language')
        duration = data.get('duration')
        unit = data.get('unit')
        raw_tones = data.get('tones') or []
        if not isinstance(raw_tones, list):
            raw_tones = [raw_tones]

        required_params = {
            "topic": topic,
            "content_type": content_type,
            "language": language,
            "duration": duration,
            "unit": unit
        }

        missing_params = [key for key, value in required_params.items() if not value]

        if missing_params:
            return jsonify({
                "error": "Missing required parameters.",
                "missing": missing_params
            }), 400

        def event_stream():
            # 1 Outline
            yield "event: status\ndata: Generating outline...\n\n"
            outline = generate_outline(data)
            yield f"event: outline\ndata: {json.dumps(outline)}\n\n"

            shared_data = {
                "topic": data["topic"],
                "content_type": data["content_type"],
                "tones": data["tones"],
                "language": data["language"]
            }
            # 2 Parallel segments (context-aware, worker-based) with streaming
            results = []

            with ThreadPoolExecutor(max_workers=6) as executor:
                futures = {}

                for idx, seg in enumerate(outline["segments"]):
                    context = build_segment_context(outline, idx)

                    future = executor.submit(
                        retry_generate_segment,
                        seg,
                        shared_data,
                        context
                    )
                    futures[future] = seg["segment_id"]

                for future in as_completed(futures):
                    try:
                        result = future.result()
                        results.append(result)
                        yield f"event: segment_done\ndata: {json.dumps(result)}\n\n"
                    except Exception as e:
                        yield (
                            "event: segment_error\n"
                            f"data: {json.dumps({'error': str(e)})}\n\n"
                        )



            # # 3 Final merge
            # results.sort(key=lambda x: x["segment_id"])
            # final_json = merge_final(outline, results)

            # yield "event: final\ndata: " + json.dumps(final_json) + "\n\n"
            # 3 Completion signal (no merge)
            results.sort(key=lambda x: x["segment_id"])

            yield (
                "event: final\n"
                "data: " + json.dumps({
                    "message": "completed",
                    "total_segments": len(results),
                    "segments": results
                }) + "\n\n"
            )


        return Response(
            stream_with_context(event_stream()),
            mimetype="text/event-stream"
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 400


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5003, debug=False)
