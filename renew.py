# renew.py
# 最后更新时间: 2025-07-09
# 这是一个集成了所有功能的完整版本脚本

import os
import sys
import requests
import json
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

# --- 1. 从环境变量中读取配置 ---
# DigitalPlat 账号信息
DP_EMAIL = os.getenv("DP_EMAIL")
DP_PASSWORD = os.getenv("DP_PASSWORD")

# Bark 通知配置 (支持官方及自建服务器)
BARK_KEY = os.getenv("BARK_KEY")
BARK_SERVER = os.getenv("BARK_SERVER") # 可选, 您的自建 Bark 服务器地址

# --- 2. 网站固定 URL ---
LOGIN_URL = "https://dash.domain.digitalplat.org/auth/login"
DOMAINS_URL = "https://dash.domain.digitalplat.org/panel/main?page=%2Fpanel%2Fdomains"


def send_bark_notification(title, body):
    """
    发送 Bark 推送通知。
    支持自建服务器地址。
    """
    if not BARK_KEY:
        print("信息: BARK_KEY 未设置，跳过发送通知。")
        return

    # 如果用户设置了 BARK_SERVER，则使用该地址，否则使用官方公共地址
    server_url = BARK_SERVER if BARK_SERVER else "https://api.day.app"
    
    # 使用 rstrip('/') 清理末尾可能存在的斜杠，让地址拼接更健壮
    api_url = f"{server_url.rstrip('/')}/{BARK_KEY}"

    print(f"正在向 Bark 服务器 {server_url} 发送通知: {title}")
    
    try:
        payload = {
            "title": title,
            "body": body,
            "group": "DigitalPlat Renew"  # 在 Bark App 中将通知分组
        }
        response = requests.post(api_url, json=payload, timeout=10)
        response.raise_for_status()  # 如果请求失败 (例如 4xx, 5xx 错误) 则抛出异常
        print("Bark 通知已成功发送。")
    except requests.exceptions.RequestException as e:
        print(f"发送 Bark 通知时发生网络错误: {e}")
    except Exception as e:
        print(f"发送 Bark 通知时发生未知错误: {e}")


def run_renewal():
    """
    主执行函数，运行完整的登录和续期流程。
    """
    # 检查必要的环境变量是否设置
    if not DP_EMAIL or not DP_PASSWORD:
        print("错误：环境变量 DP_EMAIL 或 DP_PASSWORD 未设置。请在 GitHub Secrets 中配置。")
        sys.exit(1)

    # 用于存储成功续期的域名列表
    renewed_domains = []

    with sync_playwright() as p:
    browser = p.firefox.launch(headless=False, args=[
        '--disable-blink-features=AutomationControlled',
        '--no-sandbox',
        '--disable-gpu',
        '--window-size=1920,1080',
    ])
    context = browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
    page = context.new_page()
    page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    page.goto("https://dash.domain.digitalplat.org/auth/login", wait_until="networkidle")

        try:
            # --- 步骤 1: 登录 ---
            print("正在导航到登录页面...")
            page.goto(LOGIN_URL, wait_until="networkidle")

            # --- 步骤 1.1: 等待人机验证自动跳转 ---
            print("等待人机验证页自动跳转到输入账号页面...")
            try:
                # 等待用户名输入框出现，最长120秒（根据你环境可调整）
                page.wait_for_selector("input#username", timeout=120000)
                print("检测到登录表单，已进入账号密码输入页面。")
            except PlaywrightTimeoutError:
                print("超时：未检测到登录输入框，可能人机验证页面未通过。")
                page.screenshot(path="login_timeout.png")
                send_bark_notification("DigitalPlat 登录失败", "未能自动跳过人机验证，请检查环境。")
                sys.exit(1)
            
            # --- 步骤 1.2: 填写表单并登录 ---
            print("正在填写登录信息...")
            page.fill("input#username", DP_EMAIL)
            page.fill("input#password", DP_PASSWORD)

            print("正在点击登录按钮...")
            page.click("button#login")
            
            print("正在等待登录确认...")
            page.wait_for_url("**/clientarea.php", timeout=30000)
            print("登录成功！")

            # --- 步骤 2: 导航到域名列表并开始检查 ---
            print("\n正在导航到域名管理页面...")
            page.goto(DOMAINS_URL, wait_until="networkidle")
            print("已到达域名列表。")

            domain_rows = page.locator("tr[onclick*='window.location=']").all()
            if not domain_rows:
                print("未找到任何域名。")
            else:
                print(f"共找到 {len(domain_rows)} 个域名，开始逐一检查...")
                for i, row in enumerate(domain_rows):
                    domain_name = row.locator("td:nth-child(1)").inner_text()
                    status = row.locator("td:nth-child(3)").inner_text()
                    print(f"\n[{i+1}/{len(domain_rows)}] 检查域名: {domain_name} (状态: {status})")

                    manage_button = row.locator("a.btn.btn-sm:has-text('Manage')")
                    if manage_button.count() > 0:
                        print(f"找到管理按钮，正在进入 {domain_name} 的详情页面...")
                        manage_button.click()
                        page.wait_for_load_state("networkidle")
                        
                        renew_link = page.locator("a[href*='renewdomain']")
                        if renew_link.count() > 0:
                            print("找到续期链接，开始续期流程...")
                            renew_link.click()
                            page.wait_for_load_state("networkidle")
                            
                            order_button = page.locator("button:has-text('Order Now'), button:has-text('Continue')").first
                            if order_button.count() > 0:
                                order_button.click()
                                page.wait_for_load_state("networkidle")
                                
                                agree_checkbox = page.locator("input[name='accepttos']")
                                if agree_checkbox.count() > 0:
                                    agree_checkbox.check()
                                
                                checkout_button = page.locator("button#checkout")
                                if checkout_button.count() > 0:
                                    checkout_button.click()
                                    page.wait_for_load_state("networkidle")
                                    
                                    if "Order Confirmation" in page.inner_text("body"):
                                        print(f"成功！域名 {domain_name} 续期订单已提交。")
                                        renewed_domains.append(domain_name)
                                    else:
                                        print(f"警告：域名 {domain_name} 最终确认失败，请检查网站流程。")
                        else:
                            print("在此域名详情页未找到续期链接，可能无需续期。")
                        
                        print("正在返回域名列表...")
                        page.goto(DOMAINS_URL, wait_until="networkidle")

            # --- 步骤 3: 发送最终执行结果通知 ---
            print("\n--- 检查完成 ---")
            if not renewed_domains:
                title = "DigitalPlat 续期检查完成"
                body = "所有域名均检查完毕，本次没有需要续期的域名。"
            else:
                title = f"成功续期 {len(renewed_domains)} 个 DigitalPlat 域名"
                body = "续期成功的域名列表:\n" + "\n".join(renewed_domains)
            send_bark_notification(title, body)

        except Exception as e:
            # --- 步骤 4: 统一错误处理 ---
            error_message = f"脚本执行时发生错误: {type(e).__name__}"
            print(f"错误: {error_message}")
            page.screenshot(path="error_screenshot.png")
            print("已保存截图 'error_screenshot.png' 以供调试。")
            send_bark_notification("DigitalPlat 脚本错误", f"{error_message}\n请检查 GitHub Actions 日志获取详情。")
            sys.exit(1) # 以错误码退出，让 Actions 知道任务失败了
        finally:
            # --- 步骤 5: 确保浏览器被关闭 ---
            print("关闭浏览器...")
            browser.close()


if __name__ == "__main__":
    run_renewal()
