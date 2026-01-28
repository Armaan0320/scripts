from flask import Flask, request, jsonify
from dotenv import load_dotenv
from openai import OpenAI
import os
import re
from flask_cors import CORS
from threading import Thread
import requests

load_dotenv()
app = Flask(__name__)
#CORS(app, supports_credentials=True, origins=["http://localhost:4200"])
CORS(app, supports_credentials=True, origins=["*"])
openai_key = os.getenv("api_key")
client = OpenAI(api_key=openai_key)
callback = os.getenv("callback_url")
token = '65bc09cf-1b86-4cdc-b796-30ad1f59e73a'



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

CONTENT_TYPE_RULES = {
    "ted talk": """Structure: Strong hook → Personal story → Big idea → Evidence → Call-to-action.
Language Style: Inspiring, semi-formal, personal yet intellectual.
Pacing: Moderate to slightly slow for emphasis.
Vocabulary: Mix of simple terms with occasional advanced vocabulary.
Transitions: Smooth and logical, connect personal anecdotes to larger themes.
Delivery Notes: Emphasize key points with pauses, vary tone for emotion.
Special Elements: Personal story at start, “idea worth spreading” moment, memorable closing.
Prohibited: Overly technical jargon without explanation, flat monotone delivery.""",

    "podcast": """Structure: Warm introduction → Topic discussion → Tangents → Closing summary.
Language Style: Conversational, relatable, natural flow.
Pacing: Relaxed, occasional pauses for thought.
Vocabulary: Everyday words, occasional slang, idiomatic expressions.
Transitions: Informal, can use phrases like “so anyway”, “let's shift gears”.
Delivery Notes: Include natural filler words sparingly for realism.
Special Elements: Host-listener connection, occasional personal anecdotes.
Prohibited: Script-like rigid sentences, excessive data dumping.""",

    "speech": """Structure: Introduction → Body (2-3 main points) → Conclusion.
Language Style: Formal, polished, confident.
Pacing: Moderate with clear enunciation.
Vocabulary: Standard professional vocabulary, avoid slang.
Transitions: Clear signposting (“First… Second… Lastly…”).
Delivery Notes: Use rhetorical devices like repetition, triads, and metaphors.
Special Elements: Memorable closing line, audience-inclusive statements.
Prohibited: Rambling, overly complex sentences.""",

    "presentation": """Structure: Opening greeting → Overview → Key points → Conclusion.
Language Style: Semi-formal, clear, instructional.
Pacing: Moderate, matching imaginary slides.
Vocabulary: Clear terms, explain industry jargon.
Transitions: “As you can see…”, “Next, we’ll look at…”.
Delivery Notes: Assume visual aids, emphasize clarity.
Special Elements: Summaries after each main section.
Prohibited: Overcrowding segments with too many ideas.""",

    "skit": """Structure: Scene setup → Conflict → Resolution or punchline.
Language Style: Natural dialogue for each character.
Pacing: Snappy for comedic timing, varied for drama.
Vocabulary: Everyday words fitting character personality.
Transitions: Scene changes or character reactions.
Delivery Notes: Distinct voices for each character.
Special Elements: Humor, irony, exaggerated personalities.
Prohibited: Monotonous exchanges without conflict.""",

    "debate": """Structure: Opening statement → Rebuttals → Closing arguments.
Language Style: Persuasive, formal.
Pacing: Deliberate but firm.
Vocabulary: Logical, evidence-backed phrasing.
Transitions: “My opponent claims… however…”.
Delivery Notes: Alternate speakers, respectful but assertive tone.
Special Elements: Evidence and counter-arguments.
Prohibited: Personal attacks, emotional overreactions.""",

    "stand-up comedy": """Structure: Opening joke → Observational humor → Callback → Strong closer.
Language Style: Humorous, sarcastic, personal.
Pacing: Varied, pause before punchlines.
Vocabulary: Informal, slang acceptable.
Transitions: Flow naturally between topics.
Delivery Notes: Emphasize punchline with pauses.
Special Elements: Relatable humor, callbacks.
Prohibited: Excessively offensive jokes (unless edgy humor is the intent).""",

    "narration": """Structure: Exposition → Rising action → Climax → Resolution.
Language Style: Descriptive, immersive, vivid.
Pacing: Moderate with variations for tension.
Vocabulary: Rich descriptive terms, sensory words.
Transitions: Scene-based, location/time changes.
Delivery Notes: Paint a mental picture, use pacing for mood control.
Special Elements: Sensory imagery, foreshadowing.
Prohibited: Monotone factual delivery.""",

    "interview": """Structure: Introduction of guest → Questions → Follow-ups → Closing remarks.
Language Style: Conversational, respectful.
Pacing: Varied based on guest's answers.
Vocabulary: Clear, direct questions.
Transitions: “Speaking of that…”, “Can you elaborate?”.
Delivery Notes: Distinct voices for interviewer/guest.
Special Elements: Personal stories from guest, natural banter.
Prohibited: Overly scripted robotic exchanges.""",

    "monologue": """Structure: Opening hook → Exploration of thought → Closing insight.
Language Style: Personal, introspective.
Pacing: Steady, thoughtful.
Vocabulary: Everyday words, metaphorical language.
Transitions: Smooth thought progression.
Delivery Notes: Expressive tone, emotional depth.
Special Elements: Internal conflict, self-reflection.
Prohibited: Abrupt topic jumps without connection."""
}

CONTENT_TONE_RULES = {
    "conversational": "Informal, friendly language. Use contractions, relatable examples, occasional humor. Avoid technical jargon.",
    "professional": "Formal, concise, polished delivery. Avoid slang. Use precise vocabulary and direct statements.",
    "inspirational": "Uplifting language, success stories, motivational calls to action. Use positive adjectives and strong verbs.",
    "informative": "Fact-driven, structured explanation. Use data, examples, and analogies.",
    "humorous": "Playful tone, witty remarks, exaggerations. Use comedic timing and callbacks.",
    "dramatic": "High emotional stakes, strong adjectives, dynamic pacing. Use pauses for tension.",
    "persuasive": "Logical arguments, emotional appeals, rhetorical questions. Strong call-to-action.",
    "casual": "Relaxed, everyday language. Light humor. No rigid structure.",
    "serious": "Straightforward, factual. No jokes or lightness. Strong, steady delivery.",
    "empathetic": "Compassionate, understanding tone. Validate audience feelings.",
    "sarcastic": "Ironic, exaggerated statements. Humor with a bite.",
    "storytelling": "Narrative-driven, vivid imagery. Clear beginning, middle, end.",
    "energetic": "High-paced, enthusiastic word choice. Excited delivery.",
    "neutral": "Balanced tone, factual. Avoid emotional bias.",
    "authoritative": "Commanding tone, confident statements. Speak with certainty."
}

def generate_prompt(topic, content_type, tones, language, duration, unit):
    tone_str = ", ".join(tones)
    content_type_rule = CONTENT_TYPE_RULES.get(content_type.lower(), "")
    tone_rules_combined = "\n".join(
        [f"- {tone}: {CONTENT_TONE_RULES.get(tone.lower(), '')}" for tone in tones]
    )

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

def process_script(request_id, topic, content_type, tones, language, duration, unit):
    prompt = generate_prompt(topic, content_type, tones, language, duration, unit)
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
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
