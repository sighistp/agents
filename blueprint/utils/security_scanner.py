"""Security scanner — wraps bandit (Python) + npm audit (Node) + custom patterns."""
import json
import logging
import re
import subprocess
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class SecurityScanner:
    _CUSTOM_PATTERNS = [
        # Match strings that look like actual secrets (alphanumeric, 12+ chars, no placeholders)
        (r'(?i)(api[_-]?key|secret[_-]?key|password|access[_-]?token)\s*[=:]\s*["\'][A-Za-z0-9_\-]{12,}["\']',
         "hardcoded_secret", "high", "检测到硬编码密钥/密码"),
        (r'(?i)AWS_(ACCESS|SECRET)_KEY',
         "hardcoded_secret", "critical", "检测到 AWS 密钥"),
        (r'-----BEGIN (RSA |EC )?PRIVATE KEY-----',
         "hardcoded_secret", "critical", "检测到私钥"),
    ]

    def scan_project(self, project_dir: str) -> dict[str, Any]:
        issues = []
        skip = {'.git', 'node_modules', '__pycache__', '.venv'}

        # 1. Python: bandit
        issues.extend(self._run_bandit(project_dir))

        # 2. Node: npm audit
        issues.extend(self._run_npm_audit(project_dir))

        # 3. Custom patterns (hardcoded secrets)
        project_path = Path(project_dir)
        for f in project_path.rglob("*"):
            if not f.is_file() or f.suffix not in ('.py', '.js', '.ts', '.html'):
                continue
            if any(part in skip for part in f.parts):
                continue
            try:
                content = f.read_text(encoding="utf-8", errors="replace")
                for line_num, line in enumerate(content.splitlines(), 1):
                    for pattern, category, severity, description in self._CUSTOM_PATTERNS:
                        if re.search(pattern, line):
                            issues.append({
                                "file": str(f.relative_to(project_path)),
                                "line": line_num,
                                "severity": severity,
                                "category": category,
                                "description": description,
                                "code": line.strip()[:100],
                            })
            except Exception as e:
                logger.warning("Failed to scan file for security patterns: %s", e, exc_info=True)

        return self._compile_report(issues)

    def _run_bandit(self, project_dir: str) -> list[dict]:
        issues = []
        try:
            result = subprocess.run(
                ["bandit", "-r", project_dir, "-f", "json", "-q", "--severity-level", "medium"],
                capture_output=True, text=True, timeout=30
            )
            if result.stdout:
                data = json.loads(result.stdout)
                for item in data.get("results", []):
                    issues.append({
                        "file": item.get("filename", "").replace(project_dir + "/", "").replace(project_dir + "\\", ""),
                        "line": item.get("line_number", 0),
                        "severity": item.get("issue_severity", "MEDIUM").lower(),
                        "category": f"bandit_{item.get('test_id', 'unknown')}",
                        "description": item.get("issue_text", ""),
                        "code": item.get("code", "")[:100],
                    })
        except FileNotFoundError as e:
            logger.warning("Bandit not found, skipping Python security scan: %s", e)
        except Exception as e:
            logger.warning("Bandit scan failed: %s", e, exc_info=True)
        return issues

    def _run_npm_audit(self, project_dir: str) -> list[dict]:
        issues = []
        package_json = Path(project_dir) / "package.json"
        if not package_json.exists():
            return issues
        try:
            result = subprocess.run(
                ["npm", "audit", "--json"],
                cwd=project_dir, capture_output=True, text=True, timeout=30
            )
            if result.stdout:
                data = json.loads(result.stdout)
                for vuln in data.get("vulnerabilities", {}).values():
                    severity = vuln.get("severity", "info")
                    issues.append({
                        "file": "package.json",
                        "line": 0,
                        "severity": severity if severity in ("critical", "high", "medium", "low", "info") else "medium",
                        "category": "npm_vulnerability",
                        "description": f"{vuln.get('name', 'unknown')}: {vuln.get('title', '')}",
                        "code": "",
                    })
        except FileNotFoundError as e:
            logger.warning("npm not found, skipping Node security scan: %s", e)
        except Exception as e:
            logger.warning("npm audit failed: %s", e, exc_info=True)
        return issues

    def _compile_report(self, issues: list[dict]) -> dict[str, Any]:
        penalty_map = {"critical": 30, "high": 15, "medium": 5, "low": 2, "info": 0}
        score = max(0, 100 - sum(penalty_map.get(i["severity"], 0) for i in issues))
        return {
            "total": len(issues),
            "critical": sum(1 for i in issues if i["severity"] == "critical"),
            "high": sum(1 for i in issues if i["severity"] == "high"),
            "medium": sum(1 for i in issues if i["severity"] == "medium"),
            "low": sum(1 for i in issues if i["severity"] == "low"),
            "score": score,
            "issues": issues,
        }
