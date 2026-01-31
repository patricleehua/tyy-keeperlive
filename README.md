# tyy-keeperlive

## 环境准备

- Python: 3.12+
- 依赖安装：
  - 使用 uv：`uv sync`
  - 或使用 pip：`pip install -e .`

## 驱动准备（Windows / Linux）

- ChromeDriver 需与 Chrome 版本一致：
  - https://googlechromelabs.github.io/chrome-for-testing/known-good-versions-with-downloads.json
- EdgeDriver 需与 Edge 版本一致：
  - https://developer.microsoft.com/zh-cn/microsoft-edge/tools/webdriver/

建议把驱动放在项目根目录下的 `drivers/`：

```
./drivers/chromedriver.exe
./drivers/msedgedriver.exe
```

Linux 下注意赋予执行权限：

```bash
chmod +x ./drivers/chromedriver
chmod +x ./drivers/msedgedriver
```

---

## Windows 示例

### 登录抓取配置（selenium）

```powershell
# 纯手动模式
python -m keepliver.cli login --backend selenium --chromedriver .\drivers\chromedriver.exe --auto-connect

# 账号密码 + OCR + 手动短信验证码
python -m keepliver.cli login --backend selenium --chromedriver .\drivers\chromedriver.exe --login-mode account --secrets .\keepliver\secrets.json --auto-connect

# Edge
python -m keepliver.cli login --backend selenium --browser edge --edgedriver .\drivers\msedgedriver.exe --auto-connect
```

### 自动保活（推荐）

```powershell
# config.json 不存在会自动登录并生成；保活失败会自动重登并重发一次
python -m keepliver.cli auto --interval 1800
```

#### 自动保活参数完整说明

```
--config                config.json 路径（默认 keepliver/config.json）
--interval              保活间隔秒数（默认 1800）
--backend               登录后端：selenium / playwright（默认 selenium）
--profile-dir           浏览器 profile 目录（默认自动选择）
--timeout               登录等待超时秒数（默认 600）
--chromedriver          ChromeDriver 路径（默认自动探测）
--chrome-binary         Chrome 浏览器二进制路径（可选）
--edgedriver            EdgeDriver 路径（默认自动探测）
--edge-binary           Edge 浏览器二进制路径（可选）
--browser               selenium 浏览器：chrome / edge（默认 chrome）
--auto-connect          自动点击“连接”
--login-mode            登录模式：qr / account（默认 qr）
--account               账号/手机号/邮箱
--password              密码
--secrets               secrets.json 路径（可写账号/密码/Telegram）
--headless              无界面模式（首次登录不建议）
--force-headless        强制 headless（即使首次登录）
--captcha-mode          验证码模式：auto / manual / off（默认 auto）
--captcha-timeout       验证码等待秒数（默认 120）
--captcha-port          验证码输入页端口（默认 8000，0=控制台输入）
--captcha-base-url      验证码输入页基础 URL（Telegram 消息中用于可点击链接，默认 http://127.0.0.1）
--phone-verify-template 手机验证输入页模板
--telegram-token        Telegram Bot Token
--telegram-chat-id      Telegram Chat ID
--telegram-timeout      Telegram 等待验证码秒数（默认与 captcha-timeout 一致，默认 120）
--telegram-test         启动时发送一条测试消息
```

#### 验证码与 Telegram 逻辑说明

- 图形验证码默认启用 OCR（`--captcha-mode auto`）。识别失败会回退到输入页（`--captcha-port`）。
- 手机验证短信：如果配置了 Telegram，会先等待 `--telegram-timeout` 秒接收验证码（默认 120s）；若超时，会发送一条消息提示超时，并给出输入页 URL（`<captcha-base-url>:<captcha-port>/`，默认 `http://127.0.0.1:8000/`），用户可手动输入。本机控制台仍显示 `127.0.0.1` 地址。
- 如需远程输入页，请确保端口可访问（例如使用端口映射或 SSH 隧道）。

#### 自动保活参数示例（Windows）

```powershell
# 指定驱动与登录模式（账号密码登录）
python -m keepliver.cli auto --interval 1800 `
  --chromedriver .\\drivers\\chromedriver.exe `
  --login-mode account --secrets .\\keepliver\\secrets.json --auto-connect

# 使用 Edge
python -m keepliver.cli auto --interval 1800 `
  --browser edge --edgedriver .\\drivers\\msedgedriver.exe --auto-connect

# Telegram 消息中的输入页使用公网域名
python -m keepliver.cli auto --interval 1800 `
  --captcha-base-url https://your.domain --captcha-port 8000
```

### 单次/循环保活

```powershell
python -m keepliver.cli once --config keepliver\config.json
python -m keepliver.cli keepalive --config keepliver\config.json --interval 1800
```

---

## Linux 示例

### 登录抓取配置（selenium）

```bash
# 纯手动模式
python -m keepliver.cli login --backend selenium --chromedriver ./drivers/chromedriver --auto-connect

# 账号密码 + OCR + 手动短信验证码
python -m keepliver.cli login --backend selenium --chromedriver ./drivers/chromedriver --login-mode account --secrets ./keepliver/secrets.json --auto-connect

# Edge
python -m keepliver.cli login --backend selenium --browser edge --edgedriver ./drivers/msedgedriver --auto-connect
```

