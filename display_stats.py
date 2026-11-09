#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = ["pydantic", "rich"]
# ///
"""Display codebase statistics in the terminal.

Standalone: no imports from the project it scans. Rich is declared in the
PEP 723 header above, so `uv run display_stats.py` works with no setup:

    uv run display_stats.py [path] [--top N] [--no-color] [--selftest]

File list comes from `git ls-files` when available, so .gitignore is honoured
for free; otherwise a filtered os.walk is used.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path

from pydantic import BaseModel
from rich import box
from rich.console import Console, RenderableType
from rich.panel import Panel
from rich.progress_bar import ProgressBar
from rich.table import Table
from rich.text import Text

ACCENT = "#a78bfa"
ACCENT2 = "#22d3ee"
DIM = "grey58"
TEXT = "grey87"
BORDER = "grey35"
GREEN = "#4ade80"
BAR_BG = "grey23"
BAR_COLORS = (
    "#22d3ee",
    "#a78bfa",
    "#4ade80",
    "#facc15",
    "#f87171",
    "#60a5fa",
    "#f472b6",
    "#84cc16",
    "#fb923c",
    "#c084fc",
    "#34d399",
    "#fbbf24",
)

# --------------------------------------------------------------------------- files

IGNORE_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "env",
    "node_modules",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    "dist",
    "build",
    "target",
    ".next",
    ".nuxt",
    "vendor",
    "coverage",
    ".idea",
}


def iter_files(root: Path) -> list[Path]:
    try:
        out = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
            capture_output=True,
            check=True,
        ).stdout
        names = [n for n in out.decode("utf-8", "surrogateescape").split("\0") if n]
        if names:
            return [root / n for n in names]
    except (OSError, subprocess.CalledProcessError):
        pass

    files: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in IGNORE_DIRS)
        files.extend(Path(dirpath) / name for name in sorted(filenames))
    return files


def git_info(root: Path) -> tuple[str, str] | None:
    def run(*args: str) -> str:
        return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, check=True).stdout.strip()

    try:
        return run("rev-parse", "--abbrev-ref", "HEAD"), run("rev-parse", "--short", "HEAD")
    except (OSError, subprocess.CalledProcessError):
        return None


# --------------------------------------------------------------------------- languages

LANGUAGES = {
    ".py": "Python",
    ".pyi": "Python",
    ".js": "JavaScript",
    ".mjs": "JavaScript",
    ".cjs": "JavaScript",
    ".jsx": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".mts": "TypeScript",
    ".cts": "TypeScript",
    ".html": "HTML",
    ".htm": "HTML",
    ".css": "CSS",
    ".scss": "SCSS",
    ".less": "LESS",
    ".json": "JSON",
    ".jsonc": "JSON",
    ".yaml": "YAML",
    ".yml": "YAML",
    ".toml": "TOML",
    ".md": "Markdown",
    ".rst": "reStructuredText",
    ".txt": "Text",
    ".sql": "SQL",
    ".sh": "Shell",
    ".bash": "Shell",
    ".zsh": "Shell",
    ".fish": "Shell",
    ".ps1": "PowerShell",
    ".rs": "Rust",
    ".go": "Go",
    ".java": "Java",
    ".c": "C",
    ".h": "C",
    ".cpp": "C++",
    ".cc": "C++",
    ".hpp": "C++",
    ".cs": "C#",
    ".rb": "Ruby",
    ".php": "PHP",
    ".swift": "Swift",
    ".kt": "Kotlin",
    ".kts": "Kotlin",
    ".lua": "Lua",
    ".r": "R",
    ".dart": "Dart",
    ".scala": "Scala",
    ".ex": "Elixir",
    ".exs": "Elixir",
    ".zig": "Zig",
    ".nim": "Nim",
    ".hs": "Haskell",
    ".ml": "OCaml",
    ".clj": "Clojure",
    ".vue": "Vue",
    ".svelte": "Svelte",
    ".astro": "Astro",
    ".xml": "XML",
    ".svg": "SVG",
    ".graphql": "GraphQL",
    ".proto": "Protocol Buffers",
    ".tf": "Terraform",
    ".ini": "INI",
    ".cfg": "Config",
    ".nix": "Nix",
}
LANGUAGE_BY_NAME = {"Dockerfile": "Docker", "Makefile": "Makefile", "Jenkinsfile": "Groovy"}

_HASH = (
    ".py",
    ".pyi",
    ".sh",
    ".bash",
    ".zsh",
    ".yml",
    ".yaml",
    ".toml",
    ".rb",
    ".pl",
    ".r",
    ".ps1",
    ".cfg",
    ".ini",
    ".conf",
    ".env",
    ".tf",
    ".nix",
    ".ex",
    ".exs",
)
_SLASH = (
    ".js",
    ".mjs",
    ".cjs",
    ".jsx",
    ".ts",
    ".tsx",
    ".java",
    ".c",
    ".h",
    ".cpp",
    ".cc",
    ".hpp",
    ".cs",
    ".go",
    ".rs",
    ".swift",
    ".kt",
    ".kts",
    ".php",
    ".scala",
    ".dart",
    ".zig",
    ".vue",
    ".svelte",
    ".css",
    ".scss",
    ".less",
    ".proto",
)
_DASH = (".sql", ".lua", ".hs")
_MARKUP = (".html", ".htm", ".xml", ".svg")


def comment_prefixes(ext: str) -> tuple[str, ...]:
    if ext in _HASH:
        return ("#",)
    if ext in _SLASH:
        return ("//", "/*", "*")
    if ext in _DASH:
        return ("--", "#")
    if ext in _MARKUP:
        return ("<!--",)
    return ()


def language_of(path: Path) -> str:
    if path.name in LANGUAGE_BY_NAME:
        return LANGUAGE_BY_NAME[path.name]
    return LANGUAGES.get(path.suffix.lower(), path.suffix[1:].upper() or "Other")


# --------------------------------------------------------------------------- analysis


class FileStat(BaseModel):
    rel: Path
    size: int
    lines: int
    blank: int
    comment: int
    chars: int
    longest: int

    @property
    def code(self) -> int:
        return self.lines - self.blank - self.comment


def collect(root: Path, files: list[Path]) -> tuple[list[FileStat], int]:
    stats: list[FileStat] = []
    skipped = 0
    for path in files:
        try:
            data = path.read_bytes()
        except OSError:
            skipped += 1
            continue
        if b"\0" in data[:8192]:
            skipped += 1
            continue

        lines = data.decode("utf-8", "replace").splitlines()
        prefixes = comment_prefixes(path.suffix.lower())
        blank = sum(1 for line in lines if not line.strip())
        comment = sum(1 for line in lines if any(line.strip().startswith(p) for p in prefixes))
        try:
            rel = path.relative_to(root)
        except ValueError:
            rel = Path(path.name)
        stats.append(
            FileStat(
                rel=rel,
                size=len(data),
                lines=len(lines),
                blank=blank,
                comment=comment,
                chars=sum(len(line) for line in lines) + len(lines),
                longest=max((len(line) for line in lines), default=0),
            )
        )
    return stats, skipped


# --------------------------------------------------------------------------- formatting


def human_size(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:,.0f} {unit}" if unit == "B" else f"{n:,.1f} {unit}"
        n /= 1024
    return f"{n:,.1f} TB"


def shorten(text: str, width: int) -> str:
    return text if len(text) <= width else "…" + text[-(width - 1) :]


def progress(value: float, peak: float, color: str) -> ProgressBar:
    return ProgressBar(
        total=max(peak, 1.0),
        completed=value,
        style=BAR_BG,
        complete_style=color,
        finished_style=color,
    )


def panel(title: str, body: RenderableType) -> Panel:
    return Panel(
        body,
        title=Text(title, style=ACCENT),
        title_align="left",
        border_style=BORDER,
        box=box.ROUNDED,
        expand=True,
        padding=(0, 1),
    )


# --------------------------------------------------------------------------- render


def render(console: Console, root: Path, stats: list[FileStat], skipped: int, elapsed: float, top: int) -> None:
    total_lines = sum(s.lines for s in stats)
    total_code = sum(s.code for s in stats)
    total_comment = sum(s.comment for s in stats)
    total_blank = sum(s.blank for s in stats)
    total_size = sum(s.size for s in stats)
    total_chars = sum(s.chars for s in stats)
    longest = max((s.longest for s in stats), default=0)

    def pct(part: int) -> float:
        return 100.0 * part / total_lines if total_lines else 0.0

    # header
    git = git_info(root)
    meta = [f"{len(stats):,} files", f"{elapsed:.2f}s"]
    if git:
        meta.insert(0, f"git {git[0]} @ {git[1]}")
    console.print()
    console.print(Text("◆ ", style=ACCENT) + Text(root.name or str(root), style=f"bold {TEXT}"))
    console.print(Text("  " + str(root), style=DIM))
    console.print(Text("  " + " · ".join(meta), style=DIM))
    console.print()

    # overview
    cells = [
        ("Files", f"{len(stats):,}"),
        ("Lines", f"{total_lines:,}"),
        ("Size", human_size(total_size)),
        ("Code", f"{total_code:,}"),
        ("Comments", f"{total_comment:,}"),
        ("Blank", f"{total_blank:,}"),
        ("Avg/file", f"{total_lines / len(stats):,.0f}" if stats else "0"),
        ("Avg length", f"{total_chars / total_lines:,.0f}" if total_lines else "0"),
        ("Longest line", f"{longest:,}"),
    ]
    if skipped:
        cells.append(("Skipped", f"{skipped:,}"))
    grid = Table.grid(padding=(0, 4), expand=True)
    for _ in range(3):
        grid.add_column(ratio=1)
    for i in range(0, len(cells), 3):
        row = [Text.assemble((label + " ", DIM), (value, f"bold {TEXT}")) for label, value in cells[i : i + 3]]
        grid.add_row(*(row + [Text()] * (3 - len(row))))
    console.print(panel("overview", grid))
    console.print()

    # languages
    by_lang: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for stat in stats:
        entry = by_lang[language_of(stat.rel)]
        entry[0] += 1
        entry[1] += stat.lines
    langs = sorted(by_lang.items(), key=lambda kv: kv[1][1], reverse=True)
    shown = langs[:12]
    peak = shown[0][1][1] if shown else 0
    if shown:
        table = Table(box=None, expand=True, pad_edge=False, header_style=DIM)
        table.add_column("language", no_wrap=True, min_width=12)
        table.add_column("files", justify="right", no_wrap=True)
        table.add_column("lines", justify="right", no_wrap=True)
        table.add_column("share", justify="right", no_wrap=True)
        table.add_column("", ratio=1)
        for i, (name, (files, lines)) in enumerate(shown):
            color = BAR_COLORS[i % len(BAR_COLORS)]
            table.add_row(
                Text(name, style=color),
                f"{files:,}",
                f"{lines:,}",
                f"{pct(lines):.1f}%",
                progress(lines, peak, color),
            )
        if len(langs) > len(shown):
            table.add_row(Text(f"… and {len(langs) - len(shown)} more", style=DIM), "", "", "", "")
        console.print(panel("languages", table))
    else:
        console.print(panel("languages", Text("no text files", style=DIM)))
    console.print()

    # composition
    table = Table(box=None, expand=True, pad_edge=False, header_style=DIM)
    table.add_column("kind", no_wrap=True, min_width=10)
    table.add_column("lines", justify="right", no_wrap=True)
    table.add_column("share", justify="right", no_wrap=True)
    table.add_column("", ratio=1)
    for label, count, color in (
        ("code", total_code, GREEN),
        ("comments", total_comment, ACCENT2),
        ("blank", total_blank, BORDER),
    ):
        table.add_row(Text(label, style=color), f"{count:,}", f"{pct(count):.1f}%", progress(count, total_lines, color))
    console.print(panel("line composition", table))
    console.print()

    # largest files
    largest = sorted(stats, key=lambda s: s.lines, reverse=True)[: max(1, top)]
    if largest:
        path_width = max(20, console.width - 44)
        table = Table(box=None, expand=True, pad_edge=False, header_style=DIM)
        table.add_column("lines", justify="right", no_wrap=True)
        table.add_column("file", ratio=1, no_wrap=True)
        table.add_column("", width=14)
        for stat in largest:
            table.add_row(
                f"{stat.lines:,}",
                Text(shorten(str(stat.rel), path_width), style=TEXT),
                progress(stat.lines, largest[0].lines, ACCENT2),
            )
        console.print(panel("largest files", table))
    else:
        console.print(panel("largest files", Text("none", style=DIM)))
    console.print()

    # directories
    by_dir: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for stat in stats:
        key = stat.rel.parts[0] if len(stat.rel.parts) > 1 else "(root)"
        by_dir[key][0] += 1
        by_dir[key][1] += stat.lines
    dirs = sorted(by_dir.items(), key=lambda kv: kv[1][1], reverse=True)[: max(1, top)]
    if dirs:
        peak = dirs[0][1][1]
        table = Table(box=None, expand=True, pad_edge=False, header_style=DIM)
        table.add_column("directory", no_wrap=True, min_width=16)
        table.add_column("files", justify="right", no_wrap=True)
        table.add_column("lines", justify="right", no_wrap=True)
        table.add_column("share", justify="right", no_wrap=True)
        table.add_column("", ratio=1)
        for i, (name, (files, lines)) in enumerate(dirs):
            color = BAR_COLORS[i % len(BAR_COLORS)]
            table.add_row(
                Text(name, style=color),
                f"{files:,}",
                f"{lines:,}",
                f"{pct(lines):.1f}%",
                progress(lines, peak, color),
            )
        console.print(panel("directories", table))
    else:
        console.print(panel("directories", Text("none", style=DIM)))
    console.print()


# --------------------------------------------------------------------------- cli


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Display statistics about a codebase.")
    parser.add_argument("path", nargs="?", default=".", help="directory to scan (default: .)")
    parser.add_argument("--top", type=int, default=8, help="rows in file/directory lists (default: 8)")
    parser.add_argument("--no-color", action="store_true", help="disable ANSI colors")
    parser.add_argument("--selftest", action="store_true", help="run internal checks and exit")
    return parser.parse_args(argv)


def selftest() -> None:
    assert human_size(0) == "0 B"
    assert human_size(1536) == "1.5 KB"
    assert human_size(5 * 1024**3) == "5.0 GB"
    assert shorten("a/b/c.py", 6) == "…/c.py"
    assert language_of(Path("x.py")) == "Python"
    assert language_of(Path("Dockerfile")) == "Docker"
    assert language_of(Path("weird.xyz")) == "XYZ"
    assert comment_prefixes(".py") == ("#",)
    assert comment_prefixes(".js") == ("//", "/*", "*")
    assert comment_prefixes(".md") == ()
    print("self-test ok")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.selftest:
        selftest()
        return 0

    root = Path(args.path).expanduser().resolve()
    if not root.is_dir():
        print(f"error: not a directory: {root}", file=sys.stderr)
        return 2

    console = Console(no_color=args.no_color or "NO_COLOR" in os.environ)
    started = time.perf_counter()
    files = iter_files(root)
    stats, skipped = collect(root, files)
    elapsed = time.perf_counter() - started

    render(console, root, stats, skipped, elapsed, max(1, args.top))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
