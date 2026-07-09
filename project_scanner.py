"""
项目上下文扫描器
=================
提供项目目录结构分析、文件依赖检测、相关文件定位等功能。
为 Orchestrator 和 ChildAgent 提供项目上下文感知能力。
"""

import ast
import io
import sys

# 修复Windows GBK编码问题（仅在直接运行时）
if sys.platform == 'win32' and __name__ == '__main__':
    try:
        if not isinstance(sys.stdout, io.TextIOWrapper) or sys.stdout.encoding != 'utf-8':
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
    except (ValueError, AttributeError):
        pass

import re
from pathlib import Path
from typing import Dict, List, Tuple
from dataclasses import dataclass, field


@dataclass
class FileInfo:
    """文件信息"""
    path: Path
    rel_path: str
    name: str
    suffix: str
    size: int
    language: str = ""
    imports: List[str] = field(default_factory=list)
    exports: List[str] = field(default_factory=list)
    is_test: bool = False


@dataclass
class ProjectContext:
    """项目上下文"""
    root: Path
    name: str
    files: List[FileInfo] = field(default_factory=list)
    languages: Dict[str, int] = field(default_factory=dict)  # 语言 → 文件数
    modules: Dict[str, List[str]] = field(default_factory=dict)  # 模块 → 文件列表
    dependency_graph: Dict[str, List[str]] = field(default_factory=dict)  # 文件 → 依赖文件
    total_lines: int = 0
    total_files: int = 0


# ============================================================
# 核心扫描函数
# ============================================================
def scan_project(project_dir: str) -> ProjectContext:
    """
    扫描整个项目目录

    Args:
        project_dir: 项目根目录路径

    Returns:
        ProjectContext: 包含文件列表、语言分布、依赖关系等
    """
    root = Path(project_dir).resolve()
    if not root.exists():
        raise FileNotFoundError(f"项目目录不存在: {project_dir}")

    ctx = ProjectContext(root=root, name=root.name)

    skip_dirs = {
        '.git', '__pycache__', '.checkpoints', 'node_modules',
        'workspaces', 'logs', '.claude', 'venv', '.venv',
        '.idea', '.vscode', 'dist', 'build', '.next', 'target'
    }
    skip_extensions = {
        '.pyc', '.pyo', '.pkl', '.log', '.lock', '.min.js',
        '.map', '.d.ts', '.snap', '.png', '.jpg', '.ico', '.svg'
    }

    for file_path in root.rglob("*"):
        if not file_path.is_file():
            continue

        parts = set(file_path.parts)
        if parts & skip_dirs:
            continue
        if file_path.suffix in skip_extensions:
            continue

        try:
            rel = file_path.relative_to(root)
            info = FileInfo(
                path=file_path,
                rel_path=str(rel),
                name=file_path.name,
                suffix=file_path.suffix,
                size=file_path.stat().st_size,
                language=_detect_language(file_path.suffix),
                is_test=_is_test_file(file_path.name),
            )

            # 解析导入（Python文件）
            if info.suffix == '.py':
                info.imports, info.exports = _parse_python_file(file_path)

            ctx.files.append(info)
            ctx.total_lines += _count_lines(file_path)
            ctx.total_files += 1

            # 统计语言分布
            lang = info.language
            ctx.languages[lang] = ctx.languages.get(lang, 0) + 1

            # 按模块分组
            module = _get_module(rel)
            if module not in ctx.modules:
                ctx.modules[module] = []
            ctx.modules[module].append(info.rel_path)

            # 依赖图
            ctx.dependency_graph[info.rel_path] = info.imports

        except Exception:
            pass

    return ctx


