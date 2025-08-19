# utils/browser.py
import os
import pickle
import threading
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import logging
from typing import Dict
import shutil

logger = logging.getLogger(__name__)

# 전역 상태(앱에서 import해서 사용)
driver = None
session_cookies = None
auth_event = threading.Event()

COOKIE_FILE = "/home/ec2-user/blog-tistory-comment-bot/data/cookies.pkl"
PROFILE_DIR = "/home/ec2-user/blog-tistory-comment-bot/chrome_profile"
if os.path.exists(PROFILE_DIR):
    shutil.rmtree(PROFILE_DIR, ignore_errors=True)


def create_driver(headless=True, user_data_dir=PROFILE_DIR):
    global driver
    logger.info(f"TEST-------{user_data_dir}")
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument(f"--user-data-dir={user_data_dir}")
    # Add other options as needed

    driver = webdriver.Chrome(options=options)
   # driver.set_page_load_timeout(30)
    return driver

def save_cookies_to_file(driver_obj, filename=COOKIE_FILE):
    ensure_dir = os.path.dirname(filename)
    if ensure_dir:
        os.makedirs(ensure_dir, exist_ok=True)
    with open(filename, "wb") as f:
        pickle.dump(driver_obj.get_cookies(), f)
    logger.info(f"Saved cookies to {filename}")

def load_cookies_from_file(driver_obj, filename=COOKIE_FILE):
    if not os.path.exists(filename):
        logger.info("Cookie file not found.")
        return
    with open(filename, "rb") as f:
        cookies = pickle.load(f)
    for cookie in cookies:
        # domain issue: ensure page loaded for domain first if needed
        try:
            driver_obj.add_cookie(cookie)
        except Exception:
            pass
    logger.info("Loaded cookies into driver (best-effort).")

def wait_for_element(driver_obj, by, value, timeout=10):
    return WebDriverWait(driver_obj, timeout).until(EC.presence_of_element_located((by, value)))

# 로그인 프로세스 (기존 로직을 모듈로 옮김)
def tistory_login(kakao_id: str, kakao_pw: str, driver_obj=None):
    """
    브라우저에서 직접 로그인 수행. (2차 인증은 핸드폰에서 완료 후 /auth_complete 호출로 auth_event.set())
    Returns: driver_obj (running) and saved cookies dict
    """
    global driver, session_cookies
    if driver_obj is None:
        if driver is None:
            driver = create_driver(headless=False)
        driver_obj = driver

    try:
        driver_obj.get('https://www.tistory.com/auth/login')
        # 기존 페이지의 카카오 로그인 버튼 클릭 등(예외처리 포함)
        kakao_button = driver_obj.find_element(By.CLASS_NAME, 'btn_login.link_kakao_id')
        kakao_button.click()
        WebDriverWait(driver_obj, 10).until(lambda d: "accounts.kakao.com" in d.current_url)

        WebDriverWait(driver_obj, 10).until(lambda d: d.find_element(By.NAME, 'loginId'))
        driver_obj.find_element(By.NAME, 'loginId').send_keys(kakao_id)
        driver_obj.find_element(By.NAME, 'password').send_keys(kakao_pw)

        try:
            checkbox = driver_obj.find_element(By.ID, 'saveSignedIn--4')
            if not checkbox.is_selected():
                driver_obj.execute_script("arguments[0].checked = true;", checkbox)
        except Exception:
            pass

        driver_obj.find_element(By.CSS_SELECTOR, "button.btn_g.highlight.submit").click()

        logger.info("[로그인] 2차 인증 대기 중. 핸드폰 인증을 진행해주세요.")
        # 외부에서 /auth_complete로 auth_event.set() 호출하면 계속 진행
        auth_event.clear()
        auth_event.wait(timeout=300)  # 타임아웃 5분(필요시 조정)

        # 인증 완료 후 동의/다음 단계 처리
        #WebDriverWait(driver_obj, 10).until(lambda d: "tistory.com" in d.current_url or "accounts.kakao.com" not in d.current_url)
        try:
            agree_button = driver_obj.find_element(By.CLASS_NAME, 'btn_agree')
        except NoSuchElementException:
            agree_button = driver_obj.find_element(By.CSS_SELECTOR, 'button.btn_g.highlight.submit')
        agree_button.click()
        time.sleep(1)
        try:
            save_cookies_to_file(driver_obj)
        except Exception as e:
            logger.exception("쿠키 저장 실패: %s", e)

        session_cookies = {c['name']: c['value'] for c in driver_obj.get_cookies()}
        logger.info("로그인 완료 및 세션 쿠키 수집.")
        return driver_obj, session_cookies
    except Exception as e:
        logger.exception("로그인 실패: %s", e)
        raise

