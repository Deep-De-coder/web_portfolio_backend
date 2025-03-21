from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import json
import torch
from sentence_transformers import SentenceTransformer, util
from transformers import pipeline

# ✅ Initialize FastAPI app
app = FastAPI()

# ✅ Enable CORS for frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust for security
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ Load Resume JSON
with open("resume_data.json", "r") as f:
    resume_data = json.load(f)

# ✅ Lazy load models (prevents unnecessary memory consumption)
def get_intent_classifier():
    return pipeline("zero-shot-classification", model="facebook/bart-large-mnli")

def get_sentence_transformer():
    return SentenceTransformer('all-MiniLM-L6-v2')

# ✅ Initialize models when required
intent_classifier = get_intent_classifier()
transformer_model = get_sentence_transformer()

# ✅ Create embeddings for retrieval
resume_context = "\n".join([str(item) for item in resume_data.values()])
context_sentences = resume_context.split("\n")
context_embeddings = transformer_model.encode(context_sentences, convert_to_tensor=True)

# ✅ Request Model
class ChatRequest(BaseModel):
    prompt: str

# ✅ Detect User Intent
def detect_intent(question):
    """Classify intent using Zero-Shot Classification."""
    labels = ["Skill Inquiry", "Project Inquiry", "Work Experience Inquiry", "Education Inquiry", "General"]
    result = intent_classifier(question, candidate_labels=labels)
    return result["labels"][0]

# ✅ Retrieve Context for RAG (Information Retrieval)
def retrieve_relevant_context(question, top_k=3):
    """Retrieve relevant context using sentence embeddings."""
    question_embedding = transformer_model.encode(question, convert_to_tensor=True)
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

# ✅ Structured Responses from JSON
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

    # ✅ Live Projects with Links
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



@app.post("/chat")
def chat(request: ChatRequest):
    """Chatbot API Route"""
    try:
        prompt = request.prompt.strip()
        if not prompt:
            raise HTTPException(status_code=400, detail="Prompt cannot be empty.")

        # ✅ Detect User Intent
        intent = detect_intent(prompt)

        # ✅ Structured JSON Answers
        json_response = answer_from_json(prompt)
        if json_response:
            return {"response": json_response, "intent": intent}

        # ✅ Retrieve Relevant Context for Answering
        relevant_context = retrieve_relevant_context(prompt)

        # ✅ Use Hugging Face Q&A Model (if needed)
        qa_pipeline = pipeline("question-answering", model="deepset/roberta-base-squad2")
        qa_result = qa_pipeline(question=prompt, context=relevant_context)
        answer = qa_result.get("answer", "I'm sorry, I don't have an answer for that.")

        # ✅ Format Response
        response = format_response(answer, relevant_context)
        return {"response": response, "intent": intent}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ✅ Running the FastAPI Server
@app.get("/")
def home():
    return {"message": "FastAPI is running on Render!"}


