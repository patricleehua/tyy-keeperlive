#!/bin/bash

# keepliver.sh - Keepliver 完整管理脚本
# 自动管理 Systemd 服务配置

set -e

SERVICE_NAME="keepliver"
SERVICE_FILE="$HOME/.config/systemd/user/${SERVICE_NAME}.service"
CONFIG_FILE="$HOME/.config/keepliver.conf"
WORK_DIR="/data/tyy-keeperlive"
SECRETS_FILE="$WORK_DIR/keepliver/secrets.json"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ==================== 帮助信息 ====================
show_help() {
    cat << 'EOF'
用法: keepliver.sh <命令> [选项]

服务管理:
  install     安装并配置 Systemd 服务（自动运行 install.sh）
  uninstall   卸载服务
  start       启动服务
  stop        停止服务
  restart     重启服务
  status      查看服务状态
  logs        查看实时日志 (Ctrl+C 退出)
  enable      设置开机自启
  disable     取消开机自启

配置管理:
  config      编辑配置参数
  show-config 显示当前配置

快捷命令:
  启用        一键安装+配置+启动+开机自启
  停止        停止服务
  重启        重启服务
  状态        查看状态
  日志        查看日志

安装脚本（独立使用）:
  cd /data/tyy-keeperlive && ./install.sh     # 首次安装依赖
  cd /data/tyy-keeperlive && ./install.sh -f  # 强制重新安装

示例:
  keepliver.sh install      # 首次安装配置
  keepliver.sh 启用         # 快速启用
  keepliver.sh logs         # 查看日志
EOF
}

# ==================== 配置管理 ====================
load_config() {
    # 默认值
    INTERVAL=3000
    CAPTCHA_BASE_URL="https://your.domain"
    CAPTCHA_PORT=8000
    BROWSER="edge"
    EDGEDRIVER="./drivers/msedgedriver"
    CHROMEDRIVER="./drivers/chromedriver"
    AUTO_CONNECT="true"
    HEADLESS="true"
    SECRETS="$SECRETS_FILE"
    LOGIN_MODE="account"

    # 加载用户配置
    if [ -f "$CONFIG_FILE" ]; then
        source "$CONFIG_FILE"
    fi
}

save_config() {
    mkdir -p "$(dirname "$CONFIG_FILE")"
    cat > "$CONFIG_FILE" << EOF
# Keepliver 配置文件
# 修改后执行: keepliver.sh restart

INTERVAL=$INTERVAL
CAPTCHA_BASE_URL="$CAPTCHA_BASE_URL"
CAPTCHA_PORT=$CAPTCHA_PORT
BROWSER="$BROWSER"
EDGEDRIVER="$EDGEDRIVER"
CHROMEDRIVER="$CHROMEDRIVER"
AUTO_CONNECT=$AUTO_CONNECT
HEADLESS=$HEADLESS
SECRETS="$SECRETS"
LOGIN_MODE="$LOGIN_MODE"
EOF
    echo -e "${GREEN}✅ 配置已保存到: $CONFIG_FILE${NC}"
}

edit_config() {
    load_config

    echo -e "${BLUE}=== Keepliver 配置向导 ===${NC}"
    echo "直接回车保持当前值"
    echo ""

    read -p "保活间隔(秒) [$INTERVAL]: " val
    [ -n "$val" ] && INTERVAL=$val

    read -p "验证码服务地址 [$CAPTCHA_BASE_URL]: " val
    [ -n "$val" ] && CAPTCHA_BASE_URL=$val

    read -p "验证码服务端口 [$CAPTCHA_PORT]: " val
    [ -n "$val" ] && CAPTCHA_PORT=$val

    read -p "浏览器类型 (chrome/edge) [$BROWSER]: " val
    [ -n "$val" ] && BROWSER=$val

    read -p "EdgeDriver 路径 [$EDGEDRIVER]: " val
    [ -n "$val" ] && EDGEDRIVER=$val

    read -p "ChromeDriver 路径 [$CHROMEDRIVER]: " val
    [ -n "$val" ] && CHROMEDRIVER=$val

    read -p "无头模式 (true/false) [$HEADLESS]: " val
    [ -n "$val" ] && HEADLESS=$val

    read -p "账户密码文件路径 [$SECRETS]: " val
    [ -n "$val" ] && SECRETS=$val

    read -p "登录模式 (qr/account) [$LOGIN_MODE]: " val
    [ -n "$val" ] && LOGIN_MODE=$val

    save_config

    echo ""
    echo -e "${YELLOW}配置已更新，执行 'keepliver.sh restart' 生效${NC}"
}

