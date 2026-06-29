#!/bin/bash
# Claude Code 父子多层嵌套自适应Loop系统 - Linux启动脚本
# 适配隔离内网、低资源Linux服务器

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo ""
echo "================================================================"
echo "  Claude Code 父子多层嵌套自适应Loop系统"
echo "  Linux/Mac Shell Launcher v2.1"
echo "================================================================"
echo ""

# 检查Python
if command -v python3 &> /dev/null; then
    echo "  [OK] Python: $(python3 --version)"
elif command -v python &> /dev/null; then
    echo "  [OK] Python: $(python --version)"
else
    echo "  [ERROR] Python未安装，请先安装Python 3.9+"
    exit 1
fi

PYTHON=$(command -v python3 || command -v python)

# 运行演示或任务
if [ "$1" = "--demo" ] || [ -z "$1" ]; then
    echo ""
    echo "  启动完整演示模式..."
    echo ""
    $PYTHON run_demo.py
elif [ "$1" = "--task" ] && [ -n "$2" ]; then
    echo ""
    echo "  执行任务: $2"
    echo ""
    $PYTHON orchestrator.py "$2"
else
    echo "  用法:"
    echo "    ./run_demo.sh --demo              # 运行完整演示"
    echo "    ./run_demo.sh --task '任务描述'    # 执行指定任务"
    echo ""
    echo "  示例:"
    echo "    ./run_demo.sh --demo"
    echo "    ./run_demo.sh --task '修复登录接口空指针bug'"
    echo "    ./run_demo.sh --task '从零搭建全栈用户管理系统'"
fi