def find_relevant_files(
    task_description: str,
    project_context: ProjectContext,
    max_results: int = 5
) -> List[FileInfo]:
    """
    根据任务描述找到最相关的文件

    Args:
        task_description: 任务描述
        project_context: 项目上下文
        max_results: 最大返回数量

    Returns:
        相关文件列表（按相关性排序）
    """
    task_lower = task_description.lower()
    scored = []

    # 提取任务中的关键词
    keywords = _extract_keywords(task_description)

    for f in project_context.files:
        score = 0
        name_lower = f.name.lower()
        rel_lower = f.rel_path.lower()

        # 1. 显式路径匹配
        if rel_lower in task_lower or name_lower in task_lower:
            score += 100

        # 2. 关键词匹配
        for kw in keywords:
            if kw in name_lower:
                score += 10
            if kw in rel_lower:
                score += 5
            # 检查文件内容中的关键词匹配（如果文件不大）
            if f.size < 50000:
                try:
                    content = f.path.read_text(encoding='utf-8')[:5000].lower()
                    if kw in content:
                        score += 2
                except Exception:
                    pass

        # 3. 语言匹配
        if "api" in task_lower or "接口" in task_lower or "后端" in task_lower:
            if f.language in ("Python", "TypeScript", "JavaScript"):
                score += 3
        if "前端" in task_lower or "页面" in task_lower or "frontend" in task_lower:
            if f.language in ("TypeScript", "JavaScript", "CSS", "HTML"):
                score += 3
        if "数据库" in task_lower or "sql" in task_lower or "database" in task_lower:
            if f.language == "SQL" or (f.language == "Python" and "model" in name_lower):
                score += 3

        # 4. 测试文件降权
        if f.is_test:
            score = max(0, score - 5)

        if score > 0:
            scored.append((score, f))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [f for _, f in scored[:max_results]]


def read_file_context(
    file_paths: List[str],
    project_dir: str,
    max_chars_per_file: int = 5000
) -> Dict[str, str]:
    """
    读取文件内容作为AI上下文

    Args:
        file_paths: 文件路径列表（相对路径）
        project_dir: 项目根目录
        max_chars_per_file: 每个文件最大读取字符数

    Returns:
        {文件路径: 内容}
    """
    root = Path(project_dir)
    contents = {}

    for fpath in file_paths:
        full_path = root / fpath
        if not full_path.exists():
            continue
        try:
            content = full_path.read_text(encoding='utf-8')
            if len(content) > max_chars_per_file:
                # 截断并添加标记
                content = content[:max_chars_per_file] + f"\n\n... (截断，原文件共 {len(content)} 字符)"
            contents[fpath] = content
        except Exception:
            pass

    return contents


def get_project_summary(ctx: ProjectContext) -> str:
    """
    生成项目摘要（用于AI上下文）

    Args:
        ctx: 项目上下文

    Returns:
        人类可读的项目摘要
    """
    lines = []
    lines.append(f"## 项目: {ctx.name}")
    lines.append(f"根目录: {ctx.root}")
    lines.append(f"文件总数: {ctx.total_files}")
    lines.append(f"代码总行数: {ctx.total_lines}")
    lines.append("")

    lines.append("### 语言分布")
    for lang, count in sorted(ctx.languages.items(), key=lambda x: x[1], reverse=True):
        lines.append(f"  - {lang}: {count} 文件")

    lines.append("")
    lines.append("### 模块结构")
    for module, files in sorted(ctx.modules.items()):
        lines.append(f"  - {module}/ ({len(files)} 文件)")
        for f in files[:5]:
            lines.append(f"    - {f}")
        if len(files) > 5:
            lines.append(f"    ... 还有 {len(files) - 5} 个文件")

    return "\n".join(lines)