show_config() {
    load_config
    echo -e "${BLUE}=== 当前配置 ===${NC}"
    echo "配置文件: $CONFIG_FILE"
    echo ""
    echo "INTERVAL:         $INTERVAL"
    echo "CAPTCHA_BASE_URL: $CAPTCHA_BASE_URL"
    echo "CAPTCHA_PORT:     $CAPTCHA_PORT"
    echo "BROWSER:          $BROWSER"
    echo "EDGEDRIVER:       $EDGEDRIVER"
    echo "CHROMEDRIVER:     $CHROMEDRIVER"
    echo "AUTO_CONNECT:     $AUTO_CONNECT"
    echo "HEADLESS:         $HEADLESS"
    echo "SECRETS:          $SECRETS"
    echo "LOGIN_MODE:       $LOGIN_MODE"
}

# ==================== 服务文件生成 ====================
generate_service_file() {
    load_config

    # 先定义所有变量
    local USER_ID HEADLESS_ARG
    USER_ID=$(id - u)
    HEADLESS_ARG=""
    [ "$HEADLESS" = "true" ] && HEADLESS_ARG="    --headless"

    mkdir -p "$HOME/.config/systemd/user"

    cat > "$SERVICE_FILE" << 'EOF'
[Unit]
Description=Keepliver Auto Service - CTYUN Keepalive
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=WORK_DIR_PLACEHOLDER
Environment="PATH=WORK_DIR_PLACEHOLDER/.venv/bin:/usr/bin:/bin"
Environment="PYTHONUNBUFFERED=1"
Environment="DISPLAY=:0"
Environment="XAUTHORITY=/run/user/UID_PLACEHOLDER/.mutter-Xwaylandauth.Z7YOM3"
Environment="DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/UID_PLACEHOLDER/bus"

ExecStart=WORK_DIR_PLACEHOLDER/.venv/bin/ctyun-keeplive auto \
    --interval INTERVAL_PLACEHOLDER \
    --captcha-base-url CAPTCHA_BASE_URL_PLACEHOLDER \
    --captcha-port CAPTCHA_PORT_PLACEHOLDER \
    --browser BROWSER_PLACEHOLDER \
    --edgedriver EDGEDRIVER_PLACEHOLDER \
    --chromedriver CHROMEDRIVER_PLACEHOLDER \
    --secrets SECRETS_PLACEHOLDER \
    --login-mode LOGIN_MODE_PLACEHOLDER \
    --auto-connect HEADLESS_PLACEHOLDER

Restart=always
RestartSec=60
StartLimitIntervalSec=300
StartLimitBurst=5

TimeoutStopSec=30
KillSignal=SIGTERM

StandardOutput=journal
StandardError=journal

[Install]
WantedBy=default.target
EOF

    # 替换占位符为实际值
    sed -i "s|WORK_DIR_PLACEHOLDER|$WORK_DIR|g" "$SERVICE_FILE"
    sed -i "s|UID_PLACEHOLDER|$USER_ID|g" "$SERVICE_FILE"
    sed -i "s|INTERVAL_PLACEHOLDER|$INTERVAL|g" "$SERVICE_FILE"
    sed -i "s|CAPTCHA_BASE_URL_PLACEHOLDER|$CAPTCHA_BASE_URL|g" "$SERVICE_FILE"
    sed -i "s|CAPTCHA_PORT_PLACEHOLDER|$CAPTCHA_PORT|g" "$SERVICE_FILE"
    sed -i "s|BROWSER_PLACEHOLDER|$BROWSER|g" "$SERVICE_FILE"
    sed -i "s|EDGEDRIVER_PLACEHOLDER|$EDGEDRIVER|g" "$SERVICE_FILE"
    sed -i "s|CHROMEDRIVER_PLACEHOLDER|$CHROMEDRIVER|g" "$SERVICE_FILE"
    sed -i "s|SECRETS_PLACEHOLDER|$SECRETS|g" "$SERVICE_FILE"
    sed -i "s|LOGIN_MODE_PLACEHOLDER|$LOGIN_MODE|g" "$SERVICE_FILE"
    sed -i "s|HEADLESS_PLACEHOLDER|$HEADLESS_ARG|g" "$SERVICE_FILE"
}

