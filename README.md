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

#### 自动保活参数示例（Windows）

```powershell
# 指定驱动与登录模式（账号密码登录）
python -m keepliver.cli auto --interval 1800 `
  --chromedriver .\\drivers\\chromedriver.exe `
  --login-mode account --secrets .\\keepliver\\secrets.json --auto-connect

# 使用 Edge
python -m keepliver.cli auto --interval 1800 `
  --browser edge --edgedriver .\\drivers\\msedgedriver.exe --auto-connect
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

#### 自动保活参数示例（Linux）

```bash
# 指定驱动与登录模式（账号密码登录）
python -m keepliver.cli auto --interval 1800 \\
  --chromedriver ./drivers/chromedriver \\
  --login-mode account --secrets ./keepliver/secrets.json --auto-connect

# 使用 Edge
python -m keepliver.cli auto --interval 1800 \\
  --browser edge --edgedriver ./drivers/msedgedriver --auto-connect
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
