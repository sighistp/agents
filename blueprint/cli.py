"""CLI tool for Blueprint — command-line interface."""
import json
import sys
from pathlib import Path

import click


def _projects_dir() -> Path:
    from blueprint.config import settings
    return Path(settings.project_dir) if settings.project_dir else Path("projects")


@click.group()
@click.version_option(version="1.0.0")
def cli():
    """Blueprint — AI 全栈开发平台 CLI"""
    pass


@cli.command()
def list():
    """List all projects."""
    pdir = _projects_dir()
    if not pdir.exists():
        click.echo("No projects found.")
        return

    found = False
    for entry in sorted(pdir.iterdir()):
        meta_path = entry / "meta.json"
        if entry.is_dir() and meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                req = meta.get("requirement", "")[:40]
                status = meta.get("status", "unknown")
                click.echo(f"  {entry.name:20s}  {status:12s}  {req}")
                found = True
            except Exception:
                pass

    if not found:
        click.echo("No projects found.")


@cli.command()
@click.argument("project_id")
def status(project_id):
    """Show project status."""
    pdir = _projects_dir() / project_id
    meta_path = pdir / "meta.json"
    if not meta_path.exists():
        click.echo(f"Project '{project_id}' not found.", err=True)
        sys.exit(1)

    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    click.echo(f"Project: {project_id}")
    click.echo(f"Status:  {meta.get('status', 'unknown')}")
    click.echo(f"Require: {meta.get('requirement', '')}")
    click.echo(f"Iter:    {meta.get('iteration', 0)}")


@cli.command()
@click.argument("project_id")
@click.option("--output", "-o", default=".", help="Output directory")
def download(project_id, output):
    """Download project files."""
    import zipfile
    pdir = _projects_dir() / project_id
    if not pdir.exists():
        click.echo(f"Project '{project_id}' not found.", err=True)
        sys.exit(1)

    out_path = Path(output) / f"{project_id}.zip"
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in sorted(pdir.rglob("*")):
            if f.is_file():
                zf.write(f, str(f.relative_to(pdir)))

    click.echo(f"Downloaded to {out_path}")


if __name__ == "__main__":
    cli()
