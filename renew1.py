# 最后更新时间: 2025-07-10
# 这是一个集成了所有登录方案的完整版本脚本

import os
import sys
import time
import pickle
import requests
import json
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from datetime import datetime
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from playwright_stealth import stealth_sync  # 需要先: pip install playwright-stealth

# --- 1. 配置部分 ---
# DigitalPlat 账号信息
DP_EMAIL = os.getenv("DP_EMAIL")
DP_PASSWORD = os.getenv("DP_PASSWORD")

# Bark 通知配置
BARK_KEY = os.getenv("BARK_KEY")
BARK_SERVER = os.getenv("BARK_SERVER")

# 网站 URL
LOGIN_URL = "https://dash.domain.digitalplat.org/auth/login"
DOMAINS_URL = "https://dash.domain.digitalplat.org/panel/main?page=%2Fpanel%2Fdomains"

# Cookie 文件路径
COOKIE_FILE = "digitalplat_cookies.pkl"

# --- 2. 通知函数 ---
def send_bark_notification(title, body):
    """发送 Bark 推送通知"""
    if not BARK_KEY:
        print("信息: BARK_KEY 未设置，跳过发送通知。")
        return

    server_url = BARK_SERVER if BARK_SERVER else "https://api.day.app"
    api_url = f"{server_url.rstrip('/')}/{BARK_KEY}"

    print(f"正在向 Bark 服务器 {server_url} 发送通知: {title}")
    
    try:
        payload = {
            "title": title,
            "body": body,
            "group": "DigitalPlat Renew"
        }
        response = requests.post(api_url, json=payload, timeout=10)
        response.raise_for_status()
        print("Bark 通知已成功发送。")
    except Exception as e:
        print(f"发送 Bark 通知时发生错误: {e}")

# --- 3. Cookie 管理函数 ---
def save_cookies(cookies, filename=COOKIE_FILE):
    """保存 cookies 到文件"""
    try:
        with open(filename, 'wb') as f:
            pickle.dump(cookies, f)
        print(f"Cookies 已保存到 {filename}")
        return True
    except Exception as e:
        print(f"保存 Cookies 失败: {e}")
        return False

def load_cookies(filename=COOKIE_FILE):
    """从文件加载 cookies"""
    try:
        with open(filename, 'rb') as f:
            return pickle.load(f)
    except:
        return None

# --- 4. 登录方案实现 ---
def try_playwright_login():
    """方案1: 使用 Playwright 登录"""
    print("\n尝试使用 Playwright 登录...")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, args=[
            '--disable-blink-features=AutomationControlled',
            '--no-sandbox',
            '--window-size=1920,1080',
        ])
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        
        # 使用 stealth
        stealth_sync(page)
        
        try:
            page.goto(LOGIN_URL, wait_until="networkidle")
            page.wait_for_selector("input#username", timeout=180000)
            
            # 如果成功找到登录表单，保存 cookies
            cookies = context.cookies()
            save_cookies(cookies)
            
            return context, page, True
        except Exception as e:
            print(f"Playwright 登录失败: {e}")
            page.screenshot(path="playwright_error.png")
            return None, None, False
        finally:
            if not page.is_closed():
                page.screenshot(path="final_state.png")

def try_undetected_chrome_login():
    """方案2: 使用 undetected-chromedriver 登录"""
    print("\n尝试使用 undetected-chromedriver 登录...")
    
    options = uc.ChromeOptions()
    options.add_argument('--no-sandbox')
    options.add_argument('--window-size=1920,1080')
    
    try:
        driver = uc.Chrome(options=options)
        driver.get(LOGIN_URL)
        
        # 等待登录表单出现
        username_input = WebDriverWait(driver, 180).until(
            EC.presence_of_element_located((By.ID, "username"))
        )
        
        # 获取并保存 cookies
        cookies = driver.get_cookies()
        save_cookies(cookies)
        
        return driver, True
    except Exception as e:
        print(f"Undetected Chrome 登录失败: {e}")
        if 'driver' in locals():
            driver.save_screenshot("undetected_chrome_error.png")
            driver.quit()
        return None, False

def try_api_login():
    """方案3: 尝试直接调用 API 登录"""
    print("\n尝试使用 API 直接登录...")
    
    session = requests.Session()
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0',
        'Accept': 'application/json',
        'Content-Type': 'application/json'
    }
    
    try:
        response = session.post(
            'https://dash.domain.digitalplat.org/api/auth/login',
            json={'username': DP_EMAIL, 'password': DP_PASSWORD},
            headers=headers
        )
        
        if response.status_code == 200:
            cookies = session.cookies.get_dict()
            save_cookies(cookies)
            return session, True
        else:
            print(f"API 登录失败: HTTP {response.status_code}")
            return None, False
    except Exception as e:
        print(f"API 登录请求失败: {e}")
        return None, False

def try_saved_cookies_login():
    """方案4: 尝试使用保存的 Cookies 登录"""
    print("\n尝试使用已保存的 Cookies 登录...")
    
    cookies = load_cookies()
    if not cookies:
        print("未找到保存的 Cookies")
        return None, False
        
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        
        try:
            # 设置已保存的 cookies
            context.add_cookies(cookies)
            page.goto(LOGIN_URL)
            
            # 检查是否已登录
            if page.locator("input#username").count() == 0:
                print("使用 Cookies 登录成功！")
                return context, page, True
            else:
                print("Cookies 已失效")
                return None, None, False
        except Exception as e:
            print(f"使用 Cookies 登录失败: {e}")
            return None, None, False

# --- 5. 主执行函数 ---
def run_renewal():
    """主执行函数，集成所有登录方案"""
    if not DP_EMAIL or not DP_PASSWORD:
        print("错误：环境变量 DP_EMAIL 或 DP_PASSWORD 未设置。")
        sys.exit(1)

    # 记录开始时间
    start_time = datetime.utcnow()
    print(f"开始执行时间 (UTC): {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 尝试所有登录方案
    login_success = False
    
    # 1. 首先尝试已保存的 cookies
    context, page, login_success = try_saved_cookies_login()
    
    # 2. 如果 cookies 登录失败，尝试 Playwright
    if not login_success:
        context, page, login_success = try_playwright_login()
    
    # 3. 如果 Playwright 失败，尝试 undetected-chromedriver
    if not login_success:
        driver, login_success = try_undetected_chrome_login()
    
    # 4. 如果 undetected-chromedriver 失败，尝试 API
    if not login_success:
        session, login_success = try_api_login()
    
    if not login_success:
        error_message = "所有登录方案都失败了"
        print(f"\n错误: {error_message}")
        send_bark_notification("DigitalPlat 登录失败", error_message)
        sys.exit(1)
    
    # 如果登录成功，继续原有的域名续期逻辑
    try:
        # [这里插入你原有的域名续期代码]
        # 注意根据使用的登录方案（Playwright/Selenium/Requests）调整代码
        pass
        
    except Exception as e:
        error_message = f"执行过程中发生错误: {type(e).__name__}"
        print(f"\n错误: {error_message}")
        send_bark_notification("DigitalPlat 脚本错误", error_message)
        sys.exit(1)
    finally:
        # 清理资源
        if 'driver' in locals() and driver:
            driver.quit()
        if 'context' in locals() and context:
            context.close()
        
        # 计算执行时间
        end_time = datetime.utcnow()
        duration = end_time - start_time
        print(f"\n执行结束时间 (UTC): {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"总执行时长: {duration}")

if __name__ == "__main__":
    run_renewal()
