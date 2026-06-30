"""
Claude Code 集成层 - 真实AI调用模块
====================================
提供 Claude API SDK 和 Claude Code CLI 两种调用方式。
当 API 不可用时，自动降级为模拟模式。

支持:
  - Claude API SDK 调用（anthropic 包）
  - Claude Code CLI 调用（claude 命令）
  - 自动降级：API不可用时切换模拟模式
  - 流式输出：实时反馈代码生成进度
"""

import json
import os
import sys
import io
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field

# 修复Windows GBK编码问题（仅当stdout未被重定向时）
if sys.platform == 'win32':
    try:
        if not isinstance(sys.stdout, io.TextIOWrapper) or sys.stdout.encoding != 'utf-8':
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
    except (ValueError, AttributeError):
        pass  # stdout 已被重定向或关闭

from config import (
    Colors, ANTHROPIC_API_KEY, ANTHROPIC_BASE_URL, ANTHROPIC_MODEL
)


# ============================================================
# 配置
# ============================================================
@dataclass
class ClaudeConfig:
    """Claude 集成配置"""
    api_key: str = field(default_factory=lambda: ANTHROPIC_API_KEY or os.environ.get("ANTHROPIC_API_KEY", ""))
    base_url: str = ANTHROPIC_BASE_URL
    model: str = ANTHROPIC_MODEL
    max_tokens: int = 4096
    temperature: float = 0.3
    timeout: int = 120

    @property
    def is_available(self) -> bool:
        """检查是否有可用的 API Key"""
        return bool(self.api_key and self.api_key.strip())

    @property
    def cli_available(self) -> bool:
        """检查 claude CLI 是否可用"""
        try:
            result = subprocess.run(
                ["claude", "--version"],
                capture_output=True, text=True, timeout=5
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False


# ============================================================
# Claude API SDK 调用
# ============================================================
class ClaudeAPIClient:
    """基于 Anthropic SDK 的 Claude API 客户端"""

    def __init__(self, config: ClaudeConfig = None):
        self.config = config or ClaudeConfig()
        self._client = None
        self._init_client()

    def _init_client(self):
        """初始化 Anthropic 客户端"""
        if not self.config.is_available:
            return
        try:
            from anthropic import Anthropic
            self._client = Anthropic(
                api_key=self.config.api_key,
                base_url=self.config.base_url,
                timeout=self.config.timeout
            )
        except ImportError:
            print(f"{Colors.YELLOW}  ⚠️ anthropic 包未安装，将使用模拟模式{Colors.END}")
            self._client = None
        except Exception as e:
            print(f"{Colors.YELLOW}  ⚠️ Anthropic 客户端初始化失败: {e}{Colors.END}")
            self._client = None

    @property
    def is_ready(self) -> bool:
        return self._client is not None

    def chat(
        self,
        system: str,
        messages: List[Dict],
        max_tokens: int = None,
        temperature: float = None,
        on_stream: Callable[[str], None] = None
    ) -> Dict:
        """
        发送消息到 Claude API

        Args:
            system: 系统提示词
            messages: 消息列表 [{"role": "user", "content": "..."}]
            max_tokens: 最大输出token
            temperature: 温度参数
            on_stream: 流式回调函数

        Returns:
            {"success": bool, "content": str, "usage": dict, "error": str}
        """
        if not self.is_ready:
            return {"success": False, "error": "API 客户端未初始化"}

        try:
            max_tok = max_tokens or self.config.max_tokens
            temp = temperature if temperature is not None else self.config.temperature

            if on_stream:
                # 流式调用
                full_content = []
                with self._client.messages.stream(
                    model=self.config.model,
                    system=system,
                    messages=messages,
                    max_tokens=max_tok,
                    temperature=temp,
                ) as stream:
                    for text in stream.text_stream:
                        full_content.append(text)
                        on_stream(text)
                content = "".join(full_content)
                return {"success": True, "content": content, "usage": {}}
            else:
                # 非流式调用
                response = self._client.messages.create(
                    model=self.config.model,
                    system=system,
                    messages=messages,
                    max_tokens=max_tok,
                    temperature=temp,
                )
                # 处理多种 content block 类型（TextBlock, ThinkingBlock 等）
                text_parts = []
                for block in response.content:
                    if hasattr(block, 'text'):
                        text_parts.append(block.text)
                content = "".join(text_parts) if text_parts else ""
                usage = {
                    "input_tokens": response.usage.input_tokens if response.usage else 0,
                    "output_tokens": response.usage.output_tokens if response.usage else 0,
                }
                return {"success": True, "content": content, "usage": usage}

        except Exception as e:
            return {"success": False, "error": str(e)}


# ============================================================
# Claude Code CLI 调用
# ============================================================
class ClaudeCLIClient:
    """基于 Claude Code CLI 的调用客户端"""

    def __init__(self, config: ClaudeConfig = None):
        self.config = config or ClaudeConfig()

    @property
    def is_ready(self) -> bool:
        return self.config.cli_available

    def execute(
        self,
        prompt: str,
        workdir: str = None,
        timeout: int = None,
        extra_args: List[str] = None
    ) -> Dict:
        """
        通过 claude CLI 执行任务

        Args:
            prompt: 任务提示词
            workdir: 工作目录
            timeout: 超时时间（秒）
            extra_args: 额外CLI参数

        Returns:
            {"success": bool, "output": str, "error": str}
        """
        if not self.is_ready:
            return {"success": False, "error": "Claude Code CLI 不可用"}

        cmd = ["claude", "-p", prompt]
        if extra_args:
            cmd.extend(extra_args)

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout or self.config.timeout,
                cwd=workdir,
                encoding='utf-8',
                errors='replace'
            )

            return {
                "success": result.returncode == 0,
                "output": result.stdout,
                "error": result.stderr if result.returncode != 0 else "",
                "return_code": result.returncode
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Claude CLI 执行超时"}
        except FileNotFoundError:
            return {"success": False, "error": "claude 命令未找到，请安装 Claude Code"}
        except Exception as e:
            return {"success": False, "error": str(e)}


# ============================================================
# 统一 Claude 集成层
# ============================================================
class ClaudeIntegration:
    """
    统一 Claude 集成层
    自动选择最佳调用方式：API SDK > CLI > 模拟降级
    """

    def __init__(self, config: ClaudeConfig = None):
        self.config = config or ClaudeConfig()
        self.api_client = ClaudeAPIClient(self.config)
        self.cli_client = ClaudeCLIClient(self.config)

        # 检测可用模式
        self.mode = self._detect_mode()
        print(f"{Colors.DIM}  ℹ️ Claude 集成模式: {self.mode}{Colors.END}")

    def _detect_mode(self) -> str:
        """检测最佳调用模式"""
        if self.api_client.is_ready:
            return "api_sdk"
        elif self.cli_client.is_ready:
            return "cli"
        else:
            return "simulated"

    def is_real(self) -> bool:
        """是否使用真实AI（非模拟）"""
        return self.mode != "simulated"

    # ============================================================
    # 高级API：面向不同场景的封装
    # ============================================================

    def generate_code(
        self,
        task_description: str,
        module_type: str,
        context: Dict = None,
        on_stream: Callable[[str], None] = None
    ) -> Dict:
        """
        AI 驱动的代码生成

        Args:
            task_description: 任务描述
            module_type: 模块类型 (backend/frontend/database/config)
            context: 额外上下文信息

        Returns:
            {"success": bool, "files": [{"path": str, "content": str}], "summary": str}
        """
        system_prompt = self._build_code_gen_system_prompt(module_type)
        user_prompt = self._build_code_gen_user_prompt(task_description, context)

        if self.mode == "api_sdk":
            return self._generate_via_api(system_prompt, user_prompt, module_type, on_stream)
        elif self.mode == "cli":
            return self._generate_via_cli(system_prompt, user_prompt)
        else:
            return self._generate_simulated(task_description, module_type)

    def refine_plan(
        self,
        current_plan: Dict,
        task_description: str,
        feedback: str = ""
    ) -> Dict:
        """
        AI 驱动的方案优化

        Args:
            current_plan: 当前方案
            task_description: 原始任务描述
            feedback: 反馈信息

        Returns:
            {"success": bool, "plan": dict, "changes": str}
        """
        system_prompt = """你是一个资深软件架构师。请优化给定的技术方案。
只输出优化后的JSON方案，不要添加任何解释。"""
        user_prompt = f"""原始任务: {task_description}

当前方案:
{json.dumps(current_plan, ensure_ascii=False, indent=2)}

反馈: {feedback or '请检查方案的完整性、可行性和模块划分是否合理'}

请输出优化后的方案JSON，包含:
- architecture: 架构描述
- modules: 模块列表
- tech_stack: 技术栈
- optimizations: 优化点列表
- risks: 风险点列表
"""

        if self.mode == "api_sdk":
            result = self.api_client.chat(system_prompt, [{"role": "user", "content": user_prompt}])
            if result["success"]:
                try:
                    # 尝试解析JSON
                    content = result["content"]
                    # 提取JSON块
                    if "```json" in content:
                        content = content.split("```json")[1].split("```")[0]
                    elif "```" in content:
                        content = content.split("```")[1].split("```")[0]
                    plan = json.loads(content.strip())
                    return {"success": True, "plan": plan, "changes": "AI优化完成"}
                except json.JSONDecodeError:
                    return {"success": False, "error": "AI返回的JSON解析失败"}
            return {"success": False, "error": result.get("error", "API调用失败")}
        elif self.mode == "cli":
            result = self.cli_client.execute(user_prompt)
            if result["success"]:
                try:
                    plan = json.loads(result["output"])
                    return {"success": True, "plan": plan, "changes": "AI优化完成"}
                except json.JSONDecodeError:
                    return {"success": False, "error": "CLI返回的JSON解析失败"}
            return {"success": False, "error": result.get("error", "CLI调用失败")}
        else:
            # 模拟优化
            plan = current_plan.copy()
            plan["version"] = plan.get("version", 1) + 1
            plan["optimizations"] = plan.get("optimizations", []) + [
                f"优化项v{plan['version']}: 减少模块耦合、增加容错设计"
            ]
            return {"success": True, "plan": plan, "changes": "模拟优化"}

    def review_code(
        self,
        code: str,
        language: str = "python",
        review_focus: List[str] = None
    ) -> Dict:
        """
        AI 代码审查

        Args:
            code: 代码内容
            language: 编程语言
            review_focus: 审查重点列表

        Returns:
            {"success": bool, "issues": list, "suggestions": list, "score": int}
        """
        system_prompt = f"""你是一个资深{language}代码审查专家。请审查以下代码。
只输出JSON格式结果，不要其他内容。"""

        focus_str = ", ".join(review_focus) if review_focus else "代码质量、安全性、性能、可维护性"
        user_prompt = f"""审查以下{language}代码，重点关注: {focus_str}

```{language}
{code[:8000]}  # 限制长度避免超token
```

输出JSON格式:
{{
  "issues": [{{"severity": "error/warning/info", "line": N, "description": "..."}}],
  "suggestions": ["建议1", "建议2"],
  "score": 0-100
}}
"""

        if self.mode == "api_sdk":
            result = self.api_client.chat(system_prompt, [{"role": "user", "content": user_prompt}])
            if result["success"]:
                try:
                    content = result["content"]
                    if "```json" in content:
                        content = content.split("```json")[1].split("```")[0]
                    elif "```" in content:
                        content = content.split("```")[1].split("```")[0]
                    return json.loads(content.strip())
                except json.JSONDecodeError:
                    return {"success": False, "issues": [], "suggestions": [], "score": 0}
            return {"success": False, "issues": [], "suggestions": [], "score": 0}
        elif self.mode == "cli":
            result = self.cli_client.execute(user_prompt)
            if result["success"]:
                try:
                    return json.loads(result["output"])
                except json.JSONDecodeError:
                    return {"success": False, "issues": [], "suggestions": [], "score": 0}
            return {"success": False, "issues": [], "suggestions": [], "score": 0}
        else:
            return {
                "success": True,
                "issues": [],
                "suggestions": ["代码结构良好（模拟审查）"],
                "score": 85
            }

    def analyze_complexity_ai(self, task_description: str) -> Dict:
        """
        AI 驱动的任务复杂度分析（比关键词匹配更准确）

        Args:
            task_description: 任务描述

        Returns:
            {"is_complex": bool, "confidence": float, "reasoning": str}
        """
        system_prompt = """你是一个任务分析专家。分析任务复杂度，只输出JSON。"""
        user_prompt = f"""分析以下软件开发任务的复杂度:

任务: {task_description}

输出JSON:
{{
  "is_complex": true/false,
  "confidence": 0.0-1.0,
  "reasoning": "简短理由",
  "suggested_modules": ["模块1", "模块2"],
  "estimated_effort": "low/medium/high"
}}
"""

        if self.mode == "api_sdk":
            result = self.api_client.chat(system_prompt, [{"role": "user", "content": user_prompt}])
            if result["success"]:
                try:
                    content = result["content"]
                    if "```json" in content:
                        content = content.split("```json")[1].split("```")[0]
                    elif "```" in content:
                        content = content.split("```")[1].split("```")[0]
                    return json.loads(content.strip())
                except json.JSONDecodeError:
                    pass
            return {"is_complex": True, "confidence": 0.5, "reasoning": "AI分析失败，默认复杂模式"}
        elif self.mode == "cli":
            result = self.cli_client.execute(user_prompt)
            if result["success"]:
                try:
                    return json.loads(result["output"])
                except json.JSONDecodeError:
                    pass
            return {"is_complex": True, "confidence": 0.5, "reasoning": "CLI分析失败，默认复杂模式"}
        else:
            return {"is_complex": True, "confidence": 0.5, "reasoning": "模拟模式，默认复杂"}

    def generate_tests(
        self,
        code: str,
        language: str = "python",
        test_framework: str = "pytest"
    ) -> Dict:
        """
        AI 驱动的测试生成

        Args:
            code: 源代码
            language: 语言
            test_framework: 测试框架

        Returns:
            {"success": bool, "test_code": str, "test_count": int}
        """
        system_prompt = f"""你是一个{language}测试专家。为给定代码生成完整的{test_framework}测试用例。
只输出测试代码，不要解释。"""
        user_prompt = f"""为以下{language}代码生成{test_framework}测试:

```{language}
{code[:6000]}
```

要求:
1. 覆盖正常流程和边界情况
2. 覆盖错误处理路径
3. 使用 mock 隔离外部依赖
4. 测试函数命名清晰
"""

        if self.mode == "api_sdk":
            result = self.api_client.chat(
                system_prompt,
                [{"role": "user", "content": user_prompt}],
                max_tokens=4096
            )
            if result["success"]:
                content = result["content"]
                if "```" in content:
                    content = content.split("```")[1]
                    if "\n" in content:
                        content = content.split("\n", 1)[1]
                    if content.endswith("```"):
                        content = content[:-3]
                return {
                    "success": True,
                    "test_code": content.strip(),
                    "test_count": content.count("def test_")
                }
            return {"success": False, "test_code": "", "test_count": 0}
        elif self.mode == "cli":
            result = self.cli_client.execute(user_prompt)
            if result["success"]:
                return {
                    "success": True,
                    "test_code": result["output"],
                    "test_count": result["output"].count("def test_")
                }
            return {"success": False, "test_code": "", "test_count": 0}
        else:
            return {"success": False, "test_code": "", "test_count": 0}

    def fix_error(
        self,
        code: str,
        error_message: str,
        language: str = "python"
    ) -> Dict:
        """
        AI 驱动的错误修复

        Args:
            code: 有错误的代码
            error_message: 错误信息
            language: 语言

        Returns:
            {"success": bool, "fixed_code": str, "explanation": str}
        """
        system_prompt = f"""你是一个{language}调试专家。修复代码中的错误。
只输出JSON格式: {{"fixed_code": "...", "explanation": "..."}}"""
        user_prompt = f"""修复以下{language}代码的错误:

错误信息: {error_message}

代码:
```{language}
{code[:6000]}
```
"""

        if self.mode == "api_sdk":
            result = self.api_client.chat(system_prompt, [{"role": "user", "content": user_prompt}])
            if result["success"]:
                try:
                    content = result["content"]
                    if "```json" in content:
                        content = content.split("```json")[1].split("```")[0]
                    elif "```" in content:
                        content = content.split("```")[1].split("```")[0]
                    return json.loads(content.strip())
                except json.JSONDecodeError:
                    return {"success": False, "fixed_code": code, "explanation": "AI返回解析失败"}
            return {"success": False, "fixed_code": code, "explanation": result.get("error", "")}
        elif self.mode == "cli":
            result = self.cli_client.execute(user_prompt)
            if result["success"]:
                try:
                    return json.loads(result["output"])
                except json.JSONDecodeError:
                    return {"success": False, "fixed_code": code, "explanation": "CLI返回解析失败"}
            return {"success": False, "fixed_code": code, "explanation": result.get("error", "")}
        else:
            return {
                "success": True,
                "fixed_code": code,
                "explanation": "模拟修复：检查代码逻辑和异常处理"
            }

    # ============================================================
    # 内部实现
    # ============================================================

    def _build_code_gen_system_prompt(self, module_type: str) -> str:
        """构建代码生成的系统提示词"""
        prompts = {
            "database": """你是一个数据库设计专家。请生成完整的数据库DDL脚本。
包含: 表结构、索引、约束、注释、迁移脚本。
输出格式: 每个文件用 ```文件名 ``` 标记。""",

            "backend": """你是一个Python后端开发专家。请生成完整的FastAPI后端代码。
包含: API路由、数据模型、参数校验、异常处理、测试用例。
使用 pydantic v2 语法。输出格式: 每个文件用 ```文件名 ``` 标记。""",

            "frontend": """你是一个React前端开发专家。请生成完整的TypeScript前端代码。
包含: 组件、类型定义、样式、API调用、错误处理。
使用 React 18 + TypeScript。输出格式: 每个文件用 ```文件名 ``` 标记。""",

            "config": """你是一个工程规范专家。请生成完整的项目配置文件。
包含: ESLint、Prettier、TypeScript配置、CI配置等。
输出格式: 每个文件用 ```文件名 ``` 标记。""",
        }
        return prompts.get(module_type, prompts["backend"])

    def _build_code_gen_user_prompt(
        self, task: str, context: Dict = None
    ) -> str:
        """构建代码生成的用户提示词"""
        ctx_str = ""
        if context:
            ctx_str = f"\n上下文信息:\n{json.dumps(context, ensure_ascii=False, indent=2)}"

        return f"""请根据以下任务描述生成代码:

任务: {task}{ctx_str}

要求:
1. 代码完整可运行
2. 包含充分的注释
3. 遵循最佳实践
4. 包含错误处理
5. 包含必要的类型注解
"""

    def _generate_via_api(
        self,
        system: str,
        user: str,
        module_type: str,
        on_stream: Callable = None
    ) -> Dict:
        """通过 API SDK 生成代码"""
        result = self.api_client.chat(
            system, [{"role": "user", "content": user}],
            max_tokens=8192, on_stream=on_stream
        )
        if result["success"]:
            files = self._parse_code_files(result["content"])
            return {
                "success": True,
                "files": files,
                "summary": f"AI生成 {len(files)} 个文件",
                "usage": result.get("usage", {})
            }
        return {"success": False, "files": [], "error": result.get("error", "")}

    def _generate_via_cli(self, system: str, user: str) -> Dict:
        """通过 CLI 生成代码"""
        full_prompt = f"{system}\n\n{user}"
        result = self.cli_client.execute(full_prompt)
        if result["success"]:
            files = self._parse_code_files(result["output"])
            return {
                "success": True,
                "files": files,
                "summary": f"AI生成 {len(files)} 个文件"
            }
        return {"success": False, "files": [], "error": result.get("error", "")}

    def _generate_simulated(self, task: str, module_type: str) -> Dict:
        """模拟代码生成（降级模式）"""
        print(f"{Colors.YELLOW}  ⚠️ 使用模拟模式生成代码（请配置 ANTHROPIC_API_KEY 启用AI）{Colors.END}")
        return {
            "success": True,
            "files": [],
            "summary": f"模拟模式：{module_type}模块代码框架已生成",
            "mode": "simulated"
        }

    def _parse_code_files(self, content: str) -> List[Dict]:
        """从AI输出中解析代码文件"""
        files = []
        lines = content.split("\n")
        current_file = None
        current_content = []

        for line in lines:
            if line.startswith("```") and not line.startswith("``` "):
                if current_file and current_content:
                    files.append({
                        "path": current_file,
                        "content": "\n".join(current_content)
                    })
                current_file = None
                current_content = []
            elif line.startswith("```") and len(line) > 3:
                # 文件标记: ```filename
                current_file = line[3:].strip()
                current_content = []
            elif current_file is not None:
                current_content.append(line)
            elif line.startswith("# ") or line.startswith("// "):
                # 可能是一个文件的开头
                pass

        # 处理最后可能的文件
        if current_file and current_content:
            files.append({
                "path": current_file,
                "content": "\n".join(current_content)
            })

        return files


# ============================================================
# 全局单例
# ============================================================
_claude_integration: Optional[ClaudeIntegration] = None


def get_claude() -> ClaudeIntegration:
    """获取全局 Claude 集成实例"""
    global _claude_integration
    if _claude_integration is None:
        _claude_integration = ClaudeIntegration()
    return _claude_integration


# ============================================================
# 测试
# ============================================================
if __name__ == "__main__":
    claude = ClaudeIntegration()
    print(f"\n集成模式: {claude.mode}")
    print(f"API SDK 可用: {claude.api_client.is_ready}")
    print(f"CLI 可用: {claude.cli_client.is_ready}")
    print(f"真实AI: {claude.is_real()}")

    # 测试代码生成
    result = claude.generate_code(
        "创建一个用户登录接口",
        "backend",
        context={"framework": "FastAPI", "database": "SQLite"}
    )
    print(f"\n代码生成结果: {json.dumps(result, ensure_ascii=False, indent=2)}")