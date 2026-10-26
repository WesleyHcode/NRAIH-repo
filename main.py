import os
import httpx
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

class topicRequest(BaseModel):
    topic: str

@app.post("/api/analyze-topic")
async def analyze_topic_endpoint(request: topicRequest):
    news_key = os.environ.get("NEWS_API_KEY")
    if not news_key:
        raise HTTPException(status_code=500, detail="NEWS_API_KEY is not in env")

    clean_topic = request.topic.strip()
    clean_key = news_key.strip()

    news_url = f"https://newsapi.org/v2/everything?q={clean_topic}&sortBy=popularity&apiKey={clean_key}"

    async with httpx.AsyncClient() as httpx_client:
        try:
            headers = {"User-Agent": "MRIAH/1.0"}
            news_response = await httpx_client.get(news_url, headers=headers)
            if news_response.status_code != 200:
                raise Exception(f"Server returned status code {news_response.status_code}")
            
            news_data = news_response.json()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Could not fetch news: {str(e)}")

    articles = news_data.get("articles", [])
    if not articles:
        return {"response": "None found"}

    news_summary_ai = ""
    for idx, art in enumerate(articles):
        source_name = art.get("source", {}).get("name", "Unknown Source")
        title = art.get("title", "")
        description = art.get("description", "")
        news_summary_ai += (
            f"-ARTICLE {idx+1}-\n"
            f"SOURCE {source_name}\n"
            f"TITLE {title}\n"
            f"DESCRIPTION: {description}\n"
        )

    try:
        client = Groq()
        completion = client.chat.completions.create(
            model = "llama-3.1-8b-instant",
            messages = [
                {
                    "role": "system",
                    "content": (
                        "You are an expert civic media literacy assistant. You will be provided with "
                        "a list of news articles on a specific topic. Your goal will be to analyze these articles "
                        "and provide a structured markdown report of: \n"
                        "1. Dominant Perspectives: What narrative elements or angles are these sources representing or emphasizing?\n"
                        "2. Potential Bias/Leaning: Identify any political leaning or sensational tone\n"
                        "3. Ommitted Context: What crucial details or opposing points do you think is left out?\n"
                        "Keep your tone nonpartisan and strictly education. Also be self aware in your analysis."
                    )
                },
                {
                    "role": "user",
                    "content": f"Analyze the following recent articles concerning the topic '{request.topic}':\n\n{news_summary_ai}"
                }
            ],
            temperature = 0.3,
        )
        return {"response": completion.choices[0].message.content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class chatRequest(BaseModel):
    prompt: str