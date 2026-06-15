"""Doc generator — generate README, API docs, architecture diagram."""
from pathlib import Path
from typing import Any


class DocGenerator:
    def generate(self, project_dir: str, requirement: str) -> dict[str, str]:
        """Generate documentation files for a project."""
        project_path = Path(project_dir)
        files = self._scan_files(project_path)
        tech_stack = self._detect_tech_stack(project_path)

        return {
            "readme": self._generate_readme(requirement, tech_stack, files),
            "api_docs": self._generate_api_docs(files),
            "architecture": self._generate_architecture(files),
        }

    def _scan_files(self, project_path: Path) -> list[Path]:
        skip = {'.git', 'node_modules', '__pycache__', '.venv', '_blueprint', '.snapshots'}
        files = []
        for f in project_path.rglob("*"):
            if f.is_file() and not any(part in skip for part in f.parts):
                files.append(f)
        return files

    def _detect_tech_stack(self, project_path: Path) -> list[str]:
        stack = []
        files = [f.name for f in self._scan_files(project_path)]
        if any(f.endswith('.py') for f in files):
            stack.append("python")
        if 'package.json' in files:
            stack.append("node")
        if any(f.endswith('.html') for f in files):
            stack.append("html")
        if any(f.endswith(('.js', '.ts')) for f in files):
            stack.append("javascript")
        return stack if stack else ["unknown"]

    def _generate_readme(self, requirement: str, tech_stack: list[str], files: list[Path]) -> str:
        file_list = "\n".join(f"- `{f.name}`" for f in files[:20])
        tech_str = ", ".join(tech_stack)

        readme = f"""# {requirement[:50]}

## 简介
{requirement}

## 技术栈
{tech_str}

## 项目结构
{file_list}

## 安装与运行
"""
        if "python" in tech_stack:
            readme += "```bash\npip install -r requirements.txt\npython main.py\n```\n"
        if "node" in tech_stack:
            readme += "```bash\nnpm install\nnpm start\n```\n"
        if "html" in tech_stack:
            readme += "直接在浏览器中打开 `index.html`\n"

        return readme

    def _generate_api_docs(self, files: list[Path]) -> str:
        """Generate API documentation from code."""
        routes = []
        for f in files:
            if f.suffix == ".py":
                try:
                    content = f.read_text(encoding="utf-8", errors="replace")
                    for line in content.splitlines():
                        line = line.strip()
                        if line.startswith("@app.") or line.startswith("@router."):
                            routes.append(line)
                except Exception:
                    pass

        if not routes:
            return "No API routes detected."

        docs = "## API Routes\n\n"
        for route in routes:
            docs += f"- `{route}`\n"
        return docs

    def _generate_architecture(self, files: list[Path]) -> str:
        """Generate Mermaid architecture diagram."""
        py_files = [f.name for f in files if f.suffix == ".py"]
        html_files = [f.name for f in files if f.suffix in ('.html', '.js', '.css')]

        diagram = "```mermaid\ngraph TD\n"
        if py_files:
            diagram += "    Backend[Backend]\n"
            for f in py_files[:5]:
                safe = f.replace(".", "_")
                diagram += f"    Backend --> {safe}[{f}]\n"
        if html_files:
            diagram += "    Frontend[Frontend]\n"
            for f in html_files[:5]:
                safe = f.replace(".", "_").replace("-", "_")
                diagram += f"    Frontend --> {safe}[{f}]\n"
        diagram += "```\n"
        return diagram
