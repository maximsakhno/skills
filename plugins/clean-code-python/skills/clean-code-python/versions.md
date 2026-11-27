# Версии Python: что когда появилось, устарело и удалено

Файл нужен, когда код надо сверить с версией Python проекта: пишешь под версию ниже последней, сомневаешься, с какой версии доступна возможность, или ревьюишь код на устаревший синтаксис. Главный принцип: писать возможностями нижней поддерживаемой версии проекта — не ниже (`Union[int, str]` в проекте на 3.10+ — устаревшая идиома), не выше (`class Box[T]` в проекте на 3.11 не запустится). В таблицах `\|` внутри кода означает `|`.

## 1. Определить версию проекта

- **Брать нижнюю границу `requires-python` из `pyproject.toml`.** `requires-python = ">=3.11"` значит писать под 3.11, даже если локальный интерпретатор или образ новее. Новые возможности под верхней границей использовать нельзя: код должен запускаться на минимальной версии.
- **Если `requires-python` нет, искать версию в других местах.** По порядку: `target-version` в `[tool.ruff]` (`"py311"`), `python_version` в `[tool.mypy]`, `pythonVersion` в `[tool.pyright]`, минимальная версия в матрице CI, `.python-version`, базовый образ в `Dockerfile` (`python:3.12-slim`). Приложение без матрицы и `requires-python` обычно пинит одну версию — её и брать.
- **При расхождении ориентироваться на минимум.** Если ruff или mypy настроены на версию выше `requires-python`, они пропустят несовместимый код; сказать об этом пользователю одной строкой, а писать под `requires-python`.
- **Возможность новее версии проекта не использовать, устаревшую для неё — заменять.** На ревью отмечать оба случая: `Optional[str]` в проекте 3.10+ и `type Alias = ...` в проекте 3.11. Таблицы ниже отвечают на «с какой версии» и «чем заменить».
- **Новые имена `typing` в младшей версии брать из `typing_extensions`.** Так пишут `Self`, `override`, `TypeIs`, `deprecated` до их появления в stdlib. Синтаксис (`match`, `type`, `class Box[T]`, `except*`, t-строки, `lazy import`) так не бэкпортировать: он работает только начиная со своей версии.
- **Перед повышением версии прогонять тесты с `-W error::DeprecationWarning` или `-X dev`.** Так всплывают API из раздела 4, которые в новой версии удалены или сменили поведение.

## 2. Самые частые замены

То, что агент пишет каждый день. Справа — версия, с которой «стало» доступно; в проекте ниже неё оставлять «было».

