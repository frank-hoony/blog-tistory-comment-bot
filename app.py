import kill_google_root
import random
import subprocess
from flask import Flask, request, render_template, jsonify
from selenium.webdriver.chrome.options import Options
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from bs4 import BeautifulSoup
from collections import defaultdict
import pickle
import requests
import os
import csv
import tempfile
import threading
import atexit
import signal
import sys
import config
from colorama import init, Fore, Style
from logging.handlers import TimedRotatingFileHandler
import logging
import time
from datetime import datetime

app = Flask(__name__)

driver = None
session = None
cookies = None
auth_event = threading.Event()
status_message = "대기 중"
if not os.path.exists('log'):
    os.makedirs('log')

# TimedRotatingFileHandler: 매일 자정마다 로그 파일 분리
log_handler = TimedRotatingFileHandler(
    filename='/home/ec2-user/blog-tistory-comment-bot/log/server.log',      # 날짜별 파일명
    when='midnight',                  # 자정마다 분리
    interval=1,                       # 1일 간격
    backupCount=30,                   # 30일치 백업
    encoding='utf-8'
)
# 로그 포맷 지정
formatter = logging.Formatter(
    '[%(asctime)s] %(levelname)s | %(module)s:%(lineno)d >>> %(message)s'
)
log_handler.setFormatter(formatter)
log_handler.setLevel(logging.INFO)

# Flask app logger에 핸들러 추가
app.logger.addHandler(log_handler)
app.logger.setLevel(logging.INFO)



# 임시: 내 블로그 주소
MY_BLOG_URL =config.myBlogUrl

# 댓글 기록 (중복 댓글 방지용)
# Key: (post_number, profile_url), Value: [comment1, comment2, ...]
replied_comments = defaultdict(list)

# 답글 방문 기록 (중복 방문 방지용)
# Value: set of full post URLs where reply has been made
replied_posts = set()


# 댓글 기록 파일 경로
REPLY_HISTORY_FILE = config.reply_History


# 파일 경로 설정
VISITED_POSTS_FILE = "/home/ec2-user/blog-tistory-comment-bot/visited_posts.txt"
COMMENT_SUCCESS_LOG = "/home/ec2-user/blog-tistory-comment-bot/comment_success_log.txt"
COMMENT_FAIL_LOG = "/home/ec2-user/blog-tistory-comment-bot/comment_fail_log.txt"
DUPLICATE_FAIL_LOG = "/home/ec2-user/blog-tistory-comment-bot/comment_dup_log.txt"

# 방문한 포스트 메모리 로딩
visited_posts = set()

@app.before_request
def log_func_name():
    if request.endpoint!='status':
        app.logger.info(f"접속된 함수명: {request.endpoint}")


def save_cookies_to_file(driver, filename="cookies.pkl"):
    with open(filename, "wb") as f:
        pickle.dump(driver.get_cookies(), f)

def load_cookies_from_file(driver, filename="cookies.pkl"):
    try:
        with open(filename, "rb") as f:
            cookies = pickle.load(f)
            for cookie in cookies:
                # domain 없이도 잘 작동하는 경우가 많지만 필요하면 driver.get() 먼저 호출
                driver.add_cookie(cookie)
    except FileNotFoundError:
        app.logger.info("쿠키 파일이 없습니다. 새로 로그인하세요.")


def create_driver():
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--user-data-dir=/home/ec2-user/blog-tistory-comment-bot/tmp")
    options.add_argument("--disable-dev-shm-usage")
    user_data_dir = os.path.expanduser("/home/ec2-user/blog-tistory-comment-bot/chrome_profile")
    options.add_argument(f"--user-data-dir={user_data_dir}")


#    tmp_profile = tempfile.mkdtemp(prefix="chrome_profile_")
    return webdriver.Chrome(options=options)


### --------- 헬퍼 함수 --------- ###

def wait_for(driver, by, value, timeout=10):
    WebDriverWait(driver, timeout).until(EC.presence_of_element_located((by, value)))

def wait_for_all(driver, conditions, timeout=10):
    WebDriverWait(driver, timeout).until(lambda d: all(len(d.find_elements(by, value)) > 0 for by, value in conditions))

def wait_for_any(driver, conditions, timeout=10):
    WebDriverWait(driver, timeout).until(lambda d: any(len(d.find_elements(by, value)) > 0 for by, value in conditions))

def save_cookies(driver):
    return {cookie['name']: cookie['value'] for cookie in driver.get_cookies()}

