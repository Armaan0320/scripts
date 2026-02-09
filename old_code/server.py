from flask import Flask, request, jsonify
from dotenv import load_dotenv
from openai import OpenAI
import os
import re
from flask_cors import CORS
from threading import Thread
import requests
import json

load_dotenv()
app = Flask(__name__)
#CORS(app, supports_credentials=True, origins=["http://localhost:4200"])
CORS(app, supports_credentials=True, origins=["*"])
openai_key = os.getenv("api_key")
client = OpenAI(api_key=openai_key)
callback = os.getenv("callback_url")
token = os.getenv("token")

with open("src/rules.json", "r", encoding="utf-8") as f:
    content_rules = json.load(f)

def send_callback(data, url = callback):
    """Send results back to callback endpoint."""
    try:
        headers = {
            "Content-Type": "application/json",
            "X-AUTH-TOKEN": token
        }
        resp = requests.post(url, json=data, headers=headers, timeout=10)
        print("resp:", resp.text)
        print(f"[CALLBACK] Sent ({resp.status_code})")
    except Exception as e:
        print(f"[CALLBACK ERROR] {e}")



def generate_prompt(topic, content_type, tones, language, duration, unit, content_type_rules, tone_type_rules):
    words_per_minute = 150
    total_words = duration * words_per_minute if unit == 'minutes' else int((duration / 60) * words_per_minute)

    return f"""
You are an expert {content_type} scriptwriter.

Follow these strict rules for structure, pacing, and delivery:

### Content Type Rules ({content_type.title()}):
{content_type_rule}

### Content Tone Rules:
{tone_rules_combined}

---

### Script Generation Instructions:
- Topic: {topic}
- Language: {language}
- Target Duration: {duration} {unit}
- You are fully responsible for pacing and timing.
- Write LONG, DETAILED spoken content suitable for real delivery.
- Do not summarize or compress ideas.
- Expand stories, explanations, examples, and transitions naturally.
- Assume a listener is hearing this live, not reading.
- Avoid short paragraphs.
- If unsure, err on the side of MORE spoken content.

### Timing Rules:
- Divide the script into logical spoken segments.
- Each segment must feel appropriate for its time window.
- The final segment MUST end exactly at {duration}:00 if unit is minutes.
- Use timestamps only as guidance, not approximation.
- Generate more and more words then you originally estimated if needed to fill time.


### Final Output:
Only return:
- Title: <title>
- Summary: <summary>
- Segments in order like:
   [MM:SS - MM:SS]
   (Paragraph(s) matching the segment duration based on word count)

---

### Important:
1. PLAN the segment breakdown before writing, so total duration matches target closely.
2. Revise segments if word count or timing deviate by more than 3%.
3. Output only the title and the timestamped paragraphs, nothing else.
4. No markdown or explanations.
"""

def clean_label(text):
    # Remove markdown-style labels like "**Title:**", "Title:", "**Summary:**", etc.
    return re.sub(r"^\**\s*(Title|Summary)\s*:\s*\**", "", text, flags=re.IGNORECASE).strip()


def parse_response(raw_text):
    lines = raw_text.strip().splitlines()
    title = ""
    summary = ""
    segments = []

    for i, line in enumerate(lines):
        if line.strip():
            title = clean_label(line.strip())
            lines = lines[i+1:]  # remove title
            break

    for i, line in enumerate(lines):
        if line.strip() and not re.match(r"\[\d{2}:\d{2}\s*-\s*\d{2}:\d{2}\]", line):
            summary = clean_label(line.strip())
            lines = lines[i+1:]
            break

    current_segment = {}
    buffer = []

    for line in lines:
        if match := re.match(r"\[(\d{2}:\d{2})\s*-\s*(\d{2}:\d{2})\]", line.strip()):
            if current_segment and buffer:
                current_segment['script_data'] = ' '.join(buffer).strip()
                segments.append(current_segment)
                buffer = []

            current_segment = {
                'start_time': match.group(1),
                'end_time': match.group(2)
            }
        else:
            if line.strip():
                buffer.append(line.strip())

    if current_segment and buffer:
        current_segment['script_data'] = ' '.join(buffer).strip()
        segments.append(current_segment)

    return {
        'title': title,
        'summary': summary,
        'data': segments
    }
00.

def process_script(request_id, topic, content_type, tones, language, duration, unit):
    tone_rules_combined = ""
    for tone in tones:
        if tone in content_rules['TONE_RULES']:
            tone_rules_combined += content_rules['TONE_RULES'][tone] + " "
    if content_type in content_rules['CONTENT_TYPE_RULES']:
        content_type_rule = content_rules['CONTENT_TYPE_RULES'][content_type]
    else:
        content_type_rule = content_type
    
    prompt = generate_prompt(topic, content_type, tones, language, duration, unit, content_type_rule, tone_rules_combined)
    try:
        response = client.chat.completions.create(
            model="gpt-5.2",
            messages=[
                {"role": "system", "content": "You are a helpful script-writing assistant."},
                {"role": "user", "content": prompt}
            ]
        )

        raw_output = response.choices[0].message.content.strip()
        parsed_output = parse_response(raw_output)

        print("Generated script:", parsed_output)

        parsed_output = parse_response(raw_output)

        final_payload = {
            "request_id": request_id,
            "response": parsed_output
        }

        send_callback(final_payload)

    except Exception as e:
        print("Error in process_script:", str(e))
        send_callback({'error': str(e)}, callback)


@app.route('/generate', methods=['POST'])
def generate_script():
    try:
        data = request.get_json()
        print("Received data:", data)
        request_id = data.get('request_id')
        topic = data.get('topic')
        content_type = data.get('content_type')
        language = data.get('language')
        duration = data.get('duration')
        unit = data.get('unit')
        tones = data.get('tones') or []
        if not isinstance(tones, list):
            tones = [tones]

        if not all([request_id, topic, content_type, language, duration, unit]):
            return jsonify({'error': 'Missing required parameters.'}), 400

        Thread(target=process_script,
        args=(request_id, topic, content_type, tones, language, duration, unit)
        ).start()
        return jsonify({'status': 'Processing started.'}), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 400

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5003, debug=False)