| Было | Стало | С версии |
|---|---|---|
| `Optional[str]`, `Union[int, str]`, `isinstance(x, (int, str))` | `str \| None`, `int \| str`, `isinstance(x, int \| str)` | 3.10 |
| `List[int]`, `Dict[str, int]`, `Tuple[int, ...]`, `Type[X]`, `typing.Iterable` | `list[int]`, `dict[str, int]`, `tuple[int, ...]`, `type[X]`, `collections.abc.Iterable` | 3.9 |
| `T = TypeVar("T")` + `class Box(Generic[T])` | `class Box[T]:`, `def first[T](xs: Sequence[T]) -> T`, `[T: Hashable]` | 3.12 |
| `Vector = list[float]`, `Vector: TypeAlias = list[float]` | `type Vector = list[float]`, `type Pair[T] = tuple[T, T]` | 3.12 (`TypeAlias` — 3.10) |
| `def copy(self: T) -> T` с `TypeVar(bound=...)` | `def copy(self) -> Self` | 3.11 |
| переопределение без пометки | `@override def save(self) -> None` | 3.12 |
| `Callable[..., T]` в декораторе | `def deco[**P, T](f: Callable[P, T]) -> Callable[P, T]` | 3.12 (`ParamSpec` — 3.10) |
| `**kwargs: Any` | `**kwargs: Unpack[Options]` (`Options` — `TypedDict`) | 3.12 |
| `TypeGuard[str]` | `TypeIs[str]` — сужает обе ветки `if` | 3.13 |
| `else: raise AssertionError`, `NoReturn` | `case _: assert_never(x)`, `Never` | 3.11 |
| `warnings.warn(..., DeprecationWarning)` в теле | `@deprecated("use g()")` из `warnings` | 3.13 |
| `def f(x: "Later")`, `from __future__ import annotations` | `def f(x: Later)` | 3.14 |
| цепочка `isinstance` + `len` | `match`/`case` | 3.10 |
| `n = len(a)` + `if n > 10` | `if (n := len(a)) > 10` | 3.8 |
| `{**a, **b}`, `c = a.copy(); c.update(b)` | `a \| b`, `a \|= b` | 3.9 |
| `s[len(p):] if s.startswith(p) else s`, `s.lstrip(p)` | `s.removeprefix(p)`, `s.removesuffix(p)` | 3.9 |
| `zip(xs, xs[1:])` | `pairwise(xs)` | 3.10 |
| `assert len(a) == len(b)` + `zip(a, b)` | `zip(a, b, strict=True)` | 3.10 |
| `[xs[i:i + n] for i in range(0, len(xs), n)]` | `batched(xs, n)`; проверка длины — `strict=True` (3.13) | 3.12 |
| `[x for xs in lists for x in xs]`, `chain.from_iterable` | `[*xs for xs in lists]`, `{**d for d in dicts}` | 3.15 |
| `with A() as a, \` + перенос | `with (A() as a, B() as b):` | 3.10 |
| ручные `__slots__`, длинный позиционный `__init__` | `@dataclass(frozen=True, slots=True, kw_only=True)` | 3.10 |
| `dataclasses.replace(obj, x=1)`, `nt._replace(x=1)` | `copy.replace(obj, x=1)` | 3.13 |
| `class Status(str, Enum)` | `class Status(StrEnum)` | 3.11 |
| `_MISSING = object()` | встроенный `sentinel` | 3.15 |
| `MappingProxyType(dict(...))` | `frozendict(x=1)` | 3.15 |
| импорт внутри функции ради старта | `lazy import json` в начале модуля | 3.15 |
| своя обёртка-исключение ради контекста | `e.add_note(f"row {i}"); raise` | 3.11 |
| список ошибок в атрибуте своего исключения | `raise ExceptionGroup("batch failed", errors)`, `except* ValueError` | 3.11 |
| `create_task` + `gather` | `async with TaskGroup() as tg: tg.create_task(...)` | 3.11 |
| `await wait_for(coro, 5)` | `async with timeout(5): await coro` | 3.11 |
| `loop.run_in_executor(None, partial(f, x))` | `await to_thread(f, x)` | 3.9 |
| `get_event_loop().run_until_complete(main())` | `asyncio.run(main())`; внутри корутины — `get_running_loop()` | 3.8 |
| sentinel `None` в очереди для остановки | `q.shutdown()` + `QueueShutDown`/`ShutDown` | 3.13 |
| `toml`, `tomli` | `with open(p, "rb") as f: cfg = tomllib.load(f)` | 3.11 |
| `pytz.timezone(...).localize(dt)` | `datetime(..., tzinfo=ZoneInfo("Europe/Moscow"))` | 3.9 |
| `datetime.utcnow()`, `timezone.utc` | `datetime.now(UTC)` | 3.11 |
| `old = os.getcwd(); os.chdir(p); try/finally` | `with chdir(p):` из `contextlib` | 3.11 |
| `pkg_resources.get_distribution("x").version`, `resource_filename` | `importlib.metadata.version("x")`, `importlib.resources.files("pkg") / "data.json"` | 3.8 / 3.9 |
| `os.walk(str(p))`; `shutil.copytree(src, dst)`, `shutil.move` | `p.walk()` (3.12); `src.copy(dst)`, `src.move(dst)` (3.14) | 3.12 / 3.14 |
| `uuid4()` как ключ, сортируемый по времени | `uuid7()` | 3.14 |

## 3. Возможности по версиям

Только то, что меняет прикладной код. Версия в заголовке — с какой возможность доступна.

### 3.8

| Возможность | Было → стало |
|---|---|
| `:=` | повторный вызов в условии или фильтре comprehension → `if (m := re.search(p, s)):`, `while (chunk := f.read(n)):` |
| Positional-only `/` | `def f(data, *, n)` → `def f(data, /, *, n)`: имя `data` можно менять, оно свободно для `**kwargs` |
| `f"{expr=}"` | `f"x={x!r}"` → `f"{x=}"` |
| `functools.cached_property`; `@lru_cache` без скобок | `@property` + ручной кеш в `self._x` → `@cached_property`; `@lru_cache()` → `@lru_cache` |
| `functools.singledispatchmethod` | `isinstance`-ветвление в методе → `@singledispatchmethod` + `@meth.register` |
| `Literal`, `Final`/`@final`, `Protocol`/`@runtime_checkable`, `TypedDict` | `mode: str` → `Literal["r", "w"]`; `MAX = 10` → `MAX: Final = 10`; ABC ради утиной типизации → `class Closer(Protocol)`; `dict[str, Any]` для записи → `class Movie(TypedDict)` |
| `asyncio.run()`; `create_task(coro, name=...)` | `run_until_complete` → `asyncio.run(main())`; безымянные задачи → `create_task(c, name="fetch")` |
| `importlib.metadata` | `pkg_resources.get_distribution("x").version` → `version("x")` |
| `math.prod`, `isqrt`; `shlex.join` | `reduce(mul, xs)` → `prod(xs)`; `int(sqrt(n))` → `isqrt(n)`; ручная склейка `shlex.quote` → `shlex.join(args)` |
| `copytree(dirs_exist_ok=True)`, `basicConfig(force=True)` | предварительное удаление каталога; ручная чистка хендлеров root |
| `unittest.mock.AsyncMock`, `IsolatedAsyncioTestCase` | самописные async-заглушки |
| `CancelledError` наследует `BaseException` | `except Exception` больше не ловит отмену задачи — так и должно быть |
| `SyntaxWarning` на `x is "abc"`, `x is 1` | `is` с литералом → `==` |

### 3.9

| Возможность | Было → стало |
|---|---|
| `dict` `\|`, `\|=` | `{**a, **b}` → `a \| b` |
| `str.removeprefix`, `removesuffix` | срез после `startswith` → `s.removeprefix(p)`; не `lstrip(p)` — тот срезает набор символов |
| Встроенные generics | `List[int]`, `Dict`, `Tuple`, `Type`, `typing.Iterable` → `list[int]`, `dict`, `tuple`, `type`, `collections.abc.Iterable` |
| Любое выражение в декораторе | `h = buttons[0].clicked.connect` + `@h` → `@buttons[0].clicked.connect` |
| `zoneinfo.ZoneInfo` | `pytz` → `ZoneInfo("Europe/Moscow")`; без системной базы зон — пакет `tzdata` |
| `asyncio.to_thread` | `loop.run_in_executor(None, partial(f, x, k=1))` → `await to_thread(f, x, k=1)` |
| `typing.Annotated` | метаданные в комментариях → `Annotated[int, Gt(0)]` |
| `importlib.resources.files()` | `pkg_resources.resource_filename` → `files("pkg") / "data.json"` |
| `graphlib.TopologicalSorter`; `math.lcm`, `gcd(*xs)` | самописная топосортировка; `reduce(gcd, xs)` → `gcd(*xs)` |
| `Executor.shutdown(cancel_futures=True)` | ручная отмена ожидающих future |
| `isocalendar()` — именованный кортеж | `d.isocalendar()[1]` → `d.isocalendar().week` |

### 3.10

| Возможность | Было → стало |
|---|---|
| `match`/`case` | цепочки `isinstance`/`len` → `case ["go", direction]:`, `case Point(x=0, y=y):`, `case {"id": id_, **rest}:`, guard `case P(x, y) if x == y`, альтернативы `\|`, `as`, `case _:` |
| `X \| Y` | `Union[int, str]`, `Optional[str]` → `int \| str`, `str \| None`; работает и в `isinstance` |
| Скобки в `with` | перенос через `\` → `with (A() as a, B() as b):` |
| `ParamSpec`, `Concatenate` | декоратор с `Callable[..., T]` теряет сигнатуру → `Callable[P, T]`, `*args: P.args, **kwargs: P.kwargs` |
| `TypeAlias`; `TypeGuard` | алиас неотличим от константы → `Cache: TypeAlias = ...`; `cast` после функции-проверки → `-> TypeGuard[list[str]]` |
| `zip(strict=True)`; `itertools.pairwise` | `assert len(a) == len(b)`; `zip(xs, xs[1:])` → `pairwise(xs)` |
| `dataclass(slots=True, kw_only=True)`, `KW_ONLY`, `field(kw_only=True)` | ручные `__slots__`, позиционный `__init__` на много полей |
| `aiter()`, `anext()`, `contextlib.aclosing`, async `nullcontext` | `await it.__anext__()` → `await anext(it)`; `try/finally: await agen.aclose()` → `async with aclosing(agen()) as g:` |
| `bisect.*(key=)` | параллельный список ключей |
| `inspect.get_annotations()` | `obj.__annotations__` → `get_annotations(obj)` (с 3.14 — `annotationlib`) |
| `EncodingWarning`, `encoding="locale"` | `open(path)` без кодировки → `open(path, encoding="utf-8")`; найти такие места — `-X warn_default_encoding` |
| `int.bit_count()`, `types.NoneType` | `bin(n).count("1")`; `type(None)` |
| `socket.timeout` — алиас `TimeoutError` | `except socket.timeout` → `except TimeoutError` |
| `Path.hardlink_to` | `Path.link_to` (обратный порядок аргументов) |
| Примитивы `asyncio` привязываются к циклу лениво | глобальный `Lock()` больше не падает с «attached to a different loop», но переиспользование между разными `asyncio.run` по-прежнему падает |

### 3.11

| Возможность | Было → стало |
|---|---|
| `ExceptionGroup`, `except*` | список ошибок в своём исключении → `raise ExceptionGroup("batch failed", errors)`; `except* ValueError as eg:` |
| `BaseException.add_note()` | перевыброс обёртки ради контекста → `e.add_note(f"row {i}"); raise` |
| `tomllib` | `toml`/`tomli` → `tomllib.load(f)` из файла, открытого `"rb"` (только чтение) |
| `typing.Self` | `TypeVar(bound=...)` в методах, `@classmethod`-конструкторах, `__enter__` → `-> Self` |
| `Required`/`NotRequired` | базовый `TypedDict` с `total=False` → `year: NotRequired[int]` |
| `LiteralString` | `sql: str` → `sql: LiteralString`: тайпчекер запретит f-строку с внешними данными |
| `Never`, `assert_never`, `reveal_type`, `assert_type` | `NoReturn`; `else: raise AssertionError` → `assert_never(x)` — исчерпываемость проверяет тайпчекер |
| `@dataclass_transform`; generic `TypedDict` и `NamedTuple` | плагины тайпчекера для ORM и моделей |
| `asyncio.TaskGroup` | `create_task` + `gather` → `async with TaskGroup() as tg:` |
| `asyncio.timeout()` | `wait_for(coro, 5)` → `async with timeout(5):`; `asyncio.TimeoutError` теперь то же, что `TimeoutError` |
| `asyncio.Runner`, `Barrier`; `asyncio.run` снимает главную задачу по Ctrl+C | несколько `run_until_complete` на одном цикле → `with Runner() as r: r.run(a()); r.run(b())` |
| Корутины в `asyncio.wait()` запрещены | `wait([coro])` → `wait([create_task(coro)])` |
| `contextlib.chdir()` | `os.chdir` + `try/finally` → `with chdir(p):` |
| `enum.StrEnum`, `verify`, `member`/`nonmember`, `enum.property` | `class Color(str, Enum)` → `class Color(StrEnum)` |
| `datetime.UTC`; `fromisoformat` разбирает почти любой ISO 8601 | `timezone.utc` → `UTC`; `strptime(s, "%Y-%m-%dT%H:%M:%S%z")` → `fromisoformat(s)`, в том числе с `Z` |
| `hashlib.file_digest` | чтение файла чанками → `file_digest(f, "sha256")` |
| `sys.exception()`; `logging.getLevelNamesMapping()` | `sys.exc_info()[1]`; `logging._nameToLevel` |
| `warnings.catch_warnings(action="ignore")` | `catch_warnings()` + `simplefilter("ignore")` |
| `singledispatch` по `int \| float` | отдельный `register` на каждый тип |
| `for x in *a, *b:` | `chain(a, b)` |

### 3.12

| Возможность | Было → стало |
|---|---|
| Параметры типов | `TypeVar` + `Generic[T]` → `class Box[T]:`, `def first[T](...)`; граница `[T: Hashable]`, ограничения `[T: (int, str)]`, `[**P]`, `[*Ts]`; вариантность выводится |
| Оператор `type` | `Vector: TypeAlias = list[float]` → `type Vector = list[float]`; вычисляется лениво, ссылки вперёд без кавычек |
| f-строки по общей грамматике | смена кавычек → `f"{", ".join(xs)}"`; `\n`, многострочные выражения и комментарии внутри `{}` |
| `@typing.override` | опечатка в имени переопределения проходит молча → `@override` |
| `**kwargs: Unpack[TD]` | `**kwargs: Any` → `**kwargs: Unpack[Options]` |
| `itertools.batched`; `math.sumprod` | нарезка по `range(0, len(xs), n)` → `batched(xs, n)` (кортежи, последний может быть короче); `sum(a * b for ...)` → `sumprod(x, y)` |
| `Path.walk()`, `relative_to(walk_up=True)`, наследование от `Path` | `os.walk(str(p))` → `p.walk()`; `os.path.relpath` → `relative_to(..., walk_up=True)` |
| `collections.abc.Buffer` | `ByteString`, `bytes \| bytearray \| memoryview` → `Buffer` |
| `shutil.rmtree(onexc=)` | `onerror=` с кортежем `(type, value, tb)` |
| `asyncio.run(loop_factory=)`, `eager_task_factory` | `set_event_loop_policy(...)`, `uvloop.install()` → `run(main(), loop_factory=uvloop.new_event_loop)`; `sleep(0)` ради немедленного старта задач |
| `sqlite3.connect(autocommit=...)` | управление транзакциями через `isolation_level` |
| `NamedTemporaryFile(delete_on_close=False)` | `delete=False` + ручное удаление |
| `"\d"` — `SyntaxWarning` | `re.compile("\d+")` → `re.compile(r"\d+")` |
| `extractall(filter=)` в `tarfile`, `shutil.unpack_archive` | `extractall(path)` → `extractall(path, filter="data")` — защита от выхода за каталог |
| В venv нет `setuptools` | `import pkg_resources` падает → `importlib.metadata`, `importlib.resources` |

### 3.13

| Возможность | Было → стало |
|---|---|
| Значения по умолчанию у параметров типов | `class Box[T = int]:`, `TypeVar("T", default=int)` |
| `@warnings.deprecated` | `warnings.warn(..., DeprecationWarning, stacklevel=2)` → `@deprecated("use g()")`: видят и тайпчекер, и runtime |
| `typing.TypeIs` | `TypeGuard` сужает только ветку `True` → `def is_str(x: object) -> TypeIs[str]` сужает обе |
| `typing.ReadOnly` | комментарий «не менять» → `id: ReadOnly[int]` в `TypedDict` |
| `copy.replace()` | `dataclasses.replace`, `nt._replace` → `copy.replace(obj, x=1)`; свой класс — `__replace__` |
| `batched(..., strict=True)` | ручная проверка длины последнего батча |
| `Queue.shutdown()` в `queue` и `asyncio` | sentinel `None` для остановки потребителей → `q.shutdown()` + `ShutDown`/`QueueShutDown` |
| `as_completed` — асинхронный итератор исходных задач | словарь future → запрос → `async for task in as_completed(tasks)` |
| `argparse.add_argument(deprecated=True)` | ручное предупреждение об устаревшей опции |
| `os.process_cpu_count()` | `os.cpu_count()` не учитывает affinity |
| `Path.from_uri()`, `PurePath.full_match("**/*.py")` | `urlparse` + `Path`; `fnmatch` по строке пути |
| `re.PatternError`; `str.replace(..., count=1)` | `re.error` (остался алиасом); позиционный `count` |
| `locals()` в функции — независимый снимок | `exec(code)` + чтение `locals()` → `ns = {}; exec(code, globals(), ns)` |

### 3.14

| Возможность | Было → стало |
|---|---|
| Отложенная оценка аннотаций | `"Later"` в кавычках, `from __future__ import annotations` → `def f(x: Later)`; читать — `annotationlib.get_annotations(obj, format=Format.FORWARDREF)` |
| t-строки | f-строка с внешними данными в SQL, HTML, shell → `t"... {user}"` даёт `Template`, обработчик видит интерполяции отдельно и экранирует |
| `except A, B:` без скобок | `except (A, B):` — только без `as` |
| `SyntaxWarning` на `return`/`break`/`continue` в `finally` | выход из `finally` глушит исключение — вынести из `finally` |
| `Path.copy`, `copy_into`, `move`, `move_into` | `shutil.copytree(src, dst)`, `shutil.move` → `src.copy(dst)`, `src.move(dst)` |
| `functools.Placeholder` | `lambda x: f(x, b)` → `partial(f, Placeholder, b)` |
| `io.Reader`, `io.Writer` | `IO`, `TextIO`, `BinaryIO` в параметрах → `Reader[bytes]` |
| `contextvars.Token` — контекстный менеджер | `tok = var.set(x)` + `finally: var.reset(tok)` → `with var.set(x):` |
| `uuid7()`, `uuid6`, `uuid8` | `uuid4()` как ключ, сортируемый по времени → `uuid7()` |
| `map(strict=True)`, `operator.is_none`/`is_not_none` | проверка длин; `lambda x: x is None` |
| `date.strptime`, `time.strptime` | `datetime.strptime(s, f).date()` → `date.strptime(s, f)` |
| `float.from_number` и аналоги | `float(x)` принимает и строки → `float.from_number(x)` |
| `heapq.heappush_max` и др. | `heappush(h, -x)` → `heappush_max(h, x)` |
| `compression.zstd`; `compression.gzip` и др. | сторонний `zstandard`; старые `import gzip` не устарели |
| `InterpreterPoolExecutor` | `ProcessPoolExecutor` для CPU-задач — экспериментально, см. раздел 5 |
| `Union[int, str]` и `int \| str` — один тип | сравнивать объединения `==`, не `is` |
| `NotImplemented` в `if` → `TypeError`; `int()` не зовёт `__trunc__` | вернуть и проверить явно; реализовать `__int__` или `__index__` |
| `forkserver` по умолчанию на Linux | если код полагается на `fork` — `get_context("fork")` явно |
| `get_event_loop()` без цикла → `RuntimeError` | `asyncio.run`, `get_running_loop()`, `Runner` |
| `partial` — дескриптор метода | `partial` в атрибуте класса → `staticmethod(partial(...))` |

### 3.15

| Возможность | Было → стало |
|---|---|
| `lazy import` | импорт внутри функции ради скорости старта → `lazy import json`, `lazy from pathlib import Path` в начале модуля; для кода под <3.15 — `__lazy_modules__ = ["json"]` |
| `frozendict` | `MappingProxyType(dict(...))`, `tuple(sorted(d.items()))` как ключ → `frozendict(x=1)`: хешируемый, не наследует `dict` |
| `sentinel` | `_MISSING = object()` (плохой `repr`, не пишется в аннотации) → встроенный `sentinel`: работает в `int \| MISSING`, переживает копирование и pickle |
| Распаковка в comprehension | `[x for xs in lists for x in xs]` → `[*xs for xs in lists]`; `{**d for d in dicts}` |
| UTF-8 по умолчанию | `open(p)` — UTF-8 на любой ОС; кодировка локали — `encoding="locale"` |
| `TypedDict(closed=True)`, `extra_items=` | `TypedDict` + `dict[str, Any]` для «известные ключи + произвольные» |
| `TypeForm` | `typ: Any` для выражения типа → `def cast[T](typ: TypeForm[T], v: object) -> T` |
| `TaskGroup.cancel()` | задача бросает своё исключение, чтобы закрыть группу → `tg.cancel()` |
| `re.prefixmatch()` | `re.match()` — только если код не должен работать на младших версиях |
| Пакет `profiling` | `profile` → `profiling.tracing`; `cProfile` остаётся алиасом |
| `threading.synchronized_iterator`, `serialize_iterator` | `Lock` вокруг `next()` общего генератора |
| `bytearray.take_bytes()` | `data = bytes(buf); buf.clear()` → `data = buf.take_bytes()` |
| `contextmanager`-декоратор держит контекст на всю итерацию или `await` | раньше контекст закрывался сразу при создании генератора или корутины |

## 4. Устарело и удалено

«Не назначено» — удаление не запланировано, но в новом коде старое не писать.

| Старое | Устарело в | Удалено в | Чем заменить |
|---|---|---|---|
| `typing.List/Dict/Set/Tuple/Type`, `typing.Callable/Iterable/Mapping/...` | 3.9 | не назначено | `list`, `dict`, `tuple`, `type`, `collections.abc.*` |
| `typing.Text` | 3.11 | не назначено | `str` |
| `typing.AnyStr` | 3.13 | 3.18 | `def f[S: (str, bytes)](x: S) -> S` |
| `typing.ByteString`, `collections.abc.ByteString` | 3.9 / 3.12 | 3.17 | `collections.abc.Buffer` или `bytes \| bytearray \| memoryview` |
| `typing.Hashable`, `typing.Sized` | 3.12 | не назначено | `collections.abc.Hashable`, `Sized` |
| `TypedDict("TD", x=int)` | 3.11 | 3.13 | `class TD(TypedDict)` или `TypedDict("TD", {"x": int})` |
| `NamedTuple("P", x=int)`; `TypedDict("TD")` без полей | 3.13 | 3.15 | классовый синтаксис; `TypedDict("TD", {})` |
| `isinstance` с наследником runtime-протокола без своего `@runtime_checkable` | 3.15 | 3.20 | пометить наследника `@runtime_checkable` |
| `from __future__ import annotations` | 3.14 | не раньше 2029 | отложенная оценка аннотаций 3.14 |
| `classmethod` поверх `property` | 3.11 | 3.13 | свой дескриптор `classproperty` |
| Алиасы ABC в `collections` (`collections.Mapping`) | 3.3 | 3.10 | `collections.abc.Mapping` |
| `@asyncio.coroutine`, корутины на `yield from` | 3.8 | 3.11 | `async def` / `await` |
| Параметр `loop=` в высокоуровневом `asyncio` | 3.8 | 3.10 | убрать; из другого потока — `run_coroutine_threadsafe` |
| Корутины в `asyncio.wait()` | 3.8 | 3.11 | передавать задачи `create_task(...)` |
| `with (await lock):` | — | 3.9 | `async with lock:` |
| `asyncio.get_event_loop()` без текущего цикла | 3.12 | 3.14 (`RuntimeError`) | `asyncio.run`, `get_running_loop`, `asyncio.Runner` |
| Политики `asyncio` (`set_event_loop_policy` и др.) | 3.14 | 3.16 | `asyncio.run(main(), loop_factory=...)`, `Runner(loop_factory=...)` |
| `asyncio.iscoroutinefunction` | 3.14 | 3.16 | `inspect.iscoroutinefunction` |
| `datetime.utcnow()`, `utcfromtimestamp()` | 3.12 | не назначено | `datetime.now(UTC)`, `datetime.fromtimestamp(ts, tz=UTC)` |
| `strptime` с `%d` без года в формате | 3.13 | 3.15 (`ValueError`) | добавить год в формат |
| `Thread.isAlive()`; `currentThread`, `activeCount`, `notifyAll`, `isSet`, `getName`, `setDaemon` | 3.8; 3.10 | 3.9; не назначено | `is_alive()`; `current_thread()`, `active_count()`, `notify_all()`, `is_set()`, `.name`, `.daemon` |
| `distutils` | 3.10 | 3.12 | `setuptools`, `packaging`, `shutil`, `sysconfig` |
| `pkg_resources` в новом venv | — | 3.12 (не ставится) | `importlib.metadata`, `importlib.resources`; иначе явная зависимость `setuptools` |
| `imp` | 3.4 | 3.12 | `importlib.import_module`, `importlib.reload`, `importlib.util.find_spec` |
| `asynchat`, `asyncore`, `smtpd` | 3.6 | 3.12 | `asyncio`, `aiosmtpd` |
| `cgi`, `crypt`, `imghdr`, `pipes`, `telnetlib`, `nntplib` и другие «мёртвые батарейки» (PEP 594) | 3.11 | 3.13 | `pipes.quote` → `shlex.quote`; остальное — сторонние пакеты |
| `lib2to3`; `parser` | 3.11; 3.9 | 3.13; 3.10 | LibCST, parso; `ast` |
| `ast.Num/Str/Bytes/NameConstant`, `.n`, `.s` | 3.8 | 3.14 | `ast.Constant`, `.value` |
| `assertEquals`, `assertNotEquals`, `assert_`, `assertRegexpMatches`, `assertRaisesRegexp` | 3.1–3.5 | 3.12 | `assertEqual`, `assertNotEqual`, `assertTrue`, `assertRegex`, `assertRaisesRegex` |
| `unittest.makeSuite`, `findTestCases` | 3.11 | 3.13 | методы `unittest.TestLoader` |
| `inspect.getargspec` | 3.0 | 3.11 | `inspect.signature()` |
| `ssl.wrap_socket`, `ssl.match_hostname` | 3.7 | 3.12 | `ssl.create_default_context().wrap_socket(sock, server_hostname=...)` |
| `ssl.PROTOCOL_TLS`, `SSLContext()` без протокола | 3.10 | не назначено | `PROTOCOL_TLS_CLIENT`/`SERVER`, `minimum_version` |
| `keyfile`/`certfile` в `smtplib`, `http.client` и др.; `urlopen(cafile=)` | 3.6 | 3.12; 3.13 | `context=ssl.create_default_context(...)` |
| `urllib.parse.splithost`, `splitport` и др. | — | не назначено | `urlparse`/`urlsplit` |
| `open(..., "U")`; `json.loads(encoding=)` | 3.3; 3.1 | 3.11; 3.9 | убрать флаг или параметр |
| `random.sample(set)`; `randrange(10.0)` | 3.9; 3.10 | 3.11; 3.12 | `sample(sorted(s), k)`; только `int` |
| `Path.link_to`; `Path` как контекстный менеджер | 3.10; 3.9 | 3.12; 3.13 | `hardlink_to`; — |
| `shutil.rmtree(onerror=)`; `sys.last_type/value/traceback` | 3.12 | не назначено | `onexc=`; `sys.last_exc` |
| `sqlite3`: именованные плейсхолдеры с последовательностью | 3.12 | 3.14 | `dict` параметров |
| `sqlite3.connect` с позиционными аргументами кроме пути | 3.13 | 3.15 | передавать по имени |
| `sqlite3`: адаптеры и конвертеры даты и времени по умолчанию | 3.12 | не назначено | свои адаптеры |
| `re.split/sub/subn` с позиционными `maxsplit`/`count`/`flags` | 3.13 | станут keyword-only | передавать по имени |
| `~True`, `~False` | 3.12 | 3.16 | `not x`; для целого — `~int(x)` |
| `NotImplemented` в булевом контексте; `int()` через `__trunc__` | 3.9; 3.11 | 3.14 (`TypeError`) | проверить явно; `__int__`/`__index__` |
| Невалидные escape `"\d"` | 3.12 (`SyntaxWarning`) | в будущем `SyntaxError` | raw-строки `r"\d"` |
| Литерал вплотную к ключевому слову (`0in x`) | 3.10 | в будущем `SyntaxError` | пробел: `0 in x` |
| `gen.throw(type, value, tb)` | 3.12 | не назначено | `gen.throw(exc)` |
| `codecs.open`; `os.popen`, `os.spawn*` (soft) | 3.14 | не назначено | `open`; `subprocess` |
| `argparse.FileType`; `logging.warn()` | 3.14; 3.3 | не назначено | открыть файл после разбора аргументов; `warning()` |
| `os.path.commonprefix` для путей | — | не назначено | `os.path.commonpath` |
| `profile` | 3.15 | 3.17 | `profiling.tracing` (`cProfile`) |
| `__version__` в модулях stdlib (`json`, `re`, `csv`, `logging` и др.) | 3.15 | 3.20 | `sys.version_info` |
| `hashlib.md5(string=...)` | 3.15 | 3.19 | данные позиционным аргументом |
| `partial` как атрибут класса-метода | 3.13 (`FutureWarning`) | 3.14 (поведение сменилось) | `staticmethod(partial(...))` |
| Неявный `fork` в `multiprocessing` на Linux | 3.12 | 3.14 (умолчание — `forkserver`) | `get_context("fork")` явно |
| `tarfile.extractall` без `filter` | 3.12 | 3.14 (умолчание — `"data"`) | `filter="data"` |

## 5. Ограничения и подводные камни

- **Проверять поддержку в тайпчекере проекта.** Возможность может быть в рантайме, но mypy или pyright той версии, что стоит в проекте, её ещё не понимает. Особенно это касается параметров типов и их умолчаний (3.12–3.13), `TypedDict(closed=True)`, `TypeForm`, `@disjoint_base` (3.15). Если тайпчекер не понимает конструкцию, оставить старую форму, а не глушить ошибку.
- **Понимать границы `from __future__ import annotations`.** На 3.7–3.9 он позволяет писать `int | None` и `list[int]`, но только в аннотациях: в `isinstance`, алиасах и базовых классах новый синтаксис всё равно упадёт. В проектах только 3.14+ импорт не добавлять: он устарел. Библиотеки, которые читают аннотации в рантайме, могут не понимать неквотированные ссылки вперёд на 3.14.
- **Читать аннотации функцией, а не через `__annotations__`.** `inspect.get_annotations` (3.10), с 3.14 — `annotationlib.get_annotations`. При отложенной оценке прямой доступ к словарю ломается.
- **Писать константы в `case` через точку.** `case Color.RED:` сравнивает с константой, а голое `case RED:` — захват в переменную, совпадает всегда. «Проваливания» между `case` нет; без `case _` несовпадение молча ничего не делает. Последовательные шаблоны не совпадают со строками, в mapping-шаблоне лишние ключи игнорируются.
- **Ловить ошибки `TaskGroup` через `except*`.** При ошибке одной задачи группа отменяет остальные и бросает `ExceptionGroup`. `gather`, `wait` и `wait_for` не устарели: `gather(return_exceptions=True)` остаётся для частичного успеха, `wait` — для частичного результата к сроку.
- **Указывать `encoding` при открытии текстовых файлов, пока проект поддерживает версии до 3.15.** UTF-8 по умолчанию — только с 3.15; до неё `open(p)` берёт кодировку локали и ведёт себя по-разному на разных ОС.
- **Не использовать `re.prefixmatch`, если поддерживаются версии ниже 3.15.** Код для нескольких версий оставляет `re.match`: он не удаляется.
- **Проверять сериализацию enum при переходе на 3.11.** `format()` и f-строки для члена теперь дают то же, что `str()`: у `StrEnum` и `IntEnum` это значение, у обычного `Enum` — `Class.MEMBER`.
- **Не полагаться на потокобезопасность `cached_property` и `contextlib.chdir`.** С 3.12 `cached_property` не блокирует, и при гонке потоков геттер может выполниться дважды. `chdir` меняет каталог всего процесса.
- **Ставить `lazy import` только на уровне модуля.** Внутри функции, класса или `try` это `SyntaxError`, `lazy from x import *` тоже нельзя. Ошибка импорта всплывёт при первом обращении к имени, а не при старте.
- **Не полагаться на экспериментальное по умолчанию.** Free-threaded сборка, JIT и `concurrent.interpreters` зависят от совместимости C-расширений.
- **Не считать устаревшим то, что вернули.** `importlib.resources.read_text`/`open_text` снова не устаревшие с 3.13, `optparse` — с 3.13 (для приложений по-прежнему `argparse`), `locale.getdefaultlocale` — с 3.15.
