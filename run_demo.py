"""
Claude Code 父子多层嵌套自适应Loop系统 - 完整演示
====================================================
演示两种任务模式：
  1. 简单任务：修复Bug → 极速直出
  2. 复杂任务：全栈开发 → 多层嵌套Loop调度
"""

import sys
import io

# 修复Windows GBK编码问题
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

import os
import time
import json
from pathlib import Path

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from config import Colors, DEMO_PROJECT_DIR
from utils import print_banner, print_phase, print_step, print_success, print_error, print_info, print_warning, Timer
from orchestrator import Orchestrator


def demo_simple_task():
    """演示1：简单任务 - 极速直出模式"""
    print_banner("📋 演示一：简单任务模式（极速直出）", Colors.GREEN)

    task = "修复登录接口空指针bug - 当用户名为空时抛出NullPointerException"

    print(f"\n{Colors.BOLD}任务描述:{Colors.END} {task}")
    print(f"{Colors.BOLD}预期路由:{Colors.END} {Colors.GREEN}简单任务 → 直接执行 → 零子进程{Colors.END}")
    print()

    orchestrator = Orchestrator(project_dir=DEMO_PROJECT_DIR)
    result = orchestrator.execute(task)

    print(f"\n{Colors.BOLD}📊 演示一结果:{Colors.END}")
    print(f"  模式: {Colors.GREEN}{result['mode']}{Colors.END}")
    print(f"  子Agent数: {Colors.GREEN}{result['child_agents_used']}{Colors.END}")
    print(f"  耗时: {Colors.GREEN}{result['elapsed_seconds']}秒{Colors.END}")
    print(f"  状态: {Colors.GREEN}{result['status']}{Colors.END}")

    return result


def demo_complex_task():
    """演示2：复杂任务 - 多层嵌套Loop模式"""
    print_banner("📋 演示二：复杂任务模式（多层嵌套Loop）", Colors.BLUE)

    task = "从零搭建全栈用户管理系统，包含数据库设计、后端CRUD接口、前端管理页面、工程规范统一"

    print(f"\n{Colors.BOLD}任务描述:{Colors.END} {task}")
    print(f"{Colors.BOLD}预期路由:{Colors.END} {Colors.YELLOW}复杂任务 → 方案规划 → 子Agent调度 → 汇总合并 → 闭环完成{Colors.END}")
    print()

    orchestrator = Orchestrator(project_dir=DEMO_PROJECT_DIR)
    result = orchestrator.execute(task)

    print(f"\n{Colors.BOLD}📊 演示二结果:{Colors.END}")
    print(f"  模式: {Colors.BLUE}{result['mode']}{Colors.END}")
    print(f"  子Agent总数: {Colors.BLUE}{result['subtasks_total']}{Colors.END}")
    print(f"  子Agent完成: {Colors.GREEN}{result['subtasks_completed']}{Colors.END}")
    print(f"  子Agent失败: {Colors.RED}{result['subtasks_failed']}{Colors.END}")
    print(f"  耗时: {Colors.BLUE}{result['elapsed_seconds']}秒{Colors.END}")
    print(f"  状态: {Colors.GREEN}{result['status']}{Colors.END}")

    return result


def demo_side_by_side():
    """演示3：对比演示 - 同一系统，两种任务自动分流"""
    print_banner("📋 演示三：自适应分流对比（核心价值展示）", Colors.CYAN)

    tasks = [
        {
            "name": "简单任务A",
            "description": "修改配置文件中的数据库连接超时时间从30秒改为60秒",
            "expected": "简单模式"
        },
        {
            "name": "复杂任务A",
            "description": "全栈重构订单系统：数据库迁移、后端API重写、前端页面重构、消息队列集成",
            "expected": "复杂模式"
        },
        {
            "name": "简单任务B",
            "description": "为User模型添加phone_number字段",
            "expected": "简单模式"
        },
        {
            "name": "复杂任务B",
            "description": "从零搭建完整的电商平台：商品管理、订单系统、用户系统、支付集成、物流追踪",
            "expected": "复杂模式"
        },
    ]

    print(f"\n{Colors.BOLD}自适应分流测试：{Colors.END}4个不同任务，自动判定复杂度\n")
    print(f"{'任务':<20} {'预期':<12} {'判定':<12} {'置信度':<10} {'子Agent':<10}")
    print("-" * 70)

    from utils import analyze_complexity

    for task in tasks:
        complexity = analyze_complexity(task["description"])
        mode = "🔀 复杂" if complexity["is_complex"] else "⚡ 简单"
        child_count = "4个" if complexity["is_complex"] else "0个"
        match = "✅" if (
            (complexity["is_complex"] and "复杂" in task["expected"]) or
            (not complexity["is_complex"] and "简单" in task["expected"])
        ) else "❌"

        print(f"{task['name']:<20} {task['expected']:<12} {mode:<12} {complexity['confidence']*100:.0f}%{'':<6} {child_count:<10} {match}")