# 파일에서 메모리로 읽어오는 함수
def load_replied_comments(filename):
    app.logger.info('------load_replied_comments----')
    if not os.path.exists(filename):
        return
    with open(filename, "r", encoding="utf-8") as f:
        reader = csv.reader(f, delimiter="\t")
        for row in reader:
            if len(row) < 4:
                continue
            post_number, profile_url, nickname, comment = row
            key = (post_number, profile_url)
            replied_comments[key].append(comment)
# 파일에서 메모리로 읽어오는 함수
def load_history(filename):
    global visited_posts
    if not os.path.exists(filename):
        return

    with open(filename, "r", encoding="utf-8") as f:
        visited_posts = set(line.strip() for line in f if line.strip())
    #app.logger.info(visited_posts)
        #reader = csv.reader(f, delimiter="\t")
#        for row in reader:
#            if not row:
#                continue
#            if row[0] == "REPLIED_POST":
#                replied_posts.add(row[1])
#            elif len(row) >= 4:
#                post_number, profile_url, nickname, comment = row
#                replied_comments[(post_number, profile_url)].append(comment)


@app.route('/logout', methods=['POST'])
def log_out():
    global driver, session
    driver.close()
    session.close()
    driver.get('https://www.tistory.com/')

    try:
        # 로그아웃 버튼은 로그인 후에만 보임. (예시: 로그인 상태에서만)
        # 아래는 예시 HTML 구조에 맞춘 코드입니다.
        # 실제 페이지 구조가 다를 수 있으니, 개발자 도구로 실제 버튼의 selector 확인 필요!
        logout_button = driver.find_element(By.CLASS_NAME, 'btn_logout')
        app.logger.info('3!')
        print(logout_button)
        logout_button.click()
        app.logger.info('4!')
        app.logger.info('로그아웃 버튼 클릭 성공!')
    except Exception as e:
        app.logger.info(f'로그아웃 버튼 클릭 실패:{e}')

    return ('', 204)  # No Content

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/status')
def status():
    return jsonify({'status': status_message})


@app.route('/start_login', methods=['POST'])
def start_login():
    kakao_id = request.form['kakao_id']
    kakao_pw = request.form['kakao_pw']

#    auth_event = threading.Event()
    threading.Thread(target=tistory_login, args=(kakao_id, kakao_pw)).start()

    return ('', 204)  # No Content

@app.route('/reply_start', methods=['POST'])
def reply_start():
#    google 크롬으로 댓글 써야함 
#    쿠키로드 하는 기능 
#    구글 크롬의 로그인 상태 유무 부터 만들고 그다음 댓글쓰기 작업 진행  
#    로그인 유무는 request와 같이 로그인 값 여부?
    global status_message
    global session
    max_count = int(request.form.get("max_count", 0))  # 폼에서 전달된 값
    app.logger.info('get_latest_post_url 진입 ')
    postNo=get_latest_post_url(config.myBlogUrl)
#    postNo=430
    maxPostNumber=int(postNo.split('/')[-1])
#    print(maxPostNumber)
#    loop_count = maxPostNumber - max_count + 1

    for i in range(int(maxPostNumber), int(config.minPostNo), -1):
#    for i in range(maxPostNumber, loop_count - 1, -1):
        app.logger.info(f'------------------------{i}-------------------')
        blogUrl=f'{config.myBlogUrl}'
        blogPostNo=f'{i}'
        status_message =f'글번호: {i}, 주소 :{blogUrl}{blogPostNo} 로 이동\n'
        app.logger.info(f'i 포문 {i} : {blogUrl}  --- {blogPostNo}')
        fetch_comments_json(blogUrl,blogPostNo)

    
    app.logger.info(f"-----답변 달기 끝-----")
    status_message = "답변 달기 끝"
    return ('', 204)  # No Content

def create_logged_in_session(cookies):
     
    s = requests.Session()
    for name, value in cookies.items():
        app.logger.info(f"cookies name : {name}")
        app.logger.info(f"cookies value : {value}")
        s.cookies.set(name, value)
    return s


def get_latest_post_url(blog_domain):
    """
    댓글 단 사용자의 블로그 주소로 이동해서 최신 글 URL 추출 (requests 버전)
    """
    app.logger.info(f'Blog_domain : {blog_domain}')
    resp = requests.get(blog_domain)
    soup = BeautifulSoup(resp.text, 'html.parser')

    selectors = [
        'div.post-item a',    # 최신형 스킨
        'article a',          # 기본 스킨
        'div.list_post a'     # 리스트형 스킨
    ]

    latest_url = None
    for selector in selectors:
        element = soup.select_one(selector)
        if element and element.get('href'):
            latest_url = element['href']
            break
    return latest_url.lstrip('/')

