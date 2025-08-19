# utils/ai_comment.py
import random
import logging
import requests
import config

logger = logging.getLogger(__name__)

def random_reply():
    candidates = [
        '잘 보고가요~',
        '오늘도 화이팅입니다!',
        '포스팅 감사합니다',
        '오늘도 잘 보고갑니다!!',
        '잘보고가요~ 하트남기고갑니다'
    ]
    return random.choice(candidates)

def call_perplexity(blog_body: str):
    # config should have apiUrl, apiKey, apiModel, system (names same as previous)
    API_URL = getattr(config, 'apiUrl', None)
    if not API_URL:
        logger.warning("AI API URL not configured, falling back to random reply.")
        return random_reply()
    API_KEY = getattr(config, 'apiKey', None)
    payload = {
        "model": getattr(config, 'apiModel', ''),
        "messages": [
            {"role": "system", "content": getattr(config, 'system', '')},
            {"role": "user", "content": blog_body}
        ],
        "temperature": 0.7,
    }
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    try:
        r = requests.post(API_URL, headers=headers, json=payload, timeout=15)
        r.raise_for_status()
        data = r.json()
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        logger.exception("AI API error: %s", e)
        return random_reply()

