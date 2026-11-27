#!/usr/bin/env python3
"""Конвертирует книги из books/ в Markdown, чтобы субагенты читали их частями."""

from argparse import ArgumentParser
from collections.abc import MutableSequence, Sequence
from pathlib import Path
from shutil import which
from subprocess import CalledProcessError, run
from textwrap import wrap

__all__ = [
    "main",
]

SUPPORTED_SUFFIXES = frozenset({".pdf", ".epub", ".docx", ".html", ".htm", ".txt", ".md"})
# Read обрезает строки длиннее 2000 символов, а markitdown пишет абзац одной строкой.
MAX_LINE_LENGTH = 1000
WRAP_WIDTH = 500
# В книге меньше этого объёма почти наверняка нет текста: скан без текстового слоя или битый файл.
MIN_BOOK_CHARS = 20_000


def markitdown_command() -> Sequence[str]:
    """Находит markitdown или запускает его через uvx без установки."""
    if which("markitdown") is not None:
        return ("markitdown",)
    if which("uvx") is not None:
        return ("uvx", "--from", "markitdown[all]", "markitdown")
    raise SystemExit("Нужен markitdown: pip install 'markitdown[all]' или uv (https://docs.astral.sh/uv/)")


def wrap_long_lines(text: str) -> str:
    """Переносит длинные строки, чтобы Read не обрезал абзацы."""
    lines: MutableSequence[str] = []
    for line in text.splitlines():
        if len(line) > MAX_LINE_LENGTH:
            lines.extend(wrap(line, width=WRAP_WIDTH, break_on_hyphens=False))
        else:
            lines.append(line)
    return "\n".join(lines) + "\n"


def convert(command: Sequence[str], book: Path, target: Path) -> str:
    """Конвертирует одну книгу и возвращает строку отчёта о ней."""
    if book.suffix.lower() not in SUPPORTED_SUFFIXES:
        return f"НЕ ПОДДЕРЖИВАЕТСЯ  {book.name}: сконвертировать в EPUB через Calibre (ebook-convert книга.fb2 книга.epub)"
    if target.exists() and target.stat().st_mtime >= book.stat().st_mtime:
        return f"УЖЕ ЕСТЬ  {target}"
    try:
        result = run([*command, str(book)], capture_output=True, check=True, text=True)
    except CalledProcessError as error:
        last_line = error.stderr.strip().rpartition("\n")[2]
        return f"ОШИБКА  {book.name}: {last_line}"
    text = wrap_long_lines(result.stdout)
    target.write_text(text, encoding="utf-8")
    line_count = text.count("\n")
    if len(text) < MIN_BOOK_CHARS:
        return f"МАЛО ТЕКСТА  {target}: {len(text)} символов — похоже на скан, нужен файл с текстовым слоем или OCR"
    return f"ГОТОВО  {target}: {len(text)} символов, {line_count} строк"


def main() -> int:
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("plugin_dir", type=Path, help="папка плагина с подпапкой books/")
    args = parser.parse_args()
    books_dir: Path = args.plugin_dir / "books"
    output_dir: Path = args.plugin_dir / ".build" / "md"
    books = sorted(path for path in books_dir.iterdir() if path.is_file() and not path.name.startswith("."))
    if not books:
        raise SystemExit(f"В {books_dir} нет книг")
    output_dir.mkdir(parents=True, exist_ok=True)
    command = markitdown_command()
    reports = [convert(command, book, output_dir / f"{book.stem}.md") for book in books]
    print("\n".join(reports))
    return 0 if all(report.startswith(("ГОТОВО", "УЖЕ ЕСТЬ")) for report in reports) else 1


if __name__ == "__main__":
    raise SystemExit(main())