# ==================== 服务管理 ====================
install_service() {
    echo -e "${BLUE}=== 安装 Keepliver 服务 ===${NC}"

    # 检查工作目录
    if [ ! -d "$WORK_DIR" ]; then
        echo -e "${RED}❌ 工作目录不存在: $WORK_DIR${NC}"
        exit 1
    fi

    # 运行安装脚本
    if [ -f "$WORK_DIR/install.sh" ]; then
        echo -e "${BLUE}📦 执行安装脚本...${NC}"
        bash "$WORK_DIR/install.sh"
    else
        echo -e "${YELLOW}⚠️  未找到 install.sh，跳过依赖安装${NC}"
        # 检查虚拟环境
        if [ ! -f "$WORK_DIR/.venv/bin/python" ]; then
            echo -e "${RED}❌ 虚拟环境不存在: $WORK_DIR/.venv${NC}"
            echo -e "${YELLOW}请运行: cd $WORK_DIR && ./install.sh${NC}"
            exit 1
        fi
    fi

    # 加载或创建配置
    if [ ! -f "$CONFIG_FILE" ]; then
        echo -e "${YELLOW}首次运行，进入配置向导...${NC}"
        edit_config
    else
        load_config
    fi

    # 生成服务文件
    generate_service_file
    echo -e "${GREEN}✅ 服务文件已生成: $SERVICE_FILE${NC}"

    # 重载 systemd
    systemctl --user daemon-reload
    echo -e "${GREEN}✅ Systemd 配置已重载${NC}"

    echo ""
    echo -e "${GREEN}安装完成！使用以下命令管理服务:${NC}"
    echo "  keepliver.sh start    # 启动服务"
    echo "  keepliver.sh enable   # 开机自启"
    echo "  keepliver.sh 启用     # 一键启用所有"
}

uninstall_service() {
    echo -e "${YELLOW}⚠️  确认卸载 Keepliver 服务? [y/N]${NC}"
    read -r confirm
    if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
        echo "已取消"
        exit 0
    fi

    echo -e "${BLUE}卸载服务...${NC}"
    systemctl --user stop "${SERVICE_NAME}.service" 2>/dev/null || true
    systemctl --user disable "${SERVICE_NAME}.service" 2>/dev/null || true
    rm -f "$SERVICE_FILE"
    systemctl --user daemon-reload

    echo -e "${GREEN}✅ 服务已卸载${NC}"
    echo "配置文件保留在: $CONFIG_FILE"
}

start_service() {
    echo -e "${BLUE}🚀 启动服务...${NC}"
    systemctl --user daemon-reload
    systemctl --user start "${SERVICE_NAME}.service"
    sleep 1
    check_status
}

stop_service() {
    echo -e "${BLUE}🛑 停止服务...${NC}"
    systemctl --user stop "${SERVICE_NAME}.service"
    echo -e "${GREEN}✅ 服务已停止${NC}"
}

restart_service() {
    echo -e "${BLUE}🔄 重启服务...${NC}"
    systemctl --user daemon-reload
    systemctl --user restart "${SERVICE_NAME}.service"
    sleep 1
    check_status
}

check_status() {
    echo -e "${BLUE}=== 服务状态 ===${NC}"
    systemctl --user status "${SERVICE_NAME}.service" --no-pager 2>/dev/null || true

    echo ""
    echo -e "${BLUE}=== 进程检查 ===${NC}"
    if pgrep -f "ctyun-keeplive auto" > /dev/null; then
        echo -e "${GREEN}✅ 进程运行中${NC}"
        pgrep -f "ctyun-keeplive auto"
    else
        echo -e "${RED}❌ 进程未运行${NC}"
    fi
}

show_logs() {
    echo -e "${BLUE}📜 实时日志 (Ctrl+C 退出)...${NC}"
    echo -e "${YELLOW}提示: 使用 -n 100 查看历史日志，如: keepliver.sh logs -n 100${NC}"
    echo ""
    journalctl --user -u "${SERVICE_NAME}.service" -f
}

enable_service() {
    systemctl --user enable "${SERVICE_NAME}.service"
    echo -e "${GREEN}✅ 已设置开机自启${NC}"
}

disable_service() {
    systemctl --user disable "${SERVICE_NAME}.service"
    echo -e "${GREEN}✅ 已取消开机自启${NC}"
}

# 一键启用
quick_start() {
    install_service
    enable_service
    start_service
    echo ""
    echo -e "${GREEN}🎉 Keepliver 已成功启用！${NC}"
}

# ==================== 主程序 ====================
case "$1" in
    install)
        install_service
        ;;
    uninstall)
        uninstall_service
        ;;
    start|启动)
        start_service
        ;;
    stop|停止)
        stop_service
        ;;
    restart|重启)
        restart_service
        ;;
    status|状态)
        check_status
        ;;
    logs|log|日志)
        show_logs
        ;;
    enable)
        enable_service
        ;;
    disable)
        disable_service
        ;;
    config)
        edit_config
        ;;
    show-config)
        show_config
        ;;
    启用)
        quick_start
        ;;
    *)
        show_help
        exit 1
        ;;
esac