def fetch_comments_json(blog_url, post_number):
    global session, driver
#    session golbal 로 불러와서 본문 도 긁고 다해야함
    app.logger.info('----fetch_comment')
    url_base = f"{blog_url}m/api/{post_number}/comment?reverse=true"
    headers = {
        "User-Agent": "Mozilla/5.0"
    }
    all_items=[]
    start_id = None 
    useBlogPost=True
    while True:
        url = f"{url_base}&startId={start_id}" if start_id else url_base
        app.logger.info(f"Fetching URL: {url}")

        try : 
            response = requests.get(url, headers=headers)
        except Exception as e: 
            app.logger.error(f"Request failed: {e}")
            break
        if response.status_code != 200:
            app.logger.error(f"No Blog Post Number tistory")
            useBlogPost=False     
            break
        try:
                data = response.json()
        except Exception as e:
            app.logger.error(f"JSON decode error: {e}, Response text: {response.text}")
            break

        items = data.get("data", {}).get("items",[])
        if not items:
            app.logger.info("No more Comments found. ")
            break
        all_items.extend(items)
        # Prepare for next iteration using the first id in current page - 1
        first_id=items[0].get("id")
        if first_id is None:
            break
        start_id = first_id -1

        if data.get("data", {}).get("isLast") or data.get("data", {}).get("nextId") == 0:
            break
    if useBlogPost:
        for item in all_items:
            writer = item.get("writer", {})
            app.logger.info(f'writer : {item.get("writer",{})}')
            profile_url = writer.get("homepage", "").strip()
            app.logger.info(f'homepage : {writer.get("homepage", "").strip()}')
            nickname = writer.get("name", "").strip()
            app.logger.info(f'nickname : {writer.get("name", "").strip()}')
            comment = item.get("content", "").strip()
            app.logger.info(f'comment : {item.get("content", "").strip()}')
            try : 
                post_url=get_latest_post_url(profile_url)  
            except :
                log_failure(post_number,nickname,comment,'NoSuchBlog','최신 블로그 번호를 못불러옴')
                continue
            app.logger.info(f'post_url : {post_url}')
            blogContent=blog_body(f'{profile_url}/{post_url}')
            #app.logger.info(f'blogContent : {blogContent}')
            app.logger.info(f'test------post_number : {post_number}')
            newPost=f'{profile_url}/{post_url}'
            app.logger.info(f'newPost : {newPost}')
            #app.logger.info(f'blogContent : {blogContent}')
            app.logger.info(f'---방문 포스트 체크 : {newPost}----')
            if is_visited(newPost):
                app.logger.info(f'이미 방문한 포스트 입니다.: {newPost}')
                log_dup(post_number,nickname,"이미 방문한 포스트 : "+comment,newPost)
                continue
                #호출 건수 줄이기위해 댓글 작성하는곳에 옮기기
#            aiComment=call_Perplexity(blogContent)
#            app.logger.info(f'AI comment : {aiComment}')
            

            #success = send_comment_to_blog(driver,newPost,aiComment)
            success,aiComment = send_comment_to_blog(driver,newPost,blogContent)
            if success:
                mark_visited(newPost)
                log_success(post_number,nickname,comment,profile_url,post_url,aiComment)
            else:
                log_failure(post_number,nickname,comment,newPost,aiComment)

        





#파일 write  함수 
def write_to_file(filepath, line):
    with open(filepath, "a", encoding="utf-8") as f:
        f.write(line + "\n")
def is_visited(post_url):
    global visited_posts
    #app.logger.info(f'-------전역 변수 --- {visited_posts}')
    #app.logger.info(f'-------post_url --- {post_url}')
    return post_url in visited_posts

# 댓글 작성 로직 

def send_comment_to_blog(driver,newPost,blogContent):
    try:
        driver.get(newPost)
        wait = WebDriverWait(driver, 10)

        app.logger.info('댓글 작성 완료-------1')
        comment_div = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.tt-cmt[contenteditable='true']")))
        #driver.execute_script("arguments[0].focus();", comment_div)
        
        app.logger.info('댓글 작성 완료-------2')
        # JavaScript를 이용한 이모지 포함 텍스트 삽입

#        js_code = f"arguments[0].innerText = `{aiComment}`;"  # 백틱은 줄바꿈 문자까지 허용
 #       driver.execute_script(js_code, comment_div)
  #      submit_button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button.tt-btn_register")))
   #     submit_button.click()

        comment_div.click()
