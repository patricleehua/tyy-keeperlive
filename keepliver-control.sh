#!/bin/bash

# keepliver-control.sh - 控制和杀死keepliver进程的脚本

PROCESS_NAME="python -m keepliver.cli auto"
WORK_DIR="/data/tyy-keeperlive"
VENV_PATH="$WORK_DIR/.venv/bin/activate"
LOG_FILE="$WORK_DIR/keepliver.out"
KEEP_BROWSER=10

case "$1" in
    start|启用)
        echo "启动 keepliver..."
        cd "$WORK_DIR" || { echo "无法进入工作目录 $WORK_DIR"; exit 1; }

        # 检查是否已经在运行
        if pgrep -f "$PROCESS_NAME" > /dev/null; then
            echo "keepliver 已经在运行中"
            exit 0
        fi

        # 激活虚拟环境并启动
        source "$VENV_PATH"
        nohup python -m keepliver.cli auto \
            --interval 3000 \
            --captcha-base-url https://your.domain \
            --captcha-port 8000 \
            --browser edge \
            --edgedriver ./drivers/msedgedriver \
            --auto-connect \
            --keep-browser $KEEP_BROWSER \
            --headless > "$LOG_FILE" 2>&1 &

        echo "keepliver 已启动，进程ID: $!"
        ;;
    
    stop|杀死|kill)
        echo "停止 keepliver..."
        # 查找并杀死进程
        PIDS=$(pgrep -f "$PROCESS_NAME")
        if [ -n "$PIDS" ]; then
            echo "找到进程: $PIDS"
            echo "$PIDS" | xargs kill
            sleep 2
            # 再次检查，如果还在运行则强制杀死
            REMAINING=$(pgrep -f "$PROCESS_NAME")
            if [ -n "$REMAINING" ]; then
                echo "强制终止进程..."
                echo "$REMAINING" | xargs kill -9
            fi
            echo "keepliver 已停止"
        else
            echo "没有找到运行的 keepliver 进程"
        fi
        ;;
    
    status|状态)
        if pgrep -f "$PROCESS_NAME" > /dev/null; then
            PID=$(pgrep -f "$PROCESS_NAME")
            echo "keepliver 正在运行，进程ID: $PID"
            # 显示进程详细信息
            ps -f -p "$PID"
            # 显示日志尾部
            if [ -f "$LOG_FILE" ]; then
                echo ""
                echo "最近日志:"
                tail -n 5 "$LOG_FILE"
            fi
        else
            echo "keepliver 未运行"
        fi
        ;;
    
    restart|重启)
        echo "重启 keepliver..."
        "$0" stop
        sleep 3
        "$0" start
        ;;
    
    *)
        echo "使用方法: $0 {start|启用|stop|杀死|kill|status|状态|restart|重启}"
        echo ""
        echo "命令说明:"
        echo "  start, 启用    - 启动 keepliver"
        echo "  stop, 杀死, kill - 停止 keepliver"
        echo "  status, 状态   - 查看 keepliver 状态"
        echo "  restart, 重启  - 重启 keepliver"
        exit 1
        ;;
esac

exit 0
