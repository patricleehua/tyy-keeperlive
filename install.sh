#!/bin/bash

# install.sh - Keepliver 安装脚本
# 用于首次安装项目依赖并配置环境

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

WORK_DIR="/data/tyy-keeperlive"
VENV_DIR="$WORK_DIR/.venv"

show_help() {
    cat << 'EOF'
用法: ./install.sh [选项]

选项:
  -h, --help      显示帮助信息
  -f, --force     强制重新安装（删除现有虚拟环境）
  --skip-venv     跳过创建虚拟环境（使用系统 Python）

示例:
  ./install.sh           # 正常安装
  ./install.sh -f        # 强制重新安装
EOF
}

FORCE=0
SKIP_VENV=0

while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            exit 0
            ;;
        -f|--force)
            FORCE=1
            shift
            ;;
        --skip-venv)
            SKIP_VENV=1
            shift
            ;;
        *)
            echo "未知选项: $1"
            show_help
            exit 1
            ;;
    esac
done

echo -e "${BLUE}=== Keepliver 安装脚本 ===${NC}"
echo ""

# 检查工作目录
if [ ! -d "$WORK_DIR" ]; then
    echo -e "${RED}❌ 工作目录不存在: $WORK_DIR${NC}"
    exit 1
fi

cd "$WORK_DIR"

# 检查 uv 是否安装
if ! command -v uv &> /dev/null; then
    echo -e "${YELLOW}⚠️  uv 未安装，正在安装...${NC}"
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi

# 强制重新安装
if [ "$FORCE" = "1" ] && [ -d "$VENV_DIR" ]; then
    echo -e "${YELLOW}🗑️  删除现有虚拟环境...${NC}"
    rm -rf "$VENV_DIR"
fi

# 创建虚拟环境
if [ "$SKIP_VENV" = "0" ]; then
    if [ ! -d "$VENV_DIR" ]; then
        echo -e "${BLUE}📦 创建虚拟环境...${NC}"
        uv venv "$VENV_DIR"
    else
        echo -e "${GREEN}✅ 虚拟环境已存在: $VENV_DIR${NC}"
    fi

    # 使用虚拟环境的 uv
    UV_CMD="$VENV_DIR/bin/uv"
    PYTHON_CMD="$VENV_DIR/bin/python"
else
    echo -e "${YELLOW}⚠️  跳过虚拟环境，使用系统 Python${NC}"
    UV_CMD="uv"
    PYTHON_CMD="python3"
fi

# 安装项目（wheel 模式）
echo -e "${BLUE}📥 安装 keepliver 项目...${NC}"

# 先打包
if [ ! -f "$WORK_DIR/dist/"*.whl ]; then
    echo -e "${BLUE}📦 打包项目...${NC}"
    "$UV_CMD" build --wheel
fi

# 安装 wheel
WHEEL_FILE=$(ls -t "$WORK_DIR/dist/"*.whl 2>/dev/null | head -1)
if [ -n "$WHEEL_FILE" ]; then
    echo -e "${BLUE}📥 安装: $(basename "$WHEEL_FILE")${NC}"
    "$UV_CMD" pip install "$WHEEL_FILE" --force-reinstall
else
    echo -e "${YELLOW}⚠️  未找到 wheel，使用源码安装...${NC}"
    "$UV_CMD" pip install "$WORK_DIR"
fi

# 检查安装是否成功
echo -e "${BLUE}🔍 验证安装...${NC}"
if "$PYTHON_CMD" -c "import keepliver" 2>/dev/null; then
    echo -e "${GREEN}✅ keepliver 包安装成功${NC}"
else
    echo -e "${RED}❌ keepliver 包安装失败${NC}"
    exit 1
fi

# 检查 CLI 是否可用
if "$PYTHON_CMD" -m keepliver.cli --help &> /dev/null; then
    echo -e "${GREEN}✅ CLI 命令可用${NC}"
else
    echo -e "${YELLOW}⚠️  CLI 命令测试失败${NC}"
fi

echo ""
echo -e "${GREEN}🎉 安装完成！${NC}"
echo ""
echo "接下来请执行:"
echo "  ./keepliver.sh config    # 配置参数"
echo "  ./keepliver.sh 启用      # 启动服务"
