"""
Claude Code 父子多层嵌套自适应Loop系统 - 父调度Agent核心引擎
============================================================
作为全局唯一总控大脑，负责：
  1. 任务复杂度自适应判定
  2. 全局方案规划（复杂任务）
  3. 子任务拆分与调度
  4. 结果回流汇总
  5. 全局自检修复闭环
"""

import json
import sys
import os
import io

# 修复Windows GBK编码问题
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

import shutil
from pathlib import Path
from typing import Dict, List, Optional, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

from config import (
    Colors, SubTask, LoopState,
    MAX_PLAN_ITERATIONS, MAX_CHILD_ITERATIONS,
    MAX_GLOBAL_FIX_ITERATIONS, DEMO_PROJECT_DIR,
    ORCHESTRATOR_PLANNING_PROMPT, ORCHESTRATOR_EXECUTION_PROMPT,
    ANTHROPIC_MODEL
)
from utils import (
    print_banner, print_phase, print_step, print_success,
    print_error, print_warning, print_info, print_subtask,
    analyze_complexity, Logger, Timer, setup_workspace, run_child_agent,
    create_llm_client, run_agent_loop
)


class Orchestrator:
    """
    父调度Agent - 全局唯一总控大脑
    """

    def __init__(self, project_dir: str = None):
        self.project_dir = Path(project_dir) if project_dir else DEMO_PROJECT_DIR
        self.logger = Logger("orchestrator")
        self.timer = Timer()
        self.state = LoopState()
        self.subtasks: List[SubTask] = []
        self.plan: Optional[Dict] = None
        self.all_results: List[Dict] = []

    def execute(self, task_description: str) -> Dict:
        """
        主入口：执行任务（自适应路由）
        """
        print_banner("Claude Code 父子多层嵌套自适应Loop系统", Colors.CYAN)
        print(f"\n{Colors.BOLD}📋 任务描述:{Colors.END}")
        print(f"  {Colors.DIM}{task_description}{Colors.END}")

        # ==========================================
        # 阶段0：复杂度判定
        # ==========================================
        self.state.phase = "complexity_check"
        print_phase("阶段0：自适应复杂度判定")

        complexity = analyze_complexity(task_description)
        print_step(f"简单得分: {complexity['simple_score']} | 复杂得分: {complexity['complex_score']}")
        print_step(f"判定置信度: {complexity['confidence']*100:.0f}%")
        print_step(f"建议模式: {'🔀 多Agent分层调度' if complexity['is_complex'] else '⚡ 直接执行'}")

        if complexity['complex_matches']:
            print_info(f"复杂特征匹配: {', '.join(complexity['complex_matches'])}")
        if complexity['simple_matches']:
            print_info(f"简单特征匹配: {', '.join(complexity['simple_matches'])}")

        self.timer.checkpoint("complexity_check")

        # ==========================================
        # 路由：简单任务 vs 复杂任务
        # ==========================================
        if not complexity['is_complex']:
            return self._execute_simple(task_description)
        else:
            return self._execute_complex(task_description)

    # ================================================================
    # 简单任务执行路径（直接调用 Claude API + Tool Use）
    # ================================================================
    def _execute_simple(self, task_description: str) -> Dict:
        print_banner("⚡ 简单任务模式：直接执行", Colors.GREEN)
        self.state.phase = "direct_execute"

        workspace = str(self.project_dir)
        result = run_agent_loop(
            task_description=task_description,
            workspace=workspace,
            system_prompt=ORCHESTRATOR_EXECUTION_PROMPT,
            project_dir=workspace,
            max_iterations=10
        )

        self.state.phase = "done"
        elapsed = self.timer.elapsed()

        return {
            "mode": "simple",
            "task": task_description,
            "result": result.get("result", ""),
            "iterations": result.get("iterations", 0),
            "files_created": result.get("files_created", []),
            "elapsed_seconds": round(elapsed, 2),
            "child_agents_used": 0,
            "status": "completed" if result["success"] else "partial"
        }

    # ================================================================
    # 复杂任务执行路径（多层嵌套Loop）
    # ================================================================
    def _execute_complex(self, task_description: str) -> Dict:
        print_banner("🔀 复杂任务模式：多层嵌套Loop调度", Colors.BLUE)

        # 阶段一：全局方案规划Loop
        self._phase1_plan(task_description)

        # 阶段二：分布式子Agent调度Loop
        self._phase2_execute()

        # 阶段三：结果回流汇总Loop
        self._phase3_merge()

        # 阶段四：全局自检修复闭环Loop
        self._phase4_validate()

        # 最终闭环
        self.state.phase = "done"
        elapsed = self.timer.elapsed()

        result = {
            "mode": "complex",
            "task": task_description,
            "plan": self.plan,
            "subtasks_total": len(self.subtasks),
            "subtasks_completed": self.state.completed_subtasks,
            "subtasks_failed": self.state.failed_subtasks,
            "iterations": self.state.iteration,
            "elapsed_seconds": round(elapsed, 2),
            "child_agents_used": len(self.subtasks),
            "status": "completed" if self.state.failed_subtasks == 0 else "partial"
        }

        print_banner(
            f"🏁 多层Loop任务完全闭环完成 | "
            f"子Agent: {self.state.completed_subtasks}/{len(self.subtasks)} | "
            f"耗时: {elapsed:.2f}秒",
            Colors.GREEN
        )
        return result

    # ================================================================
    # 阶段一：全局方案规划Loop
    # ================================================================
    def _phase1_plan(self, task_description: str):
        print_phase("阶段一：全局方案规划Loop（父Agent外层循环）")
        self.state.phase = "plan"

        for iteration in range(1, MAX_PLAN_ITERATIONS + 1):
            print_step(f"规划迭代 {iteration}/{MAX_PLAN_ITERATIONS}")

            if iteration == 1:
                # 第1轮：初始分析
                plan = self._generate_initial_plan(task_description)
            else:
                # 后续轮次：优化迭代
                plan = self._refine_plan(plan)

            self.plan = plan
            print_success(f"方案v{iteration}: {plan['architecture']}")

            # 检查方案是否已经稳定
            if iteration >= 2 and self._is_plan_stable():
                print_success("方案已稳定，规划完成")
                break

            self.state.iteration += 1

        self.timer.checkpoint("phase1_plan")
        print_info(f"规划阶段完成，生成 {len(self.subtasks)} 个原子子任务")

    def _generate_initial_plan(self, task: str) -> Dict:
        """通过 Claude API 生成初始方案"""
        try:
            client = create_llm_client()
            response = client.messages.create(
                model=ANTHROPIC_MODEL,
                max_tokens=8192,
                system=ORCHESTRATOR_PLANNING_PROMPT,
                messages=[{"role": "user", "content": f"请为以下任务生成实施方案:\n\n{task}"}]
            )
            raw = response.content[0].text

            # 提取 JSON（处理可能的 markdown 代码块）
            if "```json" in raw:
                raw = raw.split("```json")[1].split("```")[0]
            elif "```" in raw:
                raw = raw.split("```")[1].split("```")[0]

            plan = json.loads(raw.strip())

            # 从 plan 中提取 subtasks 并创建 SubTask 对象
            subtask_dicts = plan.pop("subtasks", [])
            self.subtasks = []
            for st in subtask_dicts:
                self.subtasks.append(SubTask(
                    id=st.get("id", f"SUB-{len(self.subtasks)+1:03d}"),
                    name=st.get("name", "未命名"),
                    description=st.get("description", ""),
                    workspace=st.get("workspace", st.get("id", "unknown").lower().replace(" ", "-")),
                    module_type=st.get("module_type", "backend"),
                    dependencies=st.get("dependencies", []),
                    completion_criteria=st.get("completion_criteria", ""),
                    priority=st.get("priority", len(self.subtasks)),
                ))

            return plan

        except Exception as e:
            print_warning(f"Claude API 规划失败: {e}，使用通用方案")
            return self._fallback_plan(task)

    def _refine_plan(self, plan: Dict) -> Dict:
        """优化方案（通过 Claude API 迭代改进）"""
        try:
            client = create_llm_client()
            response = client.messages.create(
                model=ANTHROPIC_MODEL,
                max_tokens=8192,
                system=ORCHESTRATOR_PLANNING_PROMPT,
                messages=[{
                    "role": "user",
                    "content": f"优化以下方案，减少耦合、提高可执行性:\n\n{json.dumps(plan, ensure_ascii=False, indent=2)}"
                }]
            )
            raw = response.content[0].text
            if "```json" in raw:
                raw = raw.split("```json")[1].split("```")[0]
            elif "```" in raw:
                raw = raw.split("```")[1].split("```")[0]
            refined = json.loads(raw.strip())
            refined["version"] = plan.get("version", 1) + 1
            return refined
        except Exception as e:
            print_warning(f"方案优化失败: {e}")
            plan["version"] = plan.get("version", 1) + 1
            return plan

    def _fallback_plan(self, task: str) -> Dict:
        """API 不可用时的通用兜底方案"""
        plan = {
            "architecture": "模块化分布式架构",
            "modules": ["需求分析", "模块开发", "集成测试", "优化部署"],
            "tech_stack": {"language": "通用", "testing": "标准测试框架"}
        }
        self.subtasks = [
            SubTask(id="SUB-001", name="需求分析与架构设计",
                    description="分析需求、设计架构方案",
                    workspace="requirement-analysis", module_type="config", priority=0),
            SubTask(id="SUB-002", name="核心模块开发",
                    description="开发核心业务模块",
                    workspace="core-module", module_type="backend", priority=1),
            SubTask(id="SUB-003", name="接口/页面开发",
                    description="开发接口或前端页面",
                    workspace="interface-module", module_type="frontend", priority=1),
            SubTask(id="SUB-004", name="集成测试与优化",
                    description="全局集成测试、性能优化",
                    workspace="integration-test", module_type="config", priority=2),
        ]
        return plan

    def _is_plan_stable(self) -> bool:
        """检查方案是否稳定"""
        return self.state.iteration >= 2

    # ================================================================
    # 阶段二：分布式子Agent调度Loop
    # ================================================================
    def _phase2_execute(self):
        print_phase("阶段二：分布式子Agent调度Loop")
        self.state.phase = "execute"
        self.state.total_subtasks = len(self.subtasks)

        # 按优先级和依赖关系分组
        batches = self._group_by_dependency()

        for batch_idx, batch in enumerate(batches):
            print_step(f"批次 {batch_idx + 1}/{len(batches)}: 并行执行 {len(batch)} 个子任务")

            # 并行执行同一批次中的所有子任务
            with ThreadPoolExecutor(max_workers=min(len(batch), 4)) as executor:
                futures = {}
                for subtask in batch:
                    print_subtask(subtask.id, subtask.name, "running")
                    subtask.status = "running"
                    future = executor.submit(self._run_single_subtask, subtask)
                    futures[future] = subtask

                for future in as_completed(futures):
                    subtask = futures[future]
                    try:
                        result = future.result()
                        if result.get("success"):
                            subtask.status = "completed"
                            subtask.result = result
                            self.state.completed_subtasks += 1
                            print_subtask(subtask.id, subtask.name, "completed")
                            print_success(f"{subtask.id} 完成: {result.get('summary', 'OK')}")
                        else:
                            subtask.status = "failed"
                            self.state.failed_subtasks += 1
                            print_subtask(subtask.id, subtask.name, "failed")
                            print_error(f"{subtask.id} 失败: {result.get('error', 'Unknown')}")
                    except Exception as e:
                        subtask.status = "failed"
                        self.state.failed_subtasks += 1
                        print_error(f"{subtask.id} 异常: {str(e)}")

                    self.all_results.append({
                        "subtask_id": subtask.id,
                        "subtask_name": subtask.name,
                        "status": subtask.status,
                        "result": subtask.result
                    })

        self.timer.checkpoint("phase2_execute")

    def _group_by_dependency(self) -> List[List[SubTask]]:
        """按依赖关系分组子任务"""
        completed = set()
        batches = []
        remaining = list(self.subtasks)

        while remaining:
            batch = []
            still_waiting = []

            for subtask in remaining:
                deps = set(subtask.dependencies)
                if deps.issubset(completed):
                    batch.append(subtask)
                else:
                    still_waiting.append(subtask)

            if not batch:
                # 防止死锁：如果无法推进，将剩余全部放入下一批
                batches.append(still_waiting)
                break

            batches.append(batch)
            for subtask in batch:
                completed.add(subtask.id)
            remaining = still_waiting

        return batches

    def _run_single_subtask(self, subtask: SubTask) -> Dict:
        """执行单个子任务（调用子Agent）"""
        workspace = setup_workspace(subtask.workspace)

        task_payload = {
            "id": subtask.id,
            "name": subtask.name,
            "description": subtask.description,
            "module_type": subtask.module_type,
            "max_iterations": subtask.max_iterations,
            "completion_criteria": subtask.completion_criteria,
            "workspace": str(workspace)
        }

        # 调用子Agent进程，传入项目目录以便读取上下文
        result = run_child_agent(str(workspace), task_payload, str(self.project_dir))
        return result

    # ================================================================
    # 阶段三：结果回流汇总Loop
    # ================================================================
    def _phase3_merge(self):
        print_phase("阶段三：结果回流汇总Loop")
        self.state.phase = "merge"

        completed = [r for r in self.all_results if r["status"] == "completed"]
        failed = [r for r in self.all_results if r["status"] == "failed"]
        print_info(f"已完成: {len(completed)} | 失败: {len(failed)}")

        if not completed:
            print_warning("没有成功完成的子任务，跳过合并")
            return

        # 将各工作区的文件复制到项目目录
        merged_count = 0
        for r in completed:
            ws_path = Path(r.get("result", {}).get("workspace", ""))
            if not ws_path or not ws_path.exists():
                continue

            for file_path in ws_path.rglob("*"):
                if file_path.is_file() and not file_path.name.startswith("."):
                    # 计算相对路径，保留目录结构
                    rel_path = file_path.relative_to(ws_path)
                    dest = self.project_dir / rel_path
                    dest.parent.mkdir(parents=True, exist_ok=True)

                    if dest.exists():
                        print_warning(f"冲突: {rel_path} 已存在，备份后覆盖")
                        backup = dest.with_suffix(dest.suffix + ".bak")
                        shutil.copy2(dest, backup)

                    shutil.copy2(file_path, dest)
                    merged_count += 1
                    print_success(f"合并: {rel_path}")

        print_info(f"共合并 {merged_count} 个文件到 {self.project_dir}")

        self.timer.checkpoint("phase3_merge")

    # ================================================================
    # 阶段四：全局自检修复闭环Loop
    # ================================================================
    def _phase4_validate(self):
        print_phase("阶段四：全局自检修复闭环Loop")
        self.state.phase = "validate"

        for iteration in range(1, MAX_GLOBAL_FIX_ITERATIONS + 1):
            print_step(f"全局校验迭代 {iteration}/{MAX_GLOBAL_FIX_ITERATIONS}")

            issues = self._detect_global_issues()

            if not issues:
                print_success("全局校验通过，无遗留问题")
                break

            print_warning(f"检测到 {len(issues)} 个问题，开始修复...")

            for issue in issues:
                print_step(f"修复: {issue['description']}")
                # 使用 Claude API 修复全局问题
                try:
                    fix_result = run_agent_loop(
                        task_description=f"修复以下全局问题:\n{issue['description']}\n\n文件路径: {issue.get('file', '')}\n问题详情: {issue.get('detail', '')}",
                        workspace=str(self.project_dir),
                        system_prompt=ORCHESTRATOR_EXECUTION_PROMPT,
                        project_dir=str(self.project_dir),
                        max_iterations=5
                    )
                    if fix_result["success"]:
                        print_success(f"已修复: {issue['description']}")
                    else:
                        print_error(f"修复失败: {issue['description']}")
                except Exception as e:
                    print_error(f"修复异常: {e}")

            if iteration == MAX_GLOBAL_FIX_ITERATIONS:
                print_warning("达到最大修复迭代次数")

        self.timer.checkpoint("phase4_validate")

    def _detect_global_issues(self) -> List[Dict]:
        """通过 Claude API 检测全局问题"""
        try:
            client = create_llm_client()

            # 收集项目中所有代码文件的内容摘要
            code_files = []
            for ext in ['*.py', '*.ts', '*.tsx', '*.js', '*.jsx', '*.sql', '*.json']:
                for f in self.project_dir.rglob(ext):
                    if 'node_modules' not in str(f) and '__pycache__' not in str(f):
                        try:
                            content = f.read_text(encoding='utf-8', errors='replace')
                            code_files.append(f"### {f.relative_to(self.project_dir)}\n{content[:2000]}")
                        except:
                            pass

            if not code_files:
                return []

            code_snapshot = "\n\n".join(code_files[:20])  # 限制上下文大小

            response = client.messages.create(
                model=ANTHROPIC_MODEL,
                max_tokens=4096,
                system="你是一个代码审查专家。检测项目中的全局性问题：模块间API不一致、缺失的导入、循环依赖、配置冲突等。返回 JSON 数组: [{\"type\": \"architecture|module|config\", \"description\": \"问题描述\", \"file\": \"文件路径\", \"detail\": \"详细信息\"}]。如果没有问题返回空数组 []。",
                messages=[{"role": "user", "content": f"审查以下项目代码，检测全局问题:\n\n{code_snapshot}"}]
            )

            raw = response.content[0].text
            if "```json" in raw:
                raw = raw.split("```json")[1].split("```")[0]
            elif "```" in raw:
                raw = raw.split("```")[1].split("```")[0]

            issues = json.loads(raw.strip())
            return issues if isinstance(issues, list) else []

        except Exception as e:
            print_warning(f"全局检测异常: {e}")
            return []


# ============================================================
# 命令行入口
# ============================================================
def main():
    """命令行入口"""
    if len(sys.argv) < 2:
        print("用法: python orchestrator.py <任务描述> [--project-dir <项目目录>]")
        print()
        print("示例:")
        print('  python orchestrator.py "修复登录接口空指针bug"')
        print('  python orchestrator.py "从零搭建全栈用户管理系统"')
        print('  python orchestrator.py "重构项目代码结构"')
        sys.exit(1)

    task_description = sys.argv[1]
    project_dir = None

    # 解析可选参数
    for i, arg in enumerate(sys.argv):
        if arg == "--project-dir" and i + 1 < len(sys.argv):
            project_dir = sys.argv[i + 1]

    orchestrator = Orchestrator(project_dir=project_dir)
    result = orchestrator.execute(task_description)

    # 输出最终结果
    print(f"\n{Colors.CYAN}{Colors.BOLD}📊 最终执行报告:{Colors.END}")
    print(json.dumps(result, ensure_ascii=False, indent=2))

    return result


if __name__ == "__main__":
    main()