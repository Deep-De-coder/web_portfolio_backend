from flask import Flask, request, jsonify
from flask_cors import CORS
import json
import torch
from sentence_transformers import SentenceTransformer, util
from transformers import pipeline
import os

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Load Resume JSON
with open("resume_data.json", "r") as f:
    resume_data = json.load(f)

# Optional: Initialize Flair NER (Comment out if not needed)
try:
    from flair.data import Sentence
    from flair.models import SequenceTagger
    ner_tagger = SequenceTagger.load("flair/ner-english-ontonotes-large")
    flair_enabled = True
except ImportError:
    print("Flair not installed. Skipping NER.")
    flair_enabled = False

# Initialize NLU Intent Classifier
intent_classifier = pipeline("zero-shot-classification", model="facebook/bart-large-mnli")

# Initialize SentenceTransformer for RAG
model = SentenceTransformer('all-MiniLM-L6-v2')
resume_context = "\n".join([str(item) for item in resume_data.values()])
context_sentences = resume_context.split("\n")
context_embeddings = model.encode(context_sentences, convert_to_tensor=True)

# ✅ Extract Named Entities (Optional)
def extract_entities(text):
    """Extract named entities (Skills, Projects, etc.) from user queries using Flair."""
    if not flair_enabled:
        return {}
    
    sentence = Sentence(text)
    ner_tagger.predict(sentence)
    return {entity.text: entity.get_label("ner").value for entity in sentence.get_spans("ner")}

# ✅ Detect User Intent
def detect_intent(question):
    """Classify intent using NLU (Zero-Shot Classification)."""
    labels = ["Skill Inquiry", "Project Inquiry", "Work Experience Inquiry", "Education Inquiry", "General"]
    result = intent_classifier(question, candidate_labels=labels)
    return result["labels"][0]

# ✅ Retrieve Context for RAG (Information Retrieval)
def retrieve_relevant_context(question, top_k=3):
    """Retrieve relevant context from resume JSON using sentence embeddings."""
    question_embedding = model.encode(question, convert_to_tensor=True)
    scores = util.pytorch_cos_sim(question_embedding, context_embeddings)[0]
    top_results = scores.topk(k=top_k)
    relevant_sentences = [context_sentences[idx] for idx in top_results.indices]
    return " ".join(set(relevant_sentences[:top_k])) 

# ✅ Format Responses Properly
def format_response(answer, context):
    """Format chatbot response for UI readability."""
    return f"""
    <div style="font-size: 1rem; line-height: 1.6; max-width: 85%;">
        <strong style="color: #00ffcc;">Answer:</strong> {answer} <br><br>
        <strong style="color: #ffcc00;">Relevant Context:</strong><br>{context}
    </div>
    """.strip()

# ✅ Answer Extraction from JSON
def answer_from_json(question):
    """Fetch structured answers from resume JSON."""
    question = question.lower()
    
    direct_answers = {
        "name": resume_data["personal_info"].get("name"),
        "phone number": resume_data["personal_info"].get("contact"),
        "email": resume_data["personal_info"].get("email"),
        "address": resume_data["personal_info"].get("location"),
        "linkedin": resume_data["personal_info"].get("linkedin"),
        "github": resume_data["personal_info"].get("github"),
        "portfolio": resume_data["personal_info"].get("portfolio"),
    }

    for key, value in direct_answers.items():
        if key in question and value:
            return f"My {key} is {value}."

    # ✅ Live Projects (Now with Links)
    if "live project" in question or "active project" in question:
        live_projects = [
            f"🌐 <strong>{proj['title']}</strong> - <a href='{proj['link']}' target='_blank'>{proj['link']}</a><br>"
            f"📌 <em>{proj.get('short_description', 'No description available.')}</em><br><br>"
            for proj in resume_data["projects"] if proj.get("link")
        ]
        return (
            "<strong>Here are my live projects:</strong><br>" + "<br>".join(live_projects)
            if live_projects
            else "I currently don't have any live projects."
        )

    # ✅ General Queries (Projects, Experience, etc.)
    if "education" in question:
        return format_education_response()
    if "experience" in question:
        return format_experience_response()
    if "projects" in question:
        return format_project_response()
    if "skills" in question:
        return format_skills_response()

    return None

# ✅ Formatting Structured Responses
def format_education_response():
    education = [
        f"- 🎓 <strong>{edu['degree']}</strong> at <strong>{edu['institution']}</strong> ({edu['period']})<br>📚 <em>Courses:</em> {', '.join(edu.get('courses', []))}"
        for edu in resume_data["education"]
    ]
    return "<strong>Education Background:</strong><br><br>" + "<br><br>".join(education) if education else "No education details."

def format_experience_response():
    work_experience = [
        f"- 🛠️ <strong>{exp['role']}</strong> at <strong>{exp['company']}</strong> ({exp['period']})<br>🔹 {', '.join(exp['responsibilities'])}"
        for exp in resume_data["work_experience"]
    ]
    return "<strong>Work Experience:</strong><br><br>" + "<br><br>".join(work_experience) if work_experience else "No experience found."

def format_project_response():
    projects = [
        f"- <strong>{proj['title']}</strong> <br>📅 <em>Period:</em> {proj['period']}<br>📝 <em>Description:</em> {proj['description']}"
        for proj in resume_data["projects"]
    ]
    return "<strong>Project List:</strong><br><br>" + "<br><br>".join(projects)

def format_skills_response():
    skills = [
        f"- <strong>{key.capitalize()}:</strong> {', '.join(value)}"
        for key, value in resume_data["skills"].items()
    ]
    return "<strong>Skills:</strong><br><br>" + "<br>".join(skills) if skills else "No skills available."

# ✅ API Routes
@app.route('/chat', methods=['POST'])
def chat():
    try:
        data = request.json
        prompt = data.get("prompt", "").strip()

        if not prompt:
            return jsonify({"error": "Prompt cannot be empty."}), 400

        extracted_entities = extract_entities(prompt) if flair_enabled else {}
        intent = detect_intent(prompt)

        json_response = answer_from_json(prompt)
        if json_response:
            return jsonify({"response": json_response})

        relevant_context = retrieve_relevant_context(prompt)
        response = format_response(relevant_context, relevant_context)
        return jsonify({"response": response})

    except Exception as e:
        return jsonify({"error": "An error occurred", "details": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))  # Default to 5000 if PORT is not set
    print(f"🚀 Starting Flask on port {port}...")  # Debugging output

    app.run(host="0.0.0.0", port=port)