def demo_architecture():
    """演示4：系统架构展示"""
    print_banner("📋 演示四：系统架构总览", Colors.CYAN)

    architecture = """
    {cyan}┌─────────────────────────────────────────────────────────────┐
    │                    0层：父调度Agent（核心大脑）                    │
    │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐      │
    │  │ 复杂度判定 │→│ 方案规划  │→│ 任务拆分  │→│ 调度执行  │      │
    │  └──────────┘  └──────────┘  └──────────┘  └─────┬────┘      │
    │                                                   │           │
    │              ┌──────────┐  ┌──────────┐          │           │
    │              │ 全局修复  │←│ 结果汇总  │←─────────┘           │
    │              └──────────┘  └──────────┘                      │
    └─────────────────────────────────────────────────────────────┘
                                  │
                    ┌─────────────┼─────────────┐
                    │             │             │
    {green}┌───────────────┐ ┌──────────────┐ ┌──────────────┐
    │  子Agent #1   │ │  子Agent #2  │ │  子Agent #N  │
    │  数据库模块    │ │  后端模块     │ │  前端模块     │
    │               │ │              │ │              │
    │ 编码→自测→修复 │ │ 编码→自测→修复│ │ 编码→自测→修复│
    │ 独立工作区     │ │ 独立工作区    │ │ 独立工作区    │
    │ 独立上下文     │ │ 独立上下文    │ │ 独立上下文    │
    │ 最大15轮迭代   │ │ 最大15轮迭代  │ │ 最大15轮迭代  │
    └───────────────┘ └──────────────┘ └──────────────┘
                      1层：子执行Agent（分布式工人）{reset}

    {yellow}双层嵌套Loop：
    外层：父Agent全局迭代Loop（最大5轮方案规划 + 全局修复）
    内层：多子Agent并行自修复Loop（各自独立编码→自测→修复）{reset}
    """.format(cyan=Colors.CYAN, green=Colors.GREEN, yellow=Colors.YELLOW, reset=Colors.END)

    print(architecture)


def demo_workspace_output():
    """演示5：展示子Agent工作区输出"""
    print_banner("📋 演示五：子Agent工作区输出预览", Colors.CYAN)

    # 运行一个子Agent来展示实际输出
    from child_agent import ChildAgent
    from config import WORKSPACES_DIR

    workspace = WORKSPACES_DIR / "demo-output"
    workspace.mkdir(parents=True, exist_ok=True)

    task = {
        "id": "DEMO-001",
        "name": "数据库表结构设计",
        "description": "设计用户表、角色表、权限表",
        "module_type": "database",
        "max_iterations": 15,
        "completion_criteria": "DDL语句完整、索引合理",
        "workspace": str(workspace)
    }

    print(f"\n{Colors.BOLD}启动子Agent: {task['name']}{Colors.END}\n")
    agent = ChildAgent(task, str(workspace))
    result = agent.execute()

    print(f"\n{Colors.BOLD}子Agent输出文件:{Colors.END}")
    for f in sorted(workspace.rglob("*")):
        if f.is_file():
            size = f.stat().st_size
            print(f"  {Colors.GREEN}📄 {f.name}{Colors.END} ({size} bytes)")


def main():
    """主演示流程"""
    print_banner("🚀 Claude Code 父子多层嵌套自适应Loop系统 - 完整演示", Colors.CYAN)
    print(f"\n{Colors.DIM}系统版本: v2.1 | 平台: Windows 11 | 适配: 隔离内网环境{Colors.END}")
    print(f"{Colors.DIM}核心特性: 自适应双模式切换 | 多层嵌套Loop | 分布式子Agent调度{Colors.END}")

    total_timer = Timer()

    # 演示4：架构展示
    demo_architecture()

    input(f"\n{Colors.YELLOW}按 Enter 继续查看自适应分流对比...{Colors.END}")

    # 演示3：自适应分流对比
    demo_side_by_side()

    input(f"\n{Colors.YELLOW}按 Enter 继续演示简单任务模式...{Colors.END}")

    # 演示1：简单任务
    demo_simple_task()

    input(f"\n{Colors.YELLOW}按 Enter 继续演示复杂任务模式（重点）...{Colors.END}")

    # 演示2：复杂任务
    demo_complex_task()

    input(f"\n{Colors.YELLOW}按 Enter 查看子Agent工作区输出...{Colors.END}")

    # 演示5：工作区输出
    demo_workspace_output()

    # 最终总结
    total_elapsed = total_timer.elapsed()
    print_banner(f"🏁 全部演示完成 | 总耗时: {total_elapsed:.2f}秒", Colors.GREEN)

    summary = f"""
{Colors.BOLD}{Colors.CYAN}╔══════════════════════════════════════════════════════════════╗
║          系统核心能力总结                                      ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  {Colors.GREEN}✅ 自适应双模式切换{Colors.CYAN}   简单任务直出 / 复杂任务分层调度      ║
║  {Colors.GREEN}✅ 多层嵌套Loop{Colors.CYAN}         外层全局迭代 + 内层并行自修复      ║
║  {Colors.GREEN}✅ 分布式子Agent调度{Colors.CYAN}   独立进程、独立工作区、独立上下文    ║
║  {Colors.GREEN}✅ 轮次熔断机制{Colors.CYAN}         父5轮/子15轮，防止无限循环         ║
║  {Colors.GREEN}✅ 自适应节流{Colors.CYAN}           简单任务零子进程，节省资源           ║
║  {Colors.GREEN}✅ 隔离内网适配{Colors.CYAN}         仅依赖Anthropic API，适配内网环境    ║
║  {Colors.GREEN}✅ 极低资源占用{Colors.CYAN}         无Docker/虚拟机，8G内存可运行       ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝{Colors.END}
"""
    print(summary)


if __name__ == "__main__":
    main()