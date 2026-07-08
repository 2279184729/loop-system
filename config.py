"""
Claude Code 父子多层嵌套自适应Loop系统 - 全局配置
====================================================
适配Windows/Linux双平台，隔离内网环境
"""

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Optional

# ============================================================
# 系统路径配置
# ============================================================
BASE_DIR = Path(__file__).parent.absolute()
WORKSPACES_DIR = BASE_DIR / "workspaces"
LOGS_DIR = BASE_DIR / "logs"

# ============================================================
# API配置（隔离内网，仅放行Anthropic API）
# ============================================================
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN", "")
ANTHROPIC_BASE_URL = os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com")

# 网络隔离开关
DISABLE_NETWORK_CHECK = True
DISABLE_WEB_SEARCH = True
DISABLE_EXTERNAL_FETCH = True

# ============================================================
# 循环控制参数
# ============================================================
# 父Agent方案规划最大迭代轮次
MAX_PLAN_ITERATIONS = 5
# 子Agent自循环最大迭代轮次
MAX_CHILD_ITERATIONS = 15
# 全局修复最大迭代轮次
MAX_GLOBAL_FIX_ITERATIONS = 5
# 任务超时（秒）
TASK_TIMEOUT = 3600

# ============================================================
# 子Agent配置
# ============================================================
@dataclass
class SubTask:
    """子任务定义"""
    id: str
    name: str
    description: str
    workspace: str
    module_type: str  # backend / frontend / database / config
    dependencies: List[str] = field(default_factory=list)
    completion_criteria: str = ""
    priority: int = 0  # 0=最高, 越大越低
    max_iterations: int = MAX_CHILD_ITERATIONS
    status: str = "pending"  # pending / running / completed / failed
    result: Optional[Dict] = None

@dataclass
class LoopState:
    """Loop状态追踪"""
    phase: str = "init"  # init / complexity_check / plan / execute / merge / validate / done
    iteration: int = 0
    total_subtasks: int = 0
    completed_subtasks: int = 0
    failed_subtasks: int = 0
    errors: List[str] = field(default_factory=list)
    logs: List[str] = field(default_factory=list)

# ============================================================
# 输出样式配置（终端彩色输出）
# ============================================================
class Colors:
    """终端颜色 - Windows/Linux兼容"""
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    END = '\033[0m'

    @staticmethod
    def supports_color():
        """检测终端是否支持颜色"""
        if os.name == 'nt':
            try:
                import ctypes
                kernel32 = ctypes.windll.kernel32
                kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
                return True
            except:
                return False
        return hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()

# ============================================================
# Claude API 系统提示词（用于构建 claude CLI prompt）
# ============================================================
ORCHESTRATOR_PLANNING_PROMPT = """你是一个资深技术架构师。分析用户的任务需求，生成详细的实施方案。

返回严格的 JSON 格式（不要包含 markdown 代码块标记）：
{
  "architecture": "架构设计简述（1-2句话）",
  "modules": ["模块1", "模块2"],
  "tech_stack": {"语言/框架": "版本/说明"},
  "subtasks": [
    {
      "id": "SUB-001",
      "name": "子任务名称",
      "description": "详细的实现说明，包含具体要做什么、涉及哪些文件",
      "module_type": "backend|frontend|database|config",
      "dependencies": [],
      "priority": 0,
      "completion_criteria": "具体的完成标准，如：所有测试通过、编译无错误、功能可运行"
    }
  ]
}

规则：
- 将复杂任务拆分为 2-6 个独立可执行的原子子任务
- dependencies 引用其他子任务的 id（如 ["SUB-001"]），无依赖则为空数组
- priority 0=最高优先级，数字越大优先级越低
- module_type 决定子任务的代码类型：database(数据库DDL/迁移)、backend(后端API/服务)、frontend(前端页面/组件)、config(配置/工程化/测试)
- 每个子任务必须有明确的 completion_criteria"""

ORCHESTRATOR_EXECUTION_PROMPT = """你是一个全栈软件工程师，负责执行编程任务。你可以使用工具来读取文件、编写代码、编辑文件和运行命令。

工作流程：
1. 先用 read_file 了解现有代码结构
2. 用 write_file 创建新文件或用 edit_file 修改现有文件
3. 用 run_command 运行测试、lint 或构建命令来验证你的修改
4. 如果测试失败，分析错误并修复
5. 确认所有测试通过后，总结你做了什么

重要原则：
- 只修改与任务直接相关的代码，不要重构无关代码
- 保持代码风格与现有代码一致
- 编写简洁、可工作的代码，不要过度设计
- 完成后运行测试验证
- 跨平台兼容：run_command 支持 Windows/Linux/macOS，优先使用跨平台命令（python -m pytest 而非 pytest，python 而非 python3）"""

CHILD_AGENT_SYSTEM_PROMPT = """你是一个多Agent系统中的专业工作者Agent，负责实现一个特定的模块或功能。

你的工作区是隔离的——你只能写入工作区目录内的文件。但你可以读取项目目录中的文件来理解上下文。

工作流程：
1. 阅读项目中的相关文件，理解现有架构和代码风格
2. 在工作区中创建/修改你负责的模块文件
3. 运行测试验证你的代码
4. 如果测试失败，分析错误并修复
5. 确认完成标准已满足后，报告完成

重要原则：
- 只专注于分配给你的子任务，不要越界做其他模块的工作
- 生成生产级质量的代码，包含适当的错误处理和类型注解
- 确保你的代码可以独立运行和测试
- 完成后明确说明你完成了什么以及为什么完成标准已满足
- 跨平台兼容：使用 pathlib 处理路径，run_command 优先使用跨平台命令（python -m pytest、python -m pip 等），避免平台特定 shell 语法"""