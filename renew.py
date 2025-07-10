# renew.py
import os
import sys
import requests
import json
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

# --- 从环境变量中读取机密信息 ---
DP_EMAIL = os.getenv("DP_EMAIL")
DP_PASSWORD = os.getenv("DP_PASSWORD")
BARK_KEY = os.getenv("BARK_KEY") # 新增：读取 Bark Key

# --- DigitalPlat 网站 URL ---
LOGIN_URL = "https://my.digitalplat.com/login.php"
DOMAINS_URL = "https://my.digitalplat.com/clientarea.php?action=domains"

# --- 新增：Bark 通知函数 ---
def send_bark_notification(title, body):
    """发送 Bark 推送通知"""
    if not BARK_KEY:
        print("信息: BARK_KEY 未设置，跳过发送通知。")
        return
    
    print(f"正在发送 Bark 通知: {title}")
    try:
        url = f"https://api.day.app/{BARK_KEY}"
        payload = {
            "title": title,
            "body": body,
            "group": "DigitalPlat Renew" # 通知分组
        }
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        print("Bark 通知已成功发送。")
    except requests.exceptions.RequestException as e:
        print(f"发送 Bark 通知时发生网络错误: {e}")
    except Exception as e:
        print(f"发送 Bark 通知时发生未知错误: {e}")


def run_renewal():
    """主执行函数，运行续期流程"""
    if not DP_EMAIL or not DP_PASSWORD:
        print("错误：环境变量 DP_EMAIL 或 DP_PASSWORD 未设置。")
        sys.exit(1)

    renewed_domains = [] # 新增：用于存储成功续期的域名列表

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        try:
            # --- 1. 登录 ---
            print("正在导航到登录页面...")
            page.goto(LOGIN_URL, wait_until="networkidle")
            print("正在填写登录信息...")
            page.fill("input#username", DP_EMAIL)
            page.fill("input#password", DP_PASSWORD)
            print("正在点击登录按钮...")
            page.click("button#login")
            print("正在等待登录确认...")
            page.wait_for_url("**/clientarea.php", timeout=30000)
            print("登录成功！")

            # --- 2. 导航到域名列表 ---
            print("\n正在导航到域名管理页面...")
            page.goto(DOMAINS_URL, wait_until="networkidle")
            print("已到达域名列表。")

            # --- 3. 查找并处理可续期的域名 ---
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
                        print(f"找到管理按钮，正在点击进入 {domain_name} 的详情页面...")
                        manage_button.click()
                        page.wait_for_load_state("networkidle")
                        renew_link = page.locator("a[href*='renewdomain']")
                        if renew_link.count() > 0:
                            print("找到续期链接，正在点击...")
                            renew_link.click()
                            page.wait_for_load_state("networkidle")
                            order_button = page.locator("button:has-text('Order Now'), button:has-text('Continue')").first
                            if order_button.count() > 0:
                                print("找到订单按钮，正在提交续期订单...")
                                order_button.click()
                                page.wait_for_load_state("networkidle")
                                agree_checkbox = page.locator("input[name='accepttos']")
                                if agree_checkbox.count() > 0:
                                    print("勾选同意条款...")
                                    agree_checkbox.check()
                                checkout_button = page.locator("button#checkout")
                                if checkout_button.count() > 0:
                                    print("正在点击最终确认按钮...")
                                    checkout_button.click()
                                    page.wait_for_load_state("networkidle")
                                    if "Order Confirmation" in page.inner_text("body"):
                                        print(f"成功！域名 {domain_name} 续期订单已提交。")
                                        renewed_domains.append(domain_name) # 修改：记录续期成功的域名
                                    else:
                                        print(f"警告：域名 {domain_name} 最终确认失败，请检查网站流程。")
                                else:
                                    print("未找到最终确认按钮，可能续期流程已变。")
                            else:
                                print("在续期页面未找到订单按钮，可能此域名当前无需续期。")
                        else:
                            print("在此域名详情页未找到续期链接，可能无需续期。")
                        print("正在返回域名列表...")
                        page.goto(DOMAINS_URL, wait_until="networkidle")
                    else:
                        print("未找到管理按钮，跳过此域名。")
            
            # --- 新增：发送成功摘要通知 ---
            print("\n--- 检查完成 ---")
            if not renewed_domains:
                title = "DigitalPlat 续期检查完成"
                body = "所有域名均检查完毕，本次没有需要续期的域名。"
            else:
                title = f"成功续期 {len(renewed_domains)} 个 DigitalPlat 域名"
                body = "续期成功的域名列表:\n" + "\n".join(renewed_domains)
            send_bark_notification(title, body)

        except Exception as e:
            # --- 新增：发送错误通知 ---
            error_message = f"脚本执行时发生错误: {type(e).__name__}"
            print(f"错误: {error_message}")
            page.screenshot(path="error_screenshot.png")
            print("已保存截图 'error_screenshot.png' 以供调试。")
            send_bark_notification("DigitalPlat 续期脚本错误", f"{error_message}\n请检查 GitHub Actions 日志获取详情。")
            sys.exit(1) # 错误退出
        finally:
            print("关闭浏览器...")
            browser.close()

if __name__ == "__main__":
    run_renewal()