### 自动保活（推荐）

```bash
python -m keepliver.cli auto --interval 1800
```

#### 后台运行 / 查看日志 / 停止

```bash
# 后台运行

nohup python -m keepliver.cli auto --interval 1800 --captcha-base-url https://your.domain --captcha-port 8000 --browser edge --edgedriver ./drivers/msedgedriver --auto-connect --headless  > keepliver.out 2>&1 &


# 查看运行状态
ps -ef | grep keepliver

# 查看日志
tail -n 200 keepliver.out

# 停止（替换为实际 PID）
kill <PID>
```

#### systemd 开机自启（Linux）

```bash
sudo tee /etc/systemd/system/ctyun-keepalive.service > /dev/null <<'EOF'
[Unit]
Description=CTYUN Keepalive (auto)
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/data/tyy-keeperlive
ExecStart=/data/tyy-keeperlive/.venv/bin/python -m keepliver.cli auto --interval 1800 --captcha-base-url https://your.domain --captcha-port 8000 --browser edge --edgedriver ./drivers/msedgedriver --auto-connect --headless
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable ctyun-keepalive.service
sudo systemctl start ctyun-keepalive.service
sudo systemctl status ctyun-keepalive.service
```

#### 自动保活参数完整说明

```
--config                config.json 路径（默认 keepliver/config.json）
--interval              保活间隔秒数（默认 1800）
--backend               登录后端：selenium / playwright（默认 selenium）
--profile-dir           浏览器 profile 目录（默认自动选择）
--timeout               登录等待超时秒数（默认 600）
--chromedriver          ChromeDriver 路径（默认自动探测）
--chrome-binary         Chrome 浏览器二进制路径（可选）
--edgedriver            EdgeDriver 路径（默认自动探测）
--edge-binary           Edge 浏览器二进制路径（可选）
--browser               selenium 浏览器：chrome / edge（默认 chrome）
--auto-connect          自动点击“连接”
--login-mode            登录模式：qr / account（默认 qr）
--account               账号/手机号/邮箱
--password              密码
--secrets               secrets.json 路径（可写账号/密码/Telegram）
--headless              无界面模式（首次登录不建议）
--force-headless        强制 headless（即使首次登录）
--captcha-mode          验证码模式：auto / manual / off（默认 auto）
--captcha-timeout       验证码等待秒数（默认 120）
--captcha-port          验证码输入页端口（默认 8000，0=控制台输入）
--captcha-base-url      验证码输入页基础 URL（Telegram 消息中用于可点击链接，默认 http://127.0.0.1）
--phone-verify-template 手机验证输入页模板
--telegram-token        Telegram Bot Token
--telegram-chat-id      Telegram Chat ID
--telegram-timeout      Telegram 等待验证码秒数（默认与 captcha-timeout 一致，默认 120）
--telegram-test         启动时发送一条测试消息
```

#### 验证码与 Telegram 逻辑说明

- 图形验证码默认启用 OCR（`--captcha-mode auto`）。识别失败会回退到输入页（`--captcha-port`）。
- 手机验证短信：如果配置了 Telegram，会先等待 `--telegram-timeout` 秒接收验证码（默认 120s）；若超时，会发送一条消息提示超时，并给出输入页 URL（`<captcha-base-url>:<captcha-port>/`，默认 `http://127.0.0.1:8000/`），用户可手动输入。本机控制台仍显示 `127.0.0.1` 地址。
- 如需远程输入页，请确保端口可访问（例如使用端口映射或 SSH 隧道）。

#### 自动保活参数示例（Linux）

```bash
# 指定驱动与登录模式（账号密码登录）
python -m keepliver.cli auto --interval 1800 \\
  --chromedriver ./drivers/chromedriver \\
  --login-mode account --secrets ./keepliver/secrets.json --auto-connect

# 使用 Edge
python -m keepliver.cli auto --interval 1800 \\
  --browser edge --edgedriver ./drivers/msedgedriver --auto-connect

# Telegram 消息中的输入页使用公网域名
python -m keepliver.cli auto --interval 1800 \\
  --captcha-base-url https://your.domain --captcha-port 8000
```

### 单次/循环保活

```bash
python -m keepliver.cli once --config keepliver/config.json
python -m keepliver.cli keepalive --config keepliver/config.json --interval 1800
```

### Linux 备注（Chrome 兼容性）

- 部分 Linux 环境下 Chrome 可能存在兼容问题。
- 可优先用 Edge（测试可用）。
- 或自行测试 Chromium + 匹配版本的 chromedriver。

---

## secrets.json 示例

```json
{
  "account": "你的账号或手机号",
  "password": "你的密码",
  "telegram_token": "可选的 Telegram Bot Token",
  "telegram_chat_id": "可选的 Telegram Chat ID"
}
```

## 验证码 OCR（可选）

```bash
pip install ddddocr
```

## 手机号验证弹窗（图形验证码 + 短信）

若出现手机号验证弹窗，会自动拉起输入页（同 `--captcha-port`）
可通过 `--phone-verify-template` 指定模板，默认使用 `keepliver/login-phone-verify.html`