#        aiComment=call_Perplexity(blogContent)
        app.logger.info('댓글 작성 완료-------3')
        aiComment=random_Reply()
        app.logger.info('댓글 작성 완료-------4')
        app.logger.info(f'AI comment : {aiComment}')
        comment_text =aiComment
        comment_div.send_keys(comment_text)

        app.logger.info('댓글 작성 완료-------5')
        #comment_div.execute_script(comment_text)
        time.sleep(1)
        app.logger.info('댓글 작성 완료-------6')
#        submit_button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button.tt-btn_register")))





        wait.until(lambda d: d.find_element(By.CSS_SELECTOR, "button.tt-btn_register").is_enabled())

        app.logger.info('댓글 작성 완료-------7')
        submit_button = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "button.tt-btn_register"))
        )

        app.logger.info('댓글 작성 완료-------8')

        submit_button.click()

        app.logger.info('댓글 작성 완료-------')
        return True,aiComment
    except Exception as e : 
        app.logger.info('댓글 실패 ')
        app.logger.info(e)
        return False,''



# 성공 시 댓글 작성 및 메모리 탑재 
def mark_visited(post_url):
    global VISITED_POSTS_FILE,visited_posts
    if post_url not in visited_posts:
        app.logger.info(f"Visited add {post_url}")
        visited_posts.add(post_url)
        write_to_file(VISITED_POSTS_FILE, post_url)

def log_success(my_post_id, nickname, comment_text, target_blog_url, target_post_id, sent_text):
    global COMMENT_SUCCESS_LOG
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    line = f"[{timestamp}]:\t{my_post_id}\t{nickname}\t{comment_text}\t{target_blog_url}\t{target_post_id}\t{sent_text}"
    write_to_file(COMMENT_SUCCESS_LOG, line)

def log_dup(my_post_id, nickname, comment_text, target_blog_url):
    global DUPLICATE_FAIL_LOG
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    line = f"[{timestamp}]\t{my_post_id}\t{nickname}\t{comment_text}\t{target_blog_url}"
    write_to_file(DUPLICATE_FAIL_LOG, line)

def log_failure(my_post_id, nickname, comment_text, target_blog_url, target_post_id):
    global COMMENT_FAIL_LOG
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    line = f"[{timestamp}]\t{my_post_id}\t{nickname}\t{comment_text}\t{target_blog_url}\t{target_post_id}"
    write_to_file(COMMENT_FAIL_LOG, line)

def blog_body(url):
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
    except requests.RequestException as e:
        app.logger.info(f"요청 실패: {e}")
        return ""
    soup = BeautifulSoup(response.text, "html.parser")

    content_element = soup.select_one("div.contents_style")
    if not content_element:
        app.logger.info("본문을 찾을 수 없음")
        return ""

    return content_element.get_text(strip=True)

def random_Reply():
    comments = [
    '잘 보고가요~',
    '오늘도 화이팅입니다!',
    '포스팅 감사합니다',
    '오늘도 잘 보고갑니다!!',
    '잘보고가요~ 하트남기고갑니다'
    ]
    random_comment = random.choice(comments)
    return random_comment


def call_Perplexity(blogBody):
    #이후에는 url key는 parameter로 변경 
    API_URL=config.apiUrl
    API_KEY=config.apiKey
    API_MODEL=config.apiModel
    API_ROLE=config.system
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": API_MODEL,
        "messages": [
            {
                "role": "system",
                "content": API_ROLE
            },
            {
                "role":"user",
                "content":blogBody

            }
        ],
        "temperature": 0.7,
        "top_p": 1,
        "max_tokens": 256,
        "stream": False
    }

    response = requests.post(API_URL, headers=headers, json=payload)
    result = response.json()

    return result["choices"][0]["message"]["content"]




### --------- 로그인 프로세스 --------- ###



