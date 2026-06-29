---
name: loop-system
description: Claude Code 父子多层嵌套自适应Loop系统 - 自适应双模式智能切换，简单任务极速直出，复杂任务多层嵌套Loop调度
metadata:
  type: project
  version: "2.1"
  platform: cross-platform
---

# Claude Code 父子多层嵌套自适应Loop系统

## 核心能力

自适应双模式智能切换，无需人工判断任务复杂度：

- **简单任务**（单文件/单功能/小修复）：跳过方案规划，直接就地完成，零子进程
- **复杂任务**（全栈项目/重构/多模块）：父Agent全局架构方案 → 批量并行调度子Agent → 全局汇总校验

## 调用方式

当用户需要执行代码任务时，通过以下方式调用本系统：

```bash
python orchestrator.py "<任务描述>"
```

### 示例

```bash
# 简单任务 - 自动判定为极速直出模式
python orchestrator.py "修复登录接口空指针bug"

# 复杂任务 - 自动判定为多层嵌套Loop模式
python orchestrator.py "从零搭建全栈用户管理系统"
```

## 工作流程

1. **阶段0：复杂度判定** - 自动分析任务，9种特征匹配规则
2. **简单任务路径**：直接执行 → 自检 → 闭环
3. **复杂任务路径**：
   - 阶段1：全局方案规划Loop
   - 阶段2：分布式子Agent调度Loop
   - 阶段3：结果回流汇总Loop
   - 阶段4：全局自检修复闭环Loop

## 配置参数

- 父Agent方案规划最大迭代：5轮
- 子Agent自循环最大迭代：15轮
- 全局修复最大迭代：5轮
- 子Agent并行工作区：独立进程、独立上下文

## 文件结构

```
{project_dir}/
├── orchestrator.py       # 父调度Agent核心引擎
├── child_agent.py        # 子执行Agent模块
├── config.py             # 全局配置
├── utils.py              # 工具函数库
├── workspaces/           # 子Agent独立工作区
└── logs/                 # 运行日志
```