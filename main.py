import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from groq import Groq
from dotenv import load_dotenv

load_dotenv()
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

client = Groq()

class chatRequest(BaseModel):
    prompt: str

@app.post("/api/chat")
async def chat_endpoint(request: chatRequest):
    try: 
        completion = client.chat.completions.create(
            model = "llama-3.3-70b-versatile",
            messages = [{"role": "user", "content": request.prompt}],
            temperature = 0.7,
        )
        return {"response": completion.choices.message.content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))