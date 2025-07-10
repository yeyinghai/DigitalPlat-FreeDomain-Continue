# renew.py
import os
import sys
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

# --- 从环境变量中读取机密信息 ---
# 为了安全，账号密码将作为 GitHub Secrets 传入
DP_EMAIL = os.getenv("DP_EMAIL")
DP_PASSWORD = os.getenv("DP_PASSWORD")

# --- DigitalPlat 网站 URL ---
LOGIN_URL = "https://my.digitalplat.com/login.php"
DOMAINS_URL = "https://my.digitalplat.com/clientarea.php?action=domains"

def run_renewal():
    """主执行函数，运行续期流程"""

    # 检查账号密码是否已设置
    if not DP_EMAIL or not DP_PASSWORD:
        print("错误：环境变量 DP_EMAIL 或 DP_PASSWORD 未设置。请在 GitHub Secrets 中配置。")
        sys.exit(1)

    with sync_playwright() as p:
        # 启动一个 Chromium 浏览器实例
        # headless=True 表示在后台运行，对于 GitHub Actions 是必须的
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
            # 使用 CSS 选择器定位输入框并填写
            page.fill("input#username", DP_EMAIL)
            page.fill("input#password", DP_PASSWORD)

            print("正在点击登录按钮...")
            page.click("button#login")
            
            # 等待登录成功后的页面跳转
            print("正在等待登录确认...")
            page.wait_for_url("**/clientarea.php", timeout=30000)
            print("登录成功！")

            # --- 2. 导航到域名列表 ---
            print("\n正在导航到域名管理页面...")
            page.goto(DOMAINS_URL, wait_until="networkidle")
            print("已到达域名列表。")

            # --- 3. 查找并处理可续期的域名 ---
            # 找到所有域名行，DigitalPlat 使用 <tr> 标签包裹每个域名信息
            domain_rows = page.locator("tr[onclick*='window.location=']").all()
            if not domain_rows:
                print("未找到任何域名。")
                return

            print(f"共找到 {len(domain_rows)} 个域名，开始逐一检查...")
            
            renewed_count = 0
            for i, row in enumerate(domain_rows):
                # 提取域名和状态
                domain_name = row.locator("td:nth-child(1)").inner_text()
                status = row.locator("td:nth-child(3)").inner_text()
                
                print(f"\n[{i+1}/{len(domain_rows)}] 检查域名: {domain_name} (状态: {status})")

                # DigitalPlat 中可续期的域名链接通常包含 'Renew' 字样
                # 我们直接寻找可以点击的管理按钮或续期链接
                manage_button = row.locator("a.btn.btn-sm:has-text('Manage')")
                
                if manage_button.count() > 0:
                    print(f"找到管理按钮，正在点击进入 {domain_name} 的详情页面...")
                    manage_button.click()
                    page.wait_for_load_state("networkidle")

                    # 在域名详情页，寻找续期链接
                    # 免费续期链接通常在 'management' actions 下
                    renew_link = page.locator("a[href*='renewdomain']")
                    
                    if renew_link.count() > 0:
                        print("找到续期链接，正在点击...")
                        renew_link.click()
                        page.wait_for_load_state("networkidle")

                        # --- 4. 完成续期订单 ---
                        # 在续期页面，通常需要确认价格为0.00并提交
                        # 找到免费的续期选项（例如 "0 Days @ $0.00 USD"）
                        # 这里用一个通用方法，直接找 "Order Now" 或 "Continue"
                        order_button = page.locator("button:has-text('Order Now'), button:has-text('Continue')").first
                        if order_button.count() > 0:
                            print("找到订单按钮，正在提交续期订单...")
                            order_button.click()
                            page.wait_for_load_state("networkidle")
                            
                            # 最后一步：确认并完成订单
                            # 通常会有一个 "I have read and agree..." 的复选框
                            agree_checkbox = page.locator("input[name='accepttos']")
                            if agree_checkbox.count() > 0:
                                print("勾选同意条款...")
                                agree_checkbox.check()
                            
                            checkout_button = page.locator("button#checkout")
                            if checkout_button.count() > 0:
                                print("正在点击最终确认按钮...")
                                checkout_button.click()
                                page.wait_for_load_state("networkidle")
                                
                                # 检查订单确认信息
                                if "Order Confirmation" in page.inner_text("body"):
                                    print(f"成功！域名 {domain_name} 续期订单已提交。")
                                    renewed_count += 1
                                else:
                                    print(f"警告：域名 {domain_name} 最终确认失败，请检查网站流程。")
                            else:
                                print("未找到最终确认按钮，可能续期流程已变。")
                        else:
                            print("在续期页面未找到订单按钮，可能此域名当前无需续期。")

                    else:
                        print("在此域名详情页未找到续期链接，可能无需续期。")
                    
                    # 返回域名列表页面以检查下一个
                    print("正在返回域名列表...")
                    page.goto(DOMAINS_URL, wait_until="networkidle")
                else:
                    print("未找到管理按钮，跳过此域名。")

            print(f"\n--- 检查完成 ---")
            print(f"总共成功提交了 {renewed_count} 个域名的续期请求。")

        except PlaywrightTimeoutError:
            print("错误：页面加载超时。可能是网站响应缓慢或页面结构已更改。")
            page.screenshot(path="error_screenshot.png")
            print("已保存截图 'error_screenshot.png' 以供调试。")
            sys.exit(1)
        except Exception as e:
            print(f"发生未知错误: {e}")
            page.screenshot(path="error_screenshot.png")
            print("已保存截图 'error_screenshot.png' 以供调试。")
            sys.exit(1)
        finally:
            print("关闭浏览器...")
            browser.close()

if __name__ == "__main__":
    run_renewal()
