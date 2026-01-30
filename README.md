


chromedriver - 谷歌浏览器驱动 需要与chrome版本保持一致
https://googlechromelabs.github.io/chrome-for-testing/known-good-versions-with-downloads.json


安装依赖
uv add selenium

启动脚本

python keepliver/ctyun_auto_selenium.py --chromedriver .\keepliver\chromedriver.exe  --auto-connect 

统一 CLI（推荐）

# 纯手动 测试可用
python keepliver/cli.py login --backend selenium --chromedriver .\keepliver\chromedriver.exe --auto-connect

# 读取配置账号后自动识别ocr，自动输入验证码，手动输入手机验证码  测试可用
python keepliver/cli.py login --backend selenium --chromedriver .\keepliver\chromedriver.exe --login-mode account --secrets .\keepliver\secrets.json --auto-connect

# 读取配置账号后自动识别ocr，自动输入验证码,手动输入手机验证码 无终端模式 测试可用
python keepliver/cli.py login --backend selenium --chromedriver .\keepliver\chromedriver.exe --login-mode account --secrets .\keepliver\secrets.json --headless --auto-connect

# 手动输入验证码 + 手机验证码 ：需chrome 测试可用
python keepliver/cli.py login --backend selenium --chromedriver .\keepliver\chromedriver.exe --login-mode account --secrets .\keepliver\secrets.json --captcha-mode manual --captcha-port 8000

# 每隔 1800 秒（30 分钟）向天翼云发送一次“连接/保活”请求 
python keepliver/cli.py keepalive --config keepliver/config.json --interval 1800

# 单次执行
python keepliver/cli.py once --config keepliver/config.json


secrets.json 示例

{"account":"你的账号或手机号","password":"你的密码"}

验证码 OCR（可选）

pip install ddddocr

手机号验证弹窗（图形验证码 + 短信）

若出现手机号验证弹窗，会自动拉起输入页（同 --captcha-port）
可通过 --phone-verify-template 指定模板，默认使用 keepliver/login-phone-verify.html



telegram bot

curl -s "https://api.telegram.org/bot<TOKEN>/getUpdates" 

send a message from get msg.id