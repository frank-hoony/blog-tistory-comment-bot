# utils/comments.py
import logging
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
from .file_utils import append_line, load_set_from_file
from typing import Tuple

logger = logging.getLogger(__name__)

VISITED_FILE = "/home/ec2-user/blog-tistory-comment-bot/data/visited_posts.txt"
COMMENT_SUCCESS_LOG = "/home/ec2-user/blog-tistory-comment-bot/data/comment_success_log.txt"
COMMENT_FAIL_LOG = "/home/ec2-user/blog-tistory-comment-bot/data/comment_fail_log.txt"
DUP_LOG = "/home/ec2-user/blog-tistory-comment-bot/data/comment_dup_log.txt"

visited = load_set_from_file(VISITED_FILE)

def is_visited(url: str) -> bool:
    return url in visited

def mark_visited(url: str):
    if url not in visited:
        visited.add(url)
        append_line(VISITED_FILE, url)
        logger.info("Marked visited: %s", url)

def log_success(*args):
    append_line(COMMENT_SUCCESS_LOG, "\t".join(map(str, args)))

def log_fail(*args):
    append_line(COMMENT_FAIL_LOG, "\t".join(map(str, args)))

def log_dup(*args):
    append_line(DUP_LOG, "\t".join(map(str, args)))

def try_wait_for(driver, locator, timeout=6, attempts=3, wait_between=1):
    by, value = locator
    for i in range(attempts):
        try:
            return WebDriverWait(driver, timeout).until(EC.presence_of_element_located((by, value)))
        except TimeoutException:
            logger.debug("wait attempt %d for %s:%s failed", i+1, by, value)
            time.sleep(wait_between)
    raise TimeoutException(f"Element {locator} not found after {attempts} attempts")

def send_comment(driver, post_url: str, comment_text: str) -> Tuple[bool, str]:
    """
    Attempts to open post_url in browser and post comment_text.
    Returns (success: bool, comment_text or error message)
    """
    try:
        driver.get(post_url)
        # wait for editable div
        comment_div = try_wait_for(driver, (By.CSS_SELECTOR, "div.tt-cmt[contenteditable='true']"), timeout=6)
        # click and send keys
        comment_div.click()
        time.sleep(0.3)
        comment_div.send_keys(comment_text)
        # wait until register button enabled
        for i in range(3):
            try:
                WebDriverWait(driver, 6).until(lambda d: d.find_element(By.CSS_SELECTOR, "button.tt-btn_register").is_enabled())
                break
            except Exception:
                time.sleep(0.7)
        submit_btn = try_wait_for(driver, (By.CSS_SELECTOR, "button.tt-btn_register"), timeout=6)
        submit_btn.click()
        logger.info("댓글 전송 성공: %s -> %s", post_url, comment_text)
        return True, comment_text
    except Exception as e:
        logger.exception("댓글 전송 실패 for %s: %s", post_url, e)
        return False, str(e)

