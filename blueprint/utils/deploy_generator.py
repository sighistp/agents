"""Deploy generator — generate Dockerfile, docker-compose, start scripts."""
from pathlib import Path
from typing import Any


class DeployGenerator:
    def generate(self, project_dir: str) -> dict[str, str]:
        """Generate deployment files for a project."""
        project_path = Path(project_dir)
        tech = self._detect_type(project_path)

        files = {}
        files["Dockerfile"] = self._dockerfile(tech)
        files["docker-compose.yml"] = self._compose(tech)
        files["start.sh"] = self._start_script(tech)
        files[".dockerignore"] = self._dockerignore()
        return files

    def _detect_type(self, project_path: Path) -> str:
        names = [f.name for f in project_path.rglob("*") if f.is_file()]
        if any(n == "package.json" for n in names):
            return "node"
        if any(n.endswith(".py") for n in names):
            return "python"
        if any(n.endswith((".html", ".js")) for n in names):
            return "static"
        return "python"

    def _dockerfile(self, tech: str) -> str:
        templates = {
            "python": (
                "FROM python:3.12-slim\n"
                "WORKDIR /app\n"
                "COPY . .\n"
                "EXPOSE 8000\n"
                "CMD [\"python\", \"main.py\"]\n"
            ),
            "node": (
                "FROM node:20-alpine\n"
                "WORKDIR /app\n"
                "COPY package*.json .\n"
                "RUN npm ci\n"
                "COPY . .\n"
                "EXPOSE 3000\n"
                "CMD [\"npm\", \"start\"]\n"
            ),
            "static": (
                "FROM nginx:alpine\n"
                "COPY . /usr/share/nginx/html\n"
                "EXPOSE 80\n"
            ),
        }
        return templates.get(tech, templates["python"])

    def _compose(self, tech: str) -> str:
        port = "8000" if tech == "python" else "3000" if tech == "node" else "80"
        return (
            f"services:\n"
            f"  app:\n"
            f"    build: .\n"
            f"    ports:\n"
            f"      - \"{port}:{port}\"\n"
            f"    restart: unless-stopped\n"
        )

    def _start_script(self, tech: str) -> str:
        if tech == "python":
            return "#!/bin/bash\npip install -r requirements.txt 2>/dev/null\npython main.py\n"
        if tech == "node":
            return "#!/bin/bash\nnpm install\nnpm start\n"
        return "#!/bin/bash\necho 'Open index.html in browser'\n"

    def _dockerignore(self) -> str:
        return "node_modules/\n__pycache__/\n.git/\n.env\n*.db\n"
