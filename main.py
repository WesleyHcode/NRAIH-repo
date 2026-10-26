import os
import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from groq import Groq
from dotenv import load_dotenv
import time
import hashlib

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
        f"{topic_key}|openai/gpt-oss-120b|v1".encode()
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
                        "sortBy": "popularity",
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

    selected_articles = []
    seen_sources = set()

    for article in articles:
        source = article.get("source", {}).get("name", "Unknown Source")

        if source not in seen_sources:
            selected_articles.append(article)
            seen_sources.add(source)

        if len(selected_articles) == 3:
            break

    if not selected_articles:
        return {"response": '{"analyses":[]}'}

    news_summary_ai = ""
    for idx, art in enumerate(selected_articles):
        source_name = art.get("source", {}).get("name", "Unknown Source")
        title = art.get("title", "")[:60]
        description = art.get("description", "")[:80]
        url = art.get("url", "#")
        news_summary_ai += (
            f"-ARTICLE {idx+1}-\n"
            f"SOURCE {source_name}\n"
            f"TITLE {title}\n"
            f"DESCRIPTION: {description}\n"
            f"URL: {url}\n"
        )

    try:
        print("CALLING GROQ NOW")
        client = Groq(timeout = 30.0, max_retries = 0)

        completion = client.chat.completions.create(
            model = "openai/gpt-oss-120b",
            messages = [
                {
                    "role": "system",
                    "content": (
                        "You are an expert civic media literacy assistant. Analyze each provided articles for bias. "
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
        print("GROQ CALL SUCCEEDED")
        result = {"response": completion.choices[0].message.content}
        cache_set(
            f"analysis:{analysis_key}", result, ANALYSIS_CACHE_TTL
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