# utils/tistory_api.py
import requests
from bs4 import BeautifulSoup
import logging

logger = logging.getLogger(__name__)

def get_latest_post_path(blog_domain: str) -> str:
    """
    blog_domain: ex 'https://example.tistory.com' or 'https://example.tistory.com/'
    Returns: latest post path like '/123' or '123' (caller should normalize)
    """
    if not blog_domain.startswith("http"):
        blog_domain = "https://" + blog_domain
    try:
        resp = requests.get(blog_domain, timeout=10)
        resp.raise_for_status()
    except Exception as e:
        logger.exception("get_latest_post_path failed for %s: %s", blog_domain, e)
        return ""
    soup = BeautifulSoup(resp.text, 'html.parser')
    selectors = ['div.post-item a', 'article a', 'div.list_post a']
    latest_url = None
    for sel in selectors:
        el = soup.select_one(sel)
        if el and el.get('href'):
            latest_url = el.get('href')
            break
    if not latest_url:
        return ""
    return latest_url.lstrip('/')

def fetch_all_comments(blog_url: str, post_number: str):
    """
    Returns list of comment items (dicts) via /m/api/{post}/comment?reverse=true paging
    """
    url_base = f"{blog_url.rstrip('/')}/m/api/{post_number}/comment?reverse=true"
    headers = {"User-Agent": "Mozilla/5.0"}
    all_items = []
    start_id = None
    while True:
        url = f"{url_base}&startId={start_id}" if start_id else url_base
        try:
            r = requests.get(url, headers=headers, timeout=15)
            if r.status_code != 200:
                logger.warning("Non-200 from %s: %s", url, r.status_code)
                break
            data = r.json()
        except Exception as e:
            logger.exception("fetch_all_comments error: %s", e)
            break
        items = data.get("data", {}).get("items", [])
        if not items:
            break
        all_items.extend(items)
        first_id = items[0].get("id")
        if first_id is None:
            break
        start_id = first_id - 1
        if data.get("data", {}).get("isLast") or data.get("data", {}).get("nextId") == 0:
            break
    return all_items

def get_post_body(url: str) -> str:
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
    except Exception as e:
        logger.exception("get_post_body failed: %s", e)
        return ""
    soup = BeautifulSoup(resp.text, "html.parser")
    content_element = soup.select_one("div.contents_style")
    if not content_element:
        # 시안: 다른 스킨들에 대한 fallback
        possible = soup.select_one(".post, .article, .entry-content")
        if possible:
            return possible.get_text(strip=True)
        return ""
    return content_element.get_text(strip=True)