# ============================================================
# 内部辅助函数
# ============================================================
def _detect_language(suffix: str) -> str:
    """根据扩展名检测语言"""
    mapping = {
        '.py': 'Python',
        '.ts': 'TypeScript',
        '.tsx': 'TypeScript',
        '.js': 'JavaScript',
        '.jsx': 'JavaScript',
        '.css': 'CSS',
        '.html': 'HTML',
        '.sql': 'SQL',
        '.json': 'JSON',
        '.yaml': 'YAML',
        '.yml': 'YAML',
        '.md': 'Markdown',
        '.toml': 'TOML',
        '.cfg': 'Config',
        '.ini': 'Config',
        '.env': 'Config',
        '.sh': 'Shell',
        '.ps1': 'PowerShell',
        '.rs': 'Rust',
        '.go': 'Go',
        '.java': 'Java',
        '.cpp': 'C++',
        '.c': 'C',
        '.h': 'C/C++ Header',
    }
    return mapping.get(suffix.lower(), suffix.lstrip('.') or 'Unknown')


def _is_test_file(filename: str) -> bool:
    """判断是否为测试文件"""
    name_lower = filename.lower()
    return (
        name_lower.startswith('test_') or
        name_lower.endswith('_test.py') or
        name_lower.endswith('_test.ts') or
        name_lower.endswith('.test.ts') or
        name_lower.endswith('.test.js') or
        name_lower.endswith('.spec.ts') or
        name_lower.endswith('.spec.js') or
        'test' in name_lower.split('.')[0]
    )


def _parse_python_file(file_path: Path) -> Tuple[List[str], List[str]]:
    """解析Python文件的导入和导出"""
    imports = []
    exports = []

    try:
        tree = ast.parse(file_path.read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            # 导入
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append(node.module)

            # 导出（函数和类定义）
            if isinstance(node, ast.FunctionDef):
                if not node.name.startswith('_'):
                    exports.append(node.name)
            elif isinstance(node, ast.ClassDef):
                if not node.name.startswith('_'):
                    exports.append(node.name)
    except Exception:
        pass

    return imports, exports


def _count_lines(file_path: Path) -> int:
    """统计文件行数"""
    try:
        return len(file_path.read_text(encoding='utf-8').splitlines())
    except Exception:
        return 0


def _get_module(rel_path: Path) -> str:
    """获取文件所属模块"""
    parts = rel_path.parts
    if len(parts) > 1:
        return parts[0]  # 第一级目录作为模块名
    return "root"


def _extract_keywords(task: str) -> List[str]:
    """从任务描述中提取关键词"""
    # 移除常见停用词
    stopwords = {
        '的', '了', '在', '是', '我', '有', '和', '就', '不', '人', '都', '一',
        '一个', '上', '也', '很', '到', '说', '要', '去', '你', '会', '着',
        '没有', '看', '好', '自己', '这', 'the', 'a', 'an', 'is', 'are', 'was',
        'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did',
        'will', 'would', 'could', 'should', 'may', 'might', 'can', 'shall',
        'to', 'of', 'in', 'for', 'on', 'with', 'at', 'from', 'by', 'about',
        'as', 'into', 'through', 'during', 'before', 'after',
    }

    # 提取中英文单词
    words = re.findall(r'[一-鿿]+|[a-zA-Z_]\w*', task.lower())

    # 过滤停用词和短词
    keywords = []
    for w in words:
        if w not in stopwords and len(w) >= 2:
            keywords.append(w)

    return keywords


# ============================================================
# 命令行入口
# ============================================================
def main():
    import sys

    if len(sys.argv) < 2:
        print("用法: python project_scanner.py <项目目录> [--summary]")
        print("  --summary  只输出项目摘要")
        sys.exit(1)

    project_dir = sys.argv[1]
    summary_only = "--summary" in sys.argv

    ctx = scan_project(project_dir)

    if summary_only:
        print(get_project_summary(ctx))
    else:
        print(f"项目: {ctx.name}")
        print(f"文件: {ctx.total_files} | 行数: {ctx.total_lines}")
        print(f"语言: {ctx.languages}")
        print(f"模块: {list(ctx.modules.keys())}")
        print(f"\n文件列表:")
        for f in sorted(ctx.files, key=lambda x: x.rel_path):
            test_mark = " [TEST]" if f.is_test else ""
            print(f"  {f.rel_path} ({f.language}, {f.size}B){test_mark}")


if __name__ == "__main__":
    main()