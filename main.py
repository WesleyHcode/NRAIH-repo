import os
import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from groq import Groq
from dotenv import load_dotenv
import time
import hashlib
import json

load_dotenv()
app = FastAPI()
cache = {}
NEWS_CACHE_TTL = 900
ANALYSIS_CACHE_TTL = 900

def cache_get(key):
    entry = cache.get(key)
    if entry is None:
        return None

    expires_at, value = entry

    if time.monotonic() >= expires_at:
        del cache[key]
        return None

    return value

def cache_set(key, value, ttl):
    cache[key] = (time.monotonic() + ttl, value)

def normalize_topic(topic):
    return " ".join(topic.lower().split())

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
    print("BACKEND: ", request.topic)
    news_key = os.environ.get("NEWS_API_KEY")
    if not news_key:
        raise HTTPException(status_code=500, detail="NEWS_API_KEY is not in env")

    clean_topic = request.topic.strip()
    clean_key = news_key.strip()

    topic_key = normalize_topic(clean_topic)

    analysis_key = hashlib.sha256(
        f"{topic_key}|openai/gpt-oss-120b|v2".encode()
    ).hexdigest()

    cached_analysis = cache_get(f"analysis:{analysis_key}")

    if cached_analysis is not None:
        print("CACHE HIT: returning saved analysis")
        return cached_analysis

    print("CACHE MISS: proceeding to NewsAPI and Groq")
    news_cache_key = f"news:{topic_key}" 
    articles = cache_get(news_cache_key)

    if articles is None:
        news_url = f"https://newsapi.org/v2/everything"

        async with httpx.AsyncClient(timeout=10.0) as httpx_client:
            try:
                news_response = await httpx_client.get(
                    news_url, 
                    params = {
                        "q": clean_topic,
                        "sortBy": "relevancy",
                        "pageSize": 30,
                        "language": "en",
                        "apiKey": clean_key
                    },
                    headers = {"User-Agent": "MRIAH/1.0"}
                )

                if news_response.status_code == 429:
                    raise HTTPException(status_code=429, detail=f"NewsAPI rate limit reached. Try again later.")

                news_response.raise_for_status()
                news_data = news_response.json()

                if news_data.get("status") != "ok":
                    raise HTTPException(status_code=502, detail=f"NewsAPI could not complete the search.")
                
                articles = news_data.get("articles", [])
                cache_set(news_cache_key, articles, NEWS_CACHE_TTL)

            except HTTPException:
                raise 
            except httpx.TimeoutException:
                raise HTTPException(status_code=504, detail=f"NewsAPI timed out. Try again.")
            except httpx.HTTPStatusError as e:
                raise HTTPException(status_code=502, detail=f"NewsAPI returned HTTP {e.response.status_code}.")
            except httpx.RequestError:
                raise HTTPException(status_code=502, detail=f"Could not connect to NewsAPI.")

    if not articles:
        return {"response": '{"analyses":[]}'}

    selected = []
    sources = set()

    for article in articles:
        source = article.get("source", {}).get("name", "Unknown Source")

        if source not in sources:
            selected.append(article)
            sources.add(source)

        if len(selected) == 3:
            break

    if not selected:
        return {"response": '{"analyses":[]}'}

    news_summary_ai = ""
    articles_for_ai = []
    for idx, art in enumerate(selected):
        articles_for_ai.append({
            "article_index": idx,
            "source": art.get("source", {}).get("name", "Unknown Source"),
            "title": art.get("title") or "",
            "description": art.get("description") or ""
        })

    prompt_articles = [
        {
            "article_index": i,
            "source": a.get("source", {}).get("name", "Unknown Source"),
            "title": a.get("title", ""),
            "description": a.get("description") or ""
        }
        for i, a in enumerate(selected)
    ]

    schema = {
        "type": "object",
        "properties": {
            "analyses": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "article_index": {"type": "integer"},
                        "bias": {
                            "type": "string",
                            "enum": ["Left", "Lean Left", "Center", "Lean Right", "Right"]
                        },
                        "perspective": {"type": "string"},
                        "context": {"type": "string"},
                    },
                    "required": ["article_index", "bias", "perspective", "context"],
                    "additionalProperties": False
                }
            }
        },
        "required": ["analyses"],
        "additionalProperties": False
    }

    try:
        print("CALLING GROQ NOW")
        client = Groq(timeout = 30.0, max_retries = 0)

        completion = client.chat.completions.create(
            model = "openai/gpt-oss-120b",
            messages = [
                {
                    "role": "system",
                    "content": (
                        "Analyze each news article's framing and missing context. "
                        "Return the requested JSON schema. Keep comments concise, "
                        "ground them in the supplied article information, and use "
                        "each article_index exactly as provided. Do not assume an "
                        "article's political leaning from its source alone."
                    )
                },
                {
                    "role": "user",
                    "content": 
                        f"Analyze these articles about {json.dumps(clean_topic)}:\n"
                        f"{json.dumps(prompt_articles)}"
                }
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "news_analysis",
                    "strict": True,
                    "schema": schema
                }
            },
            temperature=0.1,
            max_completion_tokens=2000,
            reasoning_effort="low"
        )
        print("GROQ CALL SUCCEEDED")
        raw_content = completion.choices[0].message.content
        print("GROQ RAW CONTENT:", repr(raw_content))
        print("GROQ FINISH REASON:", completion.choices[0].finish_reason)

        if not raw_content or not raw_content.strip():
            raise HTTPException(
                status_code=502,
                detail="Groq returned an empty response. Please try again."
            )

        ai_data = json.loads(raw_content)
        final_analyses = []
        seen_indices = set()

        for item in ai_data["analyses"]:
            i = item["article_index"]
            if (not isinstance(i, int)
                or isinstance(i, bool)
                or i < 0
                or i >= len(selected)
                or i in seen_indices
            ):
                continue

            article = selected[i]
            seen_indices.add[i]

            final_analyses.append({
                "source": article.get("source", {}).get("name") or "Unknown Source",
                "title": article.get("title") or "Untitled Article",
                "bias": item["bias"],
                "perspective": item["perspective"],
                "context": item["context"],
                "url": article.get("url") or ""
            })

        if not final_analyses:
            raise HTTPException(
                status_code=502,
                detail="Groq returned an empty response. Please try again."
            )
        result = {"analyses": final_analyses}
        cache_set(
            f"analysis:{analysis_key}",
            result,
            ANALYSIS_CACHE_TTL
        )

        return result
    except Exception as e:
        print(f"Groq error type: {type(e).__name__}")
        print(f"Groq error details: {e}")

        if hasattr(e, "response") and e.response is not None:
            print(f"Status code: {e.status_code}")
            print(f"Response headers: {e.response.headers}")
        if type(e).__name__ == "RateLimitError":
            raise HTTPException(status_code=429, detail=f"AI rate limit reached. Try again later.")
        if type(e).__name__ in ("APITimeoutError", "TimeoutError"):
            raise HTTPException(status_code=504, detail=f"GroqAPI analysis timed out. Try again.")
        raise HTTPException(status_code=502, detail=f"Could not connect to GroqAPI.")
        

class chatRequest(BaseModel):
    prompt: str