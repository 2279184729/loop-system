"""
Claude Code 父子多层嵌套自适应Loop系统 - 全局配置
====================================================
适配Windows/Linux双平台，隔离内网环境
"""

import os
import sys
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Optional

# ============================================================
# 系统路径配置
# ============================================================
BASE_DIR = Path(__file__).parent.absolute()
WORKSPACES_DIR = BASE_DIR / "workspaces"
LOGS_DIR = BASE_DIR / "logs"
DEMO_PROJECT_DIR = BASE_DIR / "demo_project"

# ============================================================
# API配置（从 Claude Code settings.json 读取，与 Claude Code 保持一致）
# ============================================================
# API Key: 支持 ANTHROPIC_API_KEY 和 ANTHROPIC_AUTH_TOKEN 两种环境变量
ANTHROPIC_API_KEY = (
    os.environ.get("ANTHROPIC_API_KEY") or
    os.environ.get("ANTHROPIC_AUTH_TOKEN") or
    ""
)
ANTHROPIC_BASE_URL = os.environ.get(
    "ANTHROPIC_BASE_URL",
    "https://dashscope.aliyuncs.com/apps/anthropic"
)
ANTHROPIC_MODEL = os.environ.get(
    "ANTHROPIC_MODEL",
    "deepseek-v4-pro"
)

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
# 复杂度判定规则
# ============================================================
SIMPLE_TASK_KEYWORDS = [
    "单文件", "修复", "bug", "配置修改", "代码格式", "注释",
    "单接口", "局部修改", "小改动", "单页面", "单函数",
    "修改变量名", "添加日志", "错误处理", "单模块",
    "fix bug", "config", "format", "typo", "single file",
    "minor fix", "small change", "one line", "空指针",
    "NullPointer", "null pointer", "小改", "修一下",
    "改一下", "调一下", "微调", "hotfix", "hot fix",
    "补丁", "patch", "简单修改", "小问题", "简单",
    "修改配置", "改配置", "调整", "改动不大",
    "改为", "改成", "添加字段", "增加字段", "新增字段",
    "超时时间", "连接超时", "参数调整", "改个",
    "添加", "增加", "字段", "新增",
]

COMPLEX_TASK_KEYWORDS = [
    "全栈", "重构", "跨模块", "数据库改造", "批量", "多文件",
    "多模块", "完整业务", "架构", "CI/CD", "部署", "全链路",
    "新增功能", "系统", "平台", "多个接口", "前后端",
    "fullstack", "refactor", "migration", "architecture",
    "multi-module", "platform", "system design"
]

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