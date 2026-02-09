from flask import Flask, request, Response, stream_with_context
from concurrent.futures import ThreadPoolExecutor, as_completed
import json

from process import (
    generate_outline,
    generate_segment, 
    build_segment_context,
    merge_final
)


app = Flask(__name__)
@app.route("/generate-stream", methods=["POST"])
def generate_stream():
    data = request.json

    def event_stream():
        # 1️⃣ Outline
        yield "event: status\ndata: Generating outline...\n\n"
        outline = generate_outline(data)
        yield f"event: outline\ndata: {json.dumps(outline)}\n\n"

        shared_data = {
            "topic": data["topic"],
            "content_type": data["content_type"],
            "tones": data["tones"],
            "language": data["language"]
        }
        # 2️⃣ Parallel segments (context-aware, worker-based)
        # 2️⃣ Parallel segments WITH streaming
        results = []

        with ThreadPoolExecutor(max_workers=6) as executor:
            futures = {}

            for idx, seg in enumerate(outline["segments"]):
                context = build_segment_context(outline, idx)

                future = executor.submit(
                    generate_segment,
                    seg,
                    shared_data,
                    context
                )
                futures[future] = seg["segment_id"]

            for future in as_completed(futures):
                result = future.result()
                results.append(result)

                # 🔥 STREAM AS SOON AS DONE
                yield f"event: segment_done\ndata: {json.dumps(result)}\n\n"



        # 3️⃣ Final merge
        results.sort(key=lambda x: x["segment_id"])
        final_json = merge_final(outline, results)

        yield "event: final\ndata: " + json.dumps(final_json) + "\n\n"

    return Response(
        stream_with_context(event_stream()),
        mimetype="text/event-stream"
    )
if __name__ == "__main__":
    app.run(port=5000, debug=True)
