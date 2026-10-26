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
        return {"response": '{"analyses":[]}'}

    news_summary_ai = ""
    for idx, art in enumerate(articles[:3]):
        source_name = art.get("source", {}).get("name", "Unknown Source")
        title = art.get("title", "")[:60]
        description = art.get("description", "")[:80]
        url = art.get("url", "#")
        news_summary_ai += (
            f"-ARTICLE {idx+1}-\n"
            f"SOURCE {source_name}\n"
            f"TITLE {title}\n"
            f"DESCRIPTION: {description}\n"
        )

    try:
        client = Groq()
        completion = client.chat.completions.create(
            model = "openai/gpt-oss-120b",
            messages = [
                {
                    "role": "system",
                    "content": (
                        "You are an expert civic media literacy assistant. Analyze the 3 provided articles for bias. "
                        "For EACH article item, you must output a structured evaluation block matching this exact template format. "
                        "You MUST wrap each article analysis strictly inside <analysis_data> and </analysis_data> tags:\n\n"
                        "<analysis_data>\n"
                        "SOURCE: Name of the news source\n"
                        "TITLE: Title of the article\n"
                        "BIAS: Left / Lean Left / Center / Lean Right / Right\n"
                        "PERSPECTIVE: One short sentence describing the primary narrative framing.\n"
                        "CONTEXT: One short sentence highlighting what context or views are missing.\n"
                        "</analysis_data>"
                    )
                },
                {
                    "role": "user",
                    "content": f"Analyze the following recent articles concerning the topic '{request.topic}'. Return the results in JSON format:\n\n{news_summary_ai}"
                }
            ],
            temperature = 0.1,
            max_tokens=400
        )
        return {"response": completion.choices[0].message.content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class chatRequest(BaseModel):
    prompt: str