# CLAUDE.md - 项目说明

## 项目概述

**Claude Code 父子多层嵌套自适应Loop系统** v2.4，全栈高阶多Agent方案。

## 两种使用模式

### 模式A：Python 脚本模式

```bash
# 简单任务（真实修改文件）
python orchestrator.py "修改 backend/main.py 的端口从8000改为9000"

# 复杂任务（多Agent调度）
python orchestrator.py "从零搭建全栈用户管理系统"

# 产品迭代循环（持续构建）
python iterate.py --max-iterations 5 "为项目添加用户认证和日志系统"

# 项目扫描
python project_scanner.py . --summary
```

### 模式B：Claude Code 原生模式（更强大）

直接在对话中说"用loop方法论"或"按loop流程"，Claude Code 将充当 Orchestrator，直接使用其工具链（Read/Write/Edit/Agent/Task/Bash）执行 Loop 四阶段流程，无需 Python 子进程。

## 核心架构

```
loop-system/
├── orchestrator.py       # 父调度Agent（大脑）
├── child_agent.py        # 子执行Agent（工人）
├── project_scanner.py    # 项目上下文扫描
├── iterate.py            # 产品迭代循环引擎
├── config.py             # 全局配置
├── utils.py              # 工具函数
└── workspaces/           # 子Agent工作区
```

## 权限要求

- `Bash(python *)` 执行 Python 脚本
- `Bash(git *)` 版本控制操作
- `Read/Write/Edit/Glob/Grep` 直接文件操作（原生模式）
- `Agent/Task` 多Agent调度（原生模式）