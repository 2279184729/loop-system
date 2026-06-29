# CLAUDE.md - 项目说明

## 项目概述

这是一个 **Claude Code 父子多层嵌套自适应Loop系统**，实现全栈高阶多Agent方案。

## 核心架构

- `orchestrator.py` - 父调度Agent（核心大脑）
- `child_agent.py` - 子执行Agent（分布式工人）
- `config.py` - 全局配置
- `utils.py` - 工具函数

## 如何调用

当用户请求执行代码任务时，使用以下命令：

```bash
python orchestrator.py "<任务描述>"
```

系统会自动判定任务复杂度并选择合适的执行路径。

## 权限要求

需要 `Bash(python *)` 权限来执行 orchestrator.py 和 child_agent.py。