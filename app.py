from flask import Flask, render_template, request, jsonify
import os
import random
import requests

app = Flask(__name__)

# ✅ Groq API key
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise RuntimeError("⚠️ Missing GROQ_API_KEY. Set it using: export GROQ_API_KEY='your_key_here'")

# 🎯 Question pool (expandable)
QUESTIONS = [
    "Did you really wake up on time today?",
    "Have you lied to someone recently?",
    "Do you always tell the truth?",
    "Are you hiding anything right now?",
    "Do you think people can tell when you lie?",
    "Would you say you’re confident in your honesty?",
    "Have you ever broken a promise?",
    "Do you trust AI to judge your truthfulness?",
    "Have you ever cheated on a test?",
    "Do you sometimes exaggerate?",
    "Have you lied to a friend before?",
    "Do you hide your feelings often?",
    "Have you ever stolen something?",
    "Do you always keep secrets?",
    "Have you ever lied about your age?",
    "Do you tell white lies often?",
    "Have you ever blamed someone else unfairly?",
    "Do you hide mistakes at work/school?",
    "Have you ever lied to avoid punishment?",
    "Do you sometimes fake interest in conversations?",
    "Do you lie in online profiles?",
    "Have you ever lied in a relationship?",
    "Do you sometimes pretend to know things you don't?",
    "Have you lied to protect someone's feelings?",
    "Do you tell different stories to different people?",
    "Have you ever lied to get out of trouble?",
    "Do you exaggerate your achievements?",
    "Have you lied to get attention?",
    "Do you lie about small things often?",
    "Have you ever faked being sick?"
]

SESSION_QUESTIONS = 30  # questions per session
SESSIONS = {}  # store sessions in memory keyed by IP

def ask_groq(question, answer):
    """Send question & answer to Groq API via requests and return verdict."""
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    system_msg = (
        "You are KV Lie Analyzer — a smart AI lie detector. "
        "Judge honesty based on tone, logic, and emotion. "
        "Respond with only one verdict: 'Truthful ✅', 'Suspicious 😶', or 'Lying 🤥'."
    )
    payload = {
        "model": "llama3-8b-8192",
        "messages": [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": f"Question: {question}\nAnswer: {answer}"}
        ],
        "temperature": 0.5
    }
    try:
        res = requests.post(url, headers=headers, json=payload, timeout=20)
        res.raise_for_status()
        data = res.json()
        return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print("🚨 Groq HTTP Error:", e)
        # fallback offline verdict (random)
        return random.choice(["Truthful ✅", "Suspicious 😶", "Lying 🤥"])

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/next", methods=["GET"])
def next_question():
    """Serve the next question for the session."""
    session_id = request.remote_addr
    if session_id not in SESSIONS:
        # Initialize session
        selected_questions = random.sample(QUESTIONS, SESSION_QUESTIONS)
        SESSIONS[session_id] = {
            "questions": selected_questions,
            "answers": [],
            "index": 0
        }
    session = SESSIONS[session_id]
    idx = session["index"]
    if idx >= len(session["questions"]):
        return jsonify({"done": True})
    question = session["questions"][idx]
    return jsonify({
        "question": question,
        "index": idx + 1,
        "total": len(session["questions"]),
        "done": False
    })

@app.route("/answer", methods=["POST"])
def handle_answer():
    """Receive user's answer, get verdict, update session, return progress."""
    session_id = request.remote_addr
    if session_id not in SESSIONS:
        return jsonify({"error": "Session not started"}), 400

    session = SESSIONS[session_id]
    idx = session["index"]

    data = request.get_json(force=True)
    answer = data.get("answer", "").strip()
    if not answer:
        return jsonify({"error": "No answer provided!"}), 400

    question = session["questions"][idx]
    verdict = ask_groq(question, answer)

    session["answers"].append({"question": question, "answer": answer, "verdict": verdict})
    session["index"] += 1
    done = session["index"] >= len(session["questions"])
    progress = session["index"]

    # If done, compute final summary
    final_summary = None
    if done:
        counts = {"Truthful ✅": 0, "Suspicious 😶": 0, "Lying 🤥": 0}
        for a in session["answers"]:
            for key in counts:
                if key in a["verdict"]:
                    counts[key] += 1
        total = sum(counts.values())
        honesty_percent = round((counts["Truthful ✅"] / total) * 100, 1) if total > 0 else 0
        final_summary = {
            "counts": counts,
            "honesty_percent": honesty_percent
        }

    return jsonify({
        "verdict": verdict,
        "progress": progress,
        "done": done,
        "summary": final_summary
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
