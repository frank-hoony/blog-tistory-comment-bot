# app.py
from flask import Flask, render_template, request, jsonify
import logging
from utils.logging_utils import setup_logging
from utils import browser, tistory_api, comments, ai_comment, file_utils
import config
import threading
import time

logger = setup_logging()
app = Flask(__name__)

# Ensure data directories
import os
os.makedirs("/home/ec2-user/blog-tistory-comment-bot/data", exist_ok=True)

# Simple status string for UI
status_message = {"text": "대기 중"}

@app.before_request
def log_req():
    if request.endpoint != 'status':
        logger.info("접속된 함수명: %s", request.endpoint)

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/status')
def status():
    return jsonify({'status': status_message["text"]})

@app.route('/start_login', methods=['POST'])
def start_login():
    kakao_id = request.form.get('kakao_id')
    kakao_pw = request.form.get('kakao_pw')

    def login_worker():
        try:
            status_message["text"] = "로그인 시도중..."
            # create driver if not exists
            if browser.driver is None:
                browser.create_driver(headless=False)
            browser.tistory_login(kakao_id, kakao_pw, browser.driver)
            status_message["text"] = "로그인 완료(2차 인증 이후)"
        except Exception as e:
            status_message["text"] = f"로그인 실패: {e}"
            logger.exception("start_login exception")
    threading.Thread(target=login_worker, daemon=True).start()
    return ('', 204)

@app.route('/auth_complete', methods=['POST'])
def auth_complete():
    browser.auth_event.set()
    return ('', 204)

@app.route('/check_login')
def check_login():
    # best-effort: try to check if page contains logout
    try:
        if browser.driver:
            # try loading tistory main page and check presence of '로그아웃' text
            browser.driver.get('https://www.tistory.com/')
            time.sleep(1)
            page = browser.driver.page_source
            logged = ("로그아웃" in page) or ("내 블로그" in page)
            browser.driver.save_screenshot("/home/ec2-user/blog-tistory-comment-bot/login_attempt.png")
            with open("/home/ec2-user/blog-tistory-comment-bot/page.html", "w", encoding="utf-8") as f:
                f.write(browser.driver.page_source)

            return jsonify({'logged_in': bool(logged)})
        return jsonify({'logged_in': False})
    except Exception as e:
        logger.exception("check_login")
        return jsonify({'logged_in': False})

@app.route('/reply_start', methods=['POST'])
def reply_start():
    """
    메인 루프: 내 최신 포스트 범위를 가져와서 댓글을 순차 처리합니다.
    필요시 병렬/다중 드라이버 옵션을 넣을 수 있음(리소스 허용 시).
    """
    def worker():
        status_message["text"] = "댓글 달기 시작"
        try:
            # get my latest post
            latest = tistory_api.get_latest_post_path(config.myBlogUrl)
            if not latest:
                status_message["text"] = "내 블로그 최신글을 못불러옴"
                return
            try:
                max_post = int(latest.split('/')[-1])
            except:
                # fallback: parse digits
                max_post = int(''.join(ch for ch in latest if ch.isdigit()) or 0)
            loop_count = max_post - 10
            for i in range(max_post, max(loop_count, 0) - 1, -1):
                status_message["text"] = f"처리중: 글번호 {i}"
                logger.info("처리중 글번호: %s", i)
                # fetch comments
                items = tistory_api.fetch_all_comments(config.myBlogUrl, str(i))
                for item in items:
                    writer = item.get("writer", {})
                    profile_url = writer.get("homepage", "").strip()
                    nickname = writer.get("name", "").strip()
                    comment = item.get("content", "").strip()

                    if not profile_url:
                        continue
                    # get latest post from that profile
                    latest_path = tistory_api.get_latest_post_path(profile_url)
                    if not latest_path:
                        comments.log_fail(i, nickname, "no_latest_post", profile_url)
                        continue
                    target_post_url = f"{profile_url.rstrip('/')}/{latest_path.lstrip('/')}"
                    if comments.is_visited(target_post_url):
                        comments.log_dup(i, nickname, comment, target_post_url)
                        continue

                    body = tistory_api.get_post_body(target_post_url)
                    # AI comment generation (or random)
#                    comment_text = ai_comment.call_perplexity(body) if getattr(config, 'apiUrl', None) else ai_comment.random_reply()
                    comment_text = ai_comment.random_reply()

                    # send via selenium driver
                    if browser.driver is None:
                        browser.create_driver(headless=False)
                    success, info = comments.send_comment(browser.driver, target_post_url, comment_text)
                    if success:
                        comments.mark_visited(target_post_url)
                        comments.log_success(i, nickname, comment, profile_url, latest_path, comment_text)
                    else:
                        comments.log_fail(i, nickname, comment, profile_url, info)

                # short sleep per post to avoid hammering
                time.sleep(0.8)

            status_message["text"] = "답변 달기 끝"
        except Exception as e:
            logger.exception("reply worker exception")
            status_message["text"] = f"오류 발생: {e}"

    threading.Thread(target=worker, daemon=True).start()
    return ('', 204)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)

