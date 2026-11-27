#!/usr/bin/env python3
"""Создаёт файлы плагина по шаблону, не перезаписывая существующие."""

from argparse import ArgumentParser
from collections.abc import Mapping, MutableMapping
from datetime import date
from json import dumps
from pathlib import Path
from re import fullmatch

__all__ = [
    "PluginName",
    "main",
]

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "template"


class PluginName(str):
    """Имя плагина и скилла в kebab-case, как требует Claude Code."""

    def __new__(cls, value: str) -> "PluginName":
        if fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", value) is None:
            raise ValueError(f"Имя плагина должно быть в kebab-case латиницей: {value!r}")
        return super().__new__(cls, value)


def manifest(name: PluginName, description: str, author: str, repository: str | None) -> str:
    """Собирает plugin.json без пустых необязательных полей."""
    fields: MutableMapping[str, object] = {
        "name": name,
        "version": "0.1.0",
        "description": description,
        "author": {"name": author},
        "license": "MIT",
    }
    if repository:
        fields["repository"] = repository
    return dumps(fields, ensure_ascii=False, indent=2) + "\n"


def write_new(path: Path, content: str) -> None:
    """Пишет файл, только если его ещё нет."""
    if path.exists():
        print(f"УЖЕ ЕСТЬ  {path}")
        return None
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    print(f"СОЗДАН  {path}")
    return None


def render(template: str, values: Mapping[str, str]) -> str:
    """Подставляет значения вместо {{KEY}} в шаблоне."""
    text = (TEMPLATE_DIR / template).read_text(encoding="utf-8")
    for key, value in values.items():
        text = text.replace(f"{{{{{key}}}}}", value)
    return text


def main() -> int:
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--dir", type=Path, required=True, help="папка плагина")
    parser.add_argument("--name", type=PluginName, required=True, help="имя плагина и скилла")
    parser.add_argument("--description", required=True, help="описание плагина для plugin.json")
    parser.add_argument("--author", required=True, help="автор для plugin.json и LICENSE")
    parser.add_argument("--repository", help="ссылка на репозиторий")
    args = parser.parse_args()
    root: Path = args.dir
    values = {
        "NAME": args.name,
        "AUTHOR": args.author,
        "YEAR": str(date.today().year),
    }
    write_new(
        path=root / ".claude-plugin" / "plugin.json",
        content=manifest(
            name=args.name,
            description=args.description,
            author=args.author,
            repository=args.repository,
        ),
    )
    write_new(root / ".gitignore", render("gitignore", values))
    write_new(root / "LICENSE", render("LICENSE", values))
    (root / "skills" / args.name).mkdir(parents=True, exist_ok=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
