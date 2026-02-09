from flask import Flask, Response
import json
import time

app = Flask(__name__)

@app.route("/stream-ndjson")
def stream_ndjson():

    def generate():
        # status
        yield json.dumps({
            "type": "status",
            "message": "Starting generation"
        }) + "\n"

        time.sleep(1)

        # outline
        yield json.dumps({
            "type": "outline",
            "data": {
                "title": "AI in Agriculture",
                "summary": "How AI is changing farming",
                "segments": [
                    {"segment_id": 1, "start_time": "00:00", "end_time": "01:00"},
                    {"segment_id": 2, "start_time": "01:00", "end_time": "03:00"}
                ]
            }
        }) + "\n"

        time.sleep(1)

        # segment 1
        yield json.dumps({
            "type": "segment",
            "segment_id": 1,
            "data": {
                "segment_id": 1,
                "script": "This is the first segment script."
            }
        }) + "\n"

        time.sleep(2)

        # segment 2
        yield json.dumps({
            "type": "segment",
            "segment_id": 2,
            "data": {
                "segment_id": 2,
                "script": "This is the second segment script."
            }
        }) + "\n"

        time.sleep(1)

        # final
        yield json.dumps({
            "type": "final",
            "data": {
                "title": "AI in Agriculture",
                "summary": "Final merged output"
            }
        }) + "\n"

    return Response(
        generate(),
        mimetype="application/x-ndjson"
    )


if __name__ == "__main__":
    app.run(port=8000, debug=True, threaded=True)
