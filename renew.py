# renew.py
# 最后更新时间: 2025-07-10
# 这是一个集成了所有功能的完整版本脚本

import os
import sys
import asyncio
import requests
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

# --- 1. 从环境变量中读取配置 ---
# DigitalPlat 账号信息
DP_EMAIL = os.getenv("DP_EMAIL")
DP_PASSWORD = os.getenv("DP_PASSWORD")

# Bark 通知配置 (支持官方及自建服务器)
BARK_KEY = os.getenv("BARK_KEY")
BARK_SERVER = os.getenv("BARK_SERVER")  # 可选, 您的自建 Bark 服务器地址

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

async def run_renewal():
    """
    主执行函数，运行完整的登录和续期流程。
    """
    # 检查必要的环境变量是否设置
    if not DP_EMAIL or not DP_PASSWORD:
        error_msg = "错误：环境变量 DP_EMAIL 或 DP_PASSWORD 未设置。请在 GitHub Secrets 中配置。"
        print(error_msg)
        send_bark_notification("DigitalPlat 脚本配置错误", error_msg)
        sys.exit(1)

    # 用于存储成功和失败的域名列表
    renewed_domains = []
    failed_domains = []

    async with async_playwright() as p:
        try:
            # --- 步骤 1: 启动浏览器 ---
            # 在 GitHub Actions 等自动化环境中必须使用 headless=True
            # 在本地调试时，可以改为 headless=False 来观察浏览器操作
            print("正在启动浏览器...")
            browser = await p.firefox.launch(headless=True, args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
                '--disable-gpu',
                '--window-size=1920,1080',
            ])
            context = await browser.new_context(
                # 使用与浏览器匹配的 User-Agent
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115.0"
            )
            page = await context.new_page()
            # 添加脚本以隐藏 webdriver 标志，增强反爬虫检测
            await page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

            # --- 步骤 2: 登录 ---
            print("正在导航到登录页面...")
            await page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=60000)

            # --- 步骤 2.1: 等待人机验证自动跳转 ---
            # 这是处理 "Verifying you are human" 的关键步骤。
            # 我们不直接与验证页面交互，而是等待它跳转后，登录页面的关键元素（用户名输入框）出现。
            print("等待人机验证页自动跳转到登录表单...")
            try:
                # 等待用户名输入框出现，最长120秒（根据你环境可调整）
                await page.wait_for_selector("input#username", timeout=120000)
                print("检测到登录表单，已进入账号密码输入页面。")
            except PlaywrightTimeoutError:
                print("超时错误：在120秒内未检测到登录输入框。")
                print("可能原因：1. 人机验证失败；2. 网络问题；3. 网站结构已更改。")
                await page.screenshot(path="login_timeout_error.png")
                send_bark_notification("DigitalPlat 登录失败", "未能自动跳过人机验证，请检查环境或查看截图。")
                sys.exit(1)
            
            # --- 步骤 2.2: 填写表单并登录 ---
            print("正在填写登录信息...")
            await page.fill("input#username", DP_EMAIL)
            await page.fill("input#password", DP_PASSWORD)

            print("正在点击登录按钮...")
            # 点击登录后，等待导航到域名管理页面作为登录成功的标志
            async with page.expect_navigation(wait_until="networkidle", timeout=60000):
                await page.click("button#login")
            
            # 确认登录成功并已跳转到仪表盘
            # 检查页面URL或特定元素来确认
            if "/panel/main" not in page.url:
                print(f"登录失败，当前URL为: {page.url}。可能账号密码错误或登录流程变更。")
                await page.screenshot(path="login_failed_error.png")
                send_bark_notification("DigitalPlat 登录失败", "点击登录后未能跳转到预期的仪表盘页面。")
                sys.exit(1)
            print("登录成功！已进入用户仪表盘。")

            # --- 步骤 3: 导航到域名列表并开始检查 ---
            print("\n正在导航到域名管理页面...")
            await page.goto(DOMAINS_URL, wait_until="networkidle")
            
            # 等待域名列表的表格加载完成
            await page.wait_for_selector("table.table-domains", timeout=30000)
            print("已到达域名列表页面。")

            domain_rows = await page.locator("table.table-domains tbody tr").all()
            if not domain_rows:
                print("未找到任何域名。")
            else:
                print(f"共找到 {len(domain_rows)} 个域名，开始逐一检查...")
                domain_urls = [await row.get_attribute("onclick").split("'")[1] for row in domain_rows]
                base_url = "https://dash.domain.digitalplat.org/"

                for i, domain_url_path in enumerate(domain_urls):
                    # 从 onclick 属性中提取域名和状态
                    row = page.locator(f"tr[onclick*='{domain_url_path}']")
                    domain_name = await row.locator("td:nth-child(1)").inner_text()
                    status = await row.locator("td:nth-child(3)").inner_text()
                    domain_name = domain_name.strip()
                    status = status.strip()
                    print(f"\n[{i+1}/{len(domain_rows)}] 检查域名: {domain_name} (状态: {status})")

                    try:
                        # 直接构造并访问域名管理页面
                        full_domain_url = base_url + domain_url_path
                        print(f"正在访问 {domain_name} 的管理页面: {full_domain_url}")
                        await page.goto(full_domain_url, wait_until="networkidle")

                        # 查找续期链接
                        renew_link = page.locator("a[href*='renewdomain']")
                        if await renew_link.count() > 0:
                            print("找到续期链接，开始续期流程...")
                            # 点击续期链接并等待页面加载
                            async with page.expect_navigation(wait_until="networkidle"):
                                await renew_link.click()

                            # 点击“Order Now”或“Continue”
                            order_button = page.locator("button:has-text('Order Now'), button:has-text('Continue')").first
                            if await order_button.count() > 0:
                                async with page.expect_navigation(wait_until="networkidle"):
                                    await order_button.click()

                                # 同意条款并完成结账
                                agree_checkbox = page.locator("input[name='accepttos']")
                                if await agree_checkbox.count() > 0:
                                    await agree_checkbox.check()
                                
                                checkout_button = page.locator("button#checkout")
                                if await checkout_button.count() > 0:
                                    async with page.expect_navigation(wait_until="networkidle"):
                                        await checkout_button.click()
                                    
                                    # 检查订单确认页面
                                    if "Order Confirmation" in await page.inner_text("body"):
                                        print(f"成功！域名 {domain_name} 续期订单已提交。")
                                        renewed_domains.append(domain_name)
                                    else:
                                        print(f"警告：域名 {domain_name} 最终确认失败，请检查网站流程。")
                                        failed_domains.append(f"{domain_name} (确认失败)")
                                        await page.screenshot(path=f"error_{domain_name}_confirm.png")
                                else:
                                    print(f"警告: 在 {domain_name} 的续期页面找不到 'Checkout' 按钮。")
                                    failed_domains.append(f"{domain_name} (无Checkout按钮)")
                        else:
                            print("在此域名详情页未找到续期链接，可能无需续期。")
                    
                    except Exception as domain_e:
                        print(f"处理域名 {domain_name} 时发生错误: {domain_e}")
                        failed_domains.append(f"{domain_name} (发生异常)")
                        await page.screenshot(path=f"error_{domain_name}.png")
                    
                    finally:
                        # 无论成功与否，都返回域名列表页面以便处理下一个
                        print("正在返回域名列表页面...")
                        await page.goto(DOMAINS_URL, wait_until="networkidle")

            # --- 步骤 4: 发送最终执行结果通知 ---
            print("\n--- 所有域名检查完成 ---")
            if not renewed_domains and not failed_domains:
                title = "DigitalPlat 续期检查完成"
                body = "所有域名均检查完毕，本次没有需要续期或处理失败的域名。"
            else:
                title = f"DigitalPlat 续期报告"
                body = ""
                if renewed_domains:
                    body += f"✅ 成功续期 {len(renewed_domains)} 个域名:\n" + "\n".join(renewed_domains) + "\n\n"
                if failed_domains:
                    body += f"❌ 处理失败 {len(failed_domains)} 个域名:\n" + "\n".join(failed_domains)
            send_bark_notification(title, body.strip())

        except Exception as e:
            # --- 步骤 5: 统一错误处理 ---
            error_message = f"脚本执行时发生严重错误: {type(e).__name__} - {e}"
            print(f"错误: {error_message}")
            # 在捕获异常时，page对象可能不存在，需要检查
            if 'page' in locals():
                await page.screenshot(path="fatal_error_screenshot.png")
                print("已保存截图 'fatal_error_screenshot.png' 以供调试。")
            send_bark_notification("DigitalPlat 脚本严重错误", f"{error_message}\n请检查 GitHub Actions 日志获取详情。")
            sys.exit(1)  # 以错误码退出，让 Actions 知道任务失败了
        finally:
            # --- 步骤 6: 确保浏览器被关闭 ---
            if 'browser' in locals() and browser.is_connected():
                print("关闭浏览器...")
                await browser.close()

if __name__ == "__main__":
    asyncio.run(run_renewal())
