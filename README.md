# DigitalPlat 免费域名自动续期脚本

这是一个使用 Python 和 Playwright 编写的脚本，旨在自动续期您在 [DigitalPlat](https://dash.domain.digitalplat.org/) 上的免费域名。脚本通过 GitHub Actions 实现云端定时运行，无需您自己准备服务器。

## ✨ 工作原理

脚本会模拟真人操作：
1. 启动一个无头浏览器（Headless Chrome）。
2. 访问 DigitalPlat 登录页面并使用您提供的凭据登录。
3. 导航到域名管理列表。
4. 遍历所有域名，找到可用的续期选项。
5. 自动完成免费续期的整个订单流程。

## 🚀 如何使用

1.  **Fork 本项目**: ...

2.  **获取 Bark Key**: ...

3.  **设置 Secrets**:
    * 在您 Fork 后的仓库中，点击 `Settings` (设置) > `Secrets and variables` > `Actions`。
    * 点击 `New repository secret` 创建以下 Secret：

    **必须的 Secrets:**
    * **`DP_EMAIL`**: 您的 DigitalPlat 登录邮箱。
    * **`DP_PASSWORD`**: 您的 DigitalPlat 登录密码。
    * **`BARK_KEY`**: 您在第2步中获取的 Bark Key。

    **可选的 Secret (用于自建服务器):**
    * **`BARK_SERVER`**: 您自建的 Bark 服务器地址，例如 `https://your.bark.server.com`。**如果您使用的是官方公共服务，请不要创建此 Secret。**

4.  **启用并运行 GitHub Actions**:
    * 进入仓库的 `Actions` 标签页。
    * 在左侧找到 `Renew DigitalPlat Free Domains` 工作流。
    * 该工作流会根据计划（默认每15天）自动运行。
    * 如果您想立即测试，可以点击 `Run workflow` 按钮手动触发一次。运行结束后，您的手机应会收到一条推送通知。

## ⚠️ 注意事项

* **安全性**: 您的账号密码存储在 GitHub 的加密 Secrets 中，脚本通过环境变量读取，不会暴露在代码或日志里，非常安全。
* **脚本健壮性**: 本脚本依赖于 DigitalPlat 网站的页面结构。如果未来网站大幅改版，可能会导致脚本失效。届时需要根据新的页面结构更新脚本中的 CSS 选择器。