def tistory_login(kakao_id, kakao_pw):
    global driver, cookies, session, status_message



    if session is not None and is_logged_in(session):
        status_message = "이미 로그인 되어 있음"
        return 
    status_message = "로그인 시도 중..."
    driver.get('https://www.tistory.com/auth/login')

    page_html = driver.page_source

    with open("page.html","w", encoding="utf-8") as file:
        file.write(page_html)
        app.logger.info("html Export")

    try:
        kakao_button = driver.find_element(By.CLASS_NAME, 'btn_login.link_kakao_id')


        kakao_button.click()
        WebDriverWait(driver, 5).until(lambda d: "accounts.kakao.com" in d.current_url)

        wait_for_all(driver, [(By.NAME, 'loginId'), (By.CSS_SELECTOR, 'button.btn_g.highlight.submit')])
        app.logger.info(f"드라이버 주소 : {driver.current_url}")

        driver.find_element(By.NAME, 'loginId').send_keys(kakao_id)
        driver.find_element(By.NAME, 'password').send_keys(kakao_pw)

        checkbox = driver.find_element(By.ID, 'saveSignedIn--4')
        if not checkbox.is_selected():
            driver.execute_script("arguments[0].checked = true;", checkbox)

        driver.find_element(By.CSS_SELECTOR, "button.btn_g.highlight.submit").click()
        status_message = "2차 인증 대기 중"
        app.logger.info("[2차 인증 대기 중] 핸드폰 인증을 완료해주세요.")

        try:
            wait_for(driver, By.CLASS_NAME, 'desc_error', timeout=5)
            error_text = driver.find_element(By.CLASS_NAME, 'desc_error').text
            if "카카오계정을 정확하게 입력해 주세요" in error_text:
                status_message = "로그인 실패: 잘못된 계정 정보"
                return
        except TimeoutException:
            pass

        auth_event.wait()

        wait_for_any(driver, [(By.CLASS_NAME, 'btn_agree'), (By.CSS_SELECTOR, 'button.btn_g.highlight.submit')])
        try:
            agree_button = driver.find_element(By.CLASS_NAME, 'btn_agree')
        except NoSuchElementException:
            agree_button = driver.find_element(By.CSS_SELECTOR, 'button.btn_g.highlight.submit')
        agree_button.click()
        wait_for(driver, By.CLASS_NAME, 'link_tab', timeout=5)

        status_message = "2차 인증 완료, 세션 생성 중..."
        cookies = save_cookies(driver)
        session = create_logged_in_session(cookies)
        status_message = "로그인 완료 및 세션 생성 완료"
        app.logger.info("[로그인 완료]")
        b=is_logged_in(session)
        app.logger.info('[driver - 로그인 쿠키 저장]')
        save_cookies_to_file(driver)
        app.logger.info(f"드라이버 끊기전 세션 여부  : {b}")
        #cleanup()
        app.logger.info("[driver close]")
#        login=is_logged_in(session)
        app.logger.info(f"로그인 여부 : {is_logged_in(session)}")
    except NoSuchElementException :
        app.logger.info ("로그인 버튼이 없음 이미 로그인 된 상태 일 수 있음")
        try : 
            load_cookies_from_file(driver)
            driver.refresh()
            cookies = save_cookies(driver)
            session = create_logged_in_session(cookies)
            status_message = "이전 세션 복구 완료"
        except Exception as f:
            status_message = f"이전 세션 복구 실패: {e}"
    except Exception as e:
        status_message = f"로그인 실패: {e}"

### --------- 종료 처리 --------- ###

@app.route('/check_login')
def check_login():
    global session
    a=is_logged_in(session)
    app.logger.info(f"check_login : {session}")
    if not session:
        return jsonify({'logged_in': False})

    if is_logged_in(session):
        return jsonify({'logged_in': True})
    else:
        return jsonify({'logged_in': False})


def is_logged_in(session):
    url = "https://www.tistory.com/"
    resp = session.get(url) 

    if "로그아웃" in resp.text or "내 블로그" in resp.text:
        return True
    else:
        return False

@app.route('/auth_complete', methods=['POST'])
def auth_complete():
    auth_event.set()
    return ('', 204)

def cleanup():
    global google
    if driver:
        app.logger.info("드라이버 종료 중...")
        driver.quit()

def signal_handler(sig, frame):
    #kill_google_root.kill_root_google_process()
    app.logger.info(f"[시그널 {sig}] 서버 종료 감지됨")
    cleanup()
    sys.exit(0)
#
atexit.register(cleanup)
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def google_init():
    user_data_dir = "/home/ec2-user/blog-tistory-comment-bot/chrome_profile"

    # chrome 프로세스 찾기
    result = subprocess.run(
        ["ps", "-eo", "pid,ppid,command"],
        capture_output=True, text=True
    )
    
    for line in result.stdout.splitlines():
        if "chrome" in line and user_data_dir in line:
            parts = line.strip().split(maxsplit=2)
            pid, ppid = parts[0], parts[1]
            if ppid == "1":  # 상위 프로세스만
                print(f"Killing Chrome root process: {pid}")
                subprocess.run(["kill", "-9", pid])
if __name__ == '__main__':
    #load_replied_comments(REPLY_HISTORY_FILE)
    google_init()
    load_history(VISITED_POSTS_FILE)
    driver = create_driver()
    app.run(host='0.0.0.0', port=5000)

