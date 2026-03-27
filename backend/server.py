from fastapi import FastAPI, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig
from pydantic import EmailStr, BaseModel
import smtplib
from email.mime.text import MIMEText
from fastapi.responses import JSONResponse
from fastapi import HTTPException
import assemblyai as aai
import google.generativeai as genai
import os
import uuid
from typing import List

app = FastAPI()

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Keys
aai.settings.api_key = process.env.AAI_API_KEY
genai.configure(api_key=process.env.GEMINI_API_KEY)

# Transcription + MoM Generation
@app.post("/api/transcribe")
async def transcribe_audio(
    file: UploadFile = File(...),
    agenda: str = Form(""),
):
    file_location = f"temp_audio_{uuid.uuid4()}_{file.filename}"
    with open(file_location, "wb") as f:
        f.write(await file.read())

    transcript_text = ""
    try:
        config = aai.TranscriptionConfig(speaker_labels=True)
        transcript = aai.Transcriber().transcribe(file_location, config)
        transcript_text = " ".join([u.text for u in transcript.utterances])
    finally:
        if os.path.exists(file_location):
            os.remove(file_location)

    prompt = f"""
You are an AI assistant. Based on the following meeting transcript, generate **only** the "Agenda" and "Discussion Summary" sections of the Minutes of Meeting (MoM) in this format and put a line break before the start of Discussion Summary:

Agenda: [in bullet point as numbered list]

Discussion Summary: [in bullet point as numbered list]

Transcript:
{transcript_text}

Agenda provided by user:
{agenda}
"""
    try:
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content(prompt)
        mom_response = response.text.strip()
    except Exception as e:
        mom_response = f"Error generating summary: {str(e)}"

    return {
        "transcript": transcript_text,
        "agenda": agenda,
        "mom": mom_response
    }

class EmailRequest(BaseModel):
    to: List[EmailStr]  # Changed to accept multiple emails
    subject: str
    body: str

@app.post("/api/send-email")
async def send_email(data: EmailRequest):
    sender_email = "ayush524425@gmail.com"
    password = "mtcs kmet bshl lqkh"

    msg = MIMEText(data.body, "plain")
    msg["Subject"] = data.subject
    msg["From"] = sender_email
    msg["To"] = ", ".join(data.to)  # Join the list of email addresses into a string

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender_email, password)
            server.sendmail(sender_email, data.to, msg.as_string())
        return {"message": "Emails sent successfully"}
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=True)
