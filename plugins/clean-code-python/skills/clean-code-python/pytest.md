# pytest

Файл нужен, только если тесты в проекте запускает pytest. Общие правила — что проверять, фейки и моки, изоляция — в `testing.md`, здесь их реализация в pytest. Главный принцип: тест — функция с голым `assert`, подготовка и очистка — в фикстурах, и всё это — только тем API, которое есть и не устарело в версии pytest проекта.

## 1. Версия pytest в проекте

- **Определить версию pytest до того, как писать тесты.** Порядок: закреплённая версия в lock-файле (`uv.lock`, `poetry.lock`, `requirements*.txt`) → ограничение в `pyproject.toml` (`pytest>=8.2`) → `minversion` в конфиге → `pytest --version` в окружении проекта. Так же определить версии плагинов (pytest-asyncio, pytest-mock, pytest-xdist).

```bash
grep -A1 '^name = "pytest"$' uv.lock
grep -A1 '^name = "pytest"$' poetry.lock
grep -iE '^pytest([<>=~! ]|$)' requirements*.txt
uv run pytest --version  # или poetry run / .venv/bin/pytest
```

- **Писать тесты под эту версию.** Не использовать возможности новее неё (таблица в разделе 13) и не использовать устаревшее, если в этой версии уже есть замена (таблица в разделе 14). Правила с пометкой «(pytest X.Y+)» применять только с этой версии, в более старой — указанную альтернативу.
- **Не обновлять pytest ради новой возможности без просьбы пользователя.** Если возможность сильно упростит тесты, предложить обновление одной строкой. Когда тесты опираются на возможность закреплённой версии, указать её в `minversion`: старый pytest тогда не запустится, а не упадёт непонятно.
- **Без lock-файла оценивать нижнюю границу по конфигу.** `[tool.pytest]` в `pyproject.toml`, `pytest.toml` или `strict = true` — 9.0+; `[tool.pytest.ini_options]` — 6.0+; `pythonpath` — 7.0+; `.pytest.ini` — 7.2+; `[tool:pytest]` в `setup.cfg` — старый проект.
- **Сверять с версией Python.** pytest 9.0 требует Python 3.10+, 8.4 — 3.9+, 8.0 — 3.8+. Python 3.14 поддерживается с pytest 8.4, 3.15 — с 9.1.
- **Обязательные плагины объявлять в `required_plugins` (pytest 6.0+).** `required_plugins = ["pytest-xdist>=2.0"]` — без плагина pytest падает с понятной ошибкой.
- **В conftest и плагинах, которые работают на нескольких версиях, ветвиться по `pytest.version_tuple` (pytest 7.0+).**

## 2. Структура и конфигурация проекта

- **Тесты держать в `tests/` отдельно от `src/`, а пакет ставить в окружение.** Editable-установка (`uv sync`, `pip install -e . --group dev`) — тесты импортируют пакет так же, как пользователь, без правки `sys.path`. Без установки — `pythonpath = ["src"]` (pytest 7.0+). pytest — в dev-группе зависимостей.
- **Хранить настройки pytest в одном файле.** pytest 9.0+: `[tool.pytest]` в `pyproject.toml` или `pytest.toml`, значения — нативные типы TOML. pytest 6.0–8.x: `[tool.pytest.ini_options]`, строковые опции — строками (не-строка устарела в pytest 9.2). Обе секции сразу нельзя; `setup.cfg` не использовать.

```toml
# pytest 9.0+
[tool.pytest]
minversion = "9.0"
testpaths = ["tests"]
addopts = ["-ra", "--import-mode=importlib"]
strict = true
filterwarnings = ["error"]
markers = ["slow: долгие тесты, в быстрый прогон не входят"]

# pytest 6.0–8.x
[tool.pytest.ini_options]
minversion = "8.0"
testpaths = ["tests"]
addopts = "-ra --strict-markers --strict-config --import-mode=importlib"
xfail_strict = true
filterwarnings = ["error"]
markers = ["slow: долгие тесты, в быстрый прогон не входят"]
```

- **`strict = true` (pytest 9.0+) включать только при закреплённой версии pytest.** Он включает `strict_config`, `strict_markers`, `strict_parametrization_ids`, `strict_xfail` и все будущие строгие проверки — обновление pytest без закрепления может уронить CI. Тогда включать строгие опции по одной; мешающую выключить отдельно: `strict_parametrization_ids = false`.
- **В новом проекте задавать `--import-mode=importlib` и src-layout, в существующем — следовать его режиму.** В режиме по умолчанию (`prepend`) тестовые файлы в разных каталогах должны иметь разные имена, иначе сбор падает с «import file mismatch». `__init__.py` в `tests/` это обходит, но делает импортируемым код из репозитория вместо установленного пакета. В `importlib` тестовые модули не импортируют друг друга: общие хелперы — в conftest или отдельном пакете.
- **Называть файлы `test_*.py`, функции `test_*`, классы `Test*` без `__init__`.** Класс с `__init__` не собирается, pytest лишь предупреждает. Правила поиска (`python_files` и т. п.) не менять. Не держать в тестовом модуле импортированных классов с именем `Test*` — их соберут; в pytest 8.4+ это выключает `collect_imported_tests = false`.
- **Тесты одной операции группировать в класс, когда им нужна общая фикстура или маркер.** `class TestUpdate` с `test_bad_id` и `test_bad_task`; класс запускается целиком: `tests/test_api.py::TestUpdate`.
- **Задавать `testpaths = ["tests"]`, а переопределяя `norecursedirs`, сохранять умолчания.** Окружение называть `.venv`: скрытые каталоги pytest и так не обходит.

## 3. Фикстуры

- **Всю подготовку выносить в фикстуры.** Исключение в фикстуре pytest показывает как ERROR, в теле теста — как FAIL. Тогда FAIL значит, что сломан тестируемый код, а не что не поднялась БД.
- **Очистку писать после `yield`.** Она выполнится, даже если тест упал; ошибка в ней даёт «ERROR at teardown». `request.addfinalizer` — только если откат нужно зарегистрировать сразу после действия посреди фикстуры; финализаторы идут в обратном порядке.

```python
@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    """Сессия БД с откатом после теста."""
    session = Session(engine)
    yield session
    session.rollback()
    session.close()
```

- **Одна фикстура — одно действие, меняющее состояние, и его откат.** Плохо: `setup()` создаёт админа, двух пользователей и письмо и возвращает кортеж — сбой посередине ничего не откатит. Хорошо: `user`, `mailbox`, `logged_in_client`, каждая со своим откатом, связаны зависимостями. Тест берёт верхнюю фикстуру и показывает только действие и проверку.
- **Когда тесту нужно несколько объектов, возвращать из фикстуры фабрику.**

```python
@pytest.fixture
def make_customer(repo: Repository) -> Iterator[Callable[[str], Customer]]:
    """Создаёт клиентов и удаляет их после теста."""
    created: MutableSequence[Customer] = []

    def make(name: str) -> Customer:
        customer = repo.add(Customer(name=name))
        created.append(customer)
        return customer

    yield make
    for customer in created:
        repo.delete(customer.id)
```

- **Scope задавать в определении фикстуры; зависеть только от фикстур того же или более широкого scope.** `function` (по умолчанию), `class`, `module`, `package`, `session`. Аргументы `@pytest.fixture` — только по имени: `@pytest.fixture(scope="module")`.
- **Дорогой ресурс держать в session-фикстуре, а изоляцию давать function-фикстурой поверх неё.** `db_engine` (session) подключается один раз, `db` (function) чистит таблицы перед каждым тестом. Если function-фикстуре оставить прежнее имя, тесты менять не придётся.
- **Фикстуры, которые только отдают данные, делать session-scope, а данные — неизменяемыми.** Значение фикстуры одно на тест: тест и другая фикстура, запросившие `order`, получают один объект и видят изменения друг друга.
- **Общие фикстуры класть в `tests/conftest.py`, фикстуры подкаталога — в его `conftest.py`, фикстуры одного файла — в сам файл.** `conftest.py` не импортировать. Фикстуры другого пакета подключать `pytest_plugins = ["mylib.fixtures"]` только в корневом conftest; в некорневом это ошибка (pytest 4.0+).
- **Предпочитать фикстуры, перечисленные в параметрах теста; `autouse=True` — только для того, от чего тесты не зависят.** Запрет сети, замер времени. Инициализация БД через autouse не даст проверить, что код без неё бросает понятное исключение.
- **Фикстуру без значения подключать `usefixtures` на классе или `pytestmark` модуля.** `pytestmark = pytest.mark.usefixtures("clean_dir")`. На саму фикстуру маркеры не действуют (pytest 9.0+: ошибка) — зависимость объявлять её параметром. `usefixtures` без аргументов даёт предупреждение (pytest 8.4+).
- **Не вызывать фикстуру как функцию (ошибка с pytest 4.0).** Если функция нужна и отдельно: `@pytest.fixture(name="cell")` над `def cell_fixture()`. Тот же `name=` снимает предупреждение линтера о переопределении внешнего имени.
- **Давать фикстурам docstring и тип результата.** `pytest --fixtures tests/test_x.py` выводит доступные тесту фикстуры с docstring и местом определения, `--setup-show` — порядок SETUP/TEARDOWN и scope. Yield-фикстура аннотируется `Iterator[X]`.
- **Встроенные фикстуры аннотировать публичными типами (pytest 6.2+).** `monkeypatch: pytest.MonkeyPatch`, `capsys: pytest.CaptureFixture[str]`, `caplog: pytest.LogCaptureFixture`, `tmp_path: Path`, `tmp_path_factory: pytest.TempPathFactory`, `request: pytest.FixtureRequest`, `recwarn: pytest.WarningsRecorder`.
- **Переопределять фикстуру одноимённой в подкаталоге или модуле.** Переопределяющая может запросить исходную: `def username(username: str) -> str: return f"admin-{username}"`.
- **Фикстуру scope `class` и шире внутри класса объявлять `@classmethod` (pytest 9.1+).** `@pytest.fixture(scope="class")` ставить над `@classmethod`. Метод экземпляра пишет атрибут в другой экземпляр, и тест получит `AttributeError`. В более старой версии такую фикстуру выносить из класса.
- **Данные из теста в фикстуру передавать маркером.** `request.node.get_closest_marker("fixt_data")` и `marker.args[0]`; отсутствие маркера обработать явно, маркер зарегистрировать.
- **Не использовать xunit-методы (`setup_module`, `setup_method`) и не смешивать их с фикстурами.** Их не видно в `--setup-show`, у них нет параметризации, а порядок при смешивании запутан. nose-методы `setup()`/`teardown()` удалены (pytest 8.0).
- **В teardown не запрашивать новую фикстуру через `request.getfixturevalue()` (устарело в pytest 9.1).** Объявить её в сигнатуре или запросить до `yield`.

## 4. Параметризация

- **Таблицу случаев оформлять `@pytest.mark.parametrize` и перечислять все имена в сигнатуре теста.** Каждый набор — отдельный тест со своим id, его можно перезапустить: `"tests/test_stock.py::test_stock_status[zero]"`.
- **Давать наборам читаемые id.** Без них отчёт показывает `[task0]`, `[task1]`. `pytest.param(..., id="zero")` или `ids=функция`; функция может вернуть `None`, тогда id сгенерируется. `ids`, `indirect`, `scope` передавать только по имени (позиционно — ошибка с pytest 9.2).

```python
@pytest.mark.parametrize(
    argnames="qty, expected",
    argvalues=[
        pytest.param(0, StockStatus.EMPTY, id="zero"),
        pytest.param(1, StockStatus.LOW, id="below-threshold"),
        pytest.param(10, StockStatus.OK, id="at-threshold"),
    ],
)
def test_stock_status(qty: int, expected: StockStatus) -> None:
    assert stock_status(qty) == expected
```

- **Маркер на отдельный набор вешать через `pytest.param(..., marks=...)`.** `pytest.param(6, 36, marks=pytest.mark.xfail(reason="bug #12"))`; так же — `skipif` на один набор.
- **В `argvalues` передавать коллекцию, а не генератор (генератор устарел в pytest 9.1).** Генератор истощается: при параметризации класса второй метод молча пропускается. `list(load_cases())`; `range` допустим.
- **Не мутировать параметры в тесте.** Значения передаются без копии: изменённый `list` увидят следующие наборы.
- **Декартово произведение получать стеком декораторов `parametrize`.** Параметризовать весь модуль — `pytestmark = pytest.mark.parametrize(...)`, класс — декоратор на классе.
- **Чтобы прогнать набор тестов на нескольких реализациях, параметризовать фикстуру.** Каждый тест, зависящий от неё даже косвенно, пройдёт на всех вариантах. Так проверяют, что фейк ведёт себя как настоящая реализация.

```python
@pytest.fixture(params=["fake", "sql"])
def repo(request: pytest.FixtureRequest) -> Repository:
    """Репозиторий каждой реализации."""
    match request.param:
        case "fake":
            return FakeRepository()
        case _:
            return SqlRepository(request.getfixturevalue("session"))
```

- **Следить за уникальностью id.** С `strict_parametrization_ids` (pytest 9.0+) дубликаты — ошибка, без неё pytest молча добавляет суффиксы. Длинные строки в id с pytest 9.2 заменяются на `argname+index`.
- **Набор, известный только при выполнении, проверять субтестами (pytest 9.0+, экспериментально).** `def test_docs(subtests: pytest.Subtests)` и в цикле `with subtests.test(path=str(path)): assert ...` — каждое падение видно отдельно. Для данных, известных при сборе, оставаться на `parametrize`.
- **Параметры из командной строки передавать хуком `pytest_generate_tests` и `metafunc.parametrize`.** Пустой список параметров даёт skip; `empty_parameter_set_mark = "fail_at_collect"` делает его ошибкой.

## 5. assert, исключения, approx

- **Проверять голым `assert` и сравнивать объекты целиком.** pytest показывает diff по полям dataclass, словарей и списков (dataclass и attrs — рекурсивно, если `__eq__` не переопределён). Полный diff — `-vv` или `verbosity_assertions = 2` (pytest 8.0+).
- **Хелперы с `assert` вне тестовых модулей и conftest регистрировать для переписывания.** `pytest.register_assert_rewrite("tests.helpers")` в корневом conftest до импорта, иначе при падении — голый `AssertionError`.
- **Для объектов предметной области понятный diff задавать хуком `pytest_assertrepr_compare` в conftest.**
- **Ожидаемое исключение проверять `with pytest.raises(E, match=...)`.** `match` — это `re.search`: спецсимволы экранировать `re.escape`, пустое сообщение — `match="^$"` (`match=""` в pytest 8.4+ даёт предупреждение). С pytest 8.0 `match` смотрит и в `__notes__`.

```python
def test_allocate_raises_out_of_stock_for_sku() -> None:
    batch = make_batch(sku=Sku("SMALL-FORK"), qty=10)
    line = make_line(sku=Sku("SMALL-FORK"), qty=20)

    with pytest.raises(OutOfStock, match=re.escape("SMALL-FORK (qty 20)")):
        allocate(line, [batch])
```

- **Атрибуты исключения читать из `excinfo.value` после блока.** Плохо: `"msg" in str(excinfo)` — с pytest 5.0 это `repr` → хорошо: `"msg" in str(excinfo.value)`. `raises(RuntimeError)` ловит и подклассы, точный тип — `assert excinfo.type is RuntimeError`. Условие на атрибуты — `pytest.raises(ApiError, check=lambda e: e.code == 3)` (pytest 8.4+).
- **`ExceptionGroup` проверять `pytest.RaisesGroup` (pytest 8.4+).** `with pytest.RaisesGroup(ValueError, TypeError):` строг к структуре; детали вложенного — `RaisesGroup(RaisesExc(ValueError, match="foo"))`; ослабить — `flatten_subgroups=True`, `allow_unwrapped=True`. В pytest 8.0–8.3 — `excinfo.group_contains(ValueError)`, но он не доказывает, что лишних исключений нет.
- **Не использовать callable-форму `pytest.raises(E, func, *args)` и параметр `message=` (удалён в pytest 5.0).** Своё сообщение при отсутствии исключения — `pytest.fail("...")` последней строкой в блоке `with`.
- **Float сравнивать `actual == pytest.approx(expected)`.** Работает со скалярами, списками, словарями и NaN; `set` и вложенные контейнеры — `TypeError`. `datetime` и `timedelta` — с явным `abs=timedelta(seconds=1)` (pytest 9.1+). Для `Decimal` допуск передавать `Decimal`.
- **Не возвращать значение из теста.** В pytest 8.4+ такой тест падает, раньше проходил с предупреждением. Заменить `return` на `assert`.

## 6. Предупреждения

- **В конфиге превращать предупреждения в ошибки, а известные чужие — игнорировать точечно.** `filterwarnings = ["error", 'ignore:function ham\(\) is deprecated:DeprecationWarning']`; regex в TOML — в одинарных кавычках. Побеждает последний совпавший фильтр; сообщение — regex от начала строки без учёта регистра.
- **Фильтр на отдельный тест ставить маркером `@pytest.mark.filterwarnings("ignore:api v1")`.** Маркер сильнее конфига и `-W`; из нескольких декораторов приоритетнее верхний.
- **Предупреждение проверять `with pytest.warns(UserWarning, match=...)`, устаревание — `pytest.deprecated_call()`.** `pytest.warns` возвращает список записей с `category` и `message`. В pytest 8.0+ несовпавшие предупреждения выпускаются заново и при `error` роняют тест; `deprecated_call` ловит и `FutureWarning`.
- **«Нет предупреждений» проверять `warnings.catch_warnings()` и `simplefilter("error")`.** `pytest.warns(None)` удалён в pytest 8.0. «Ровно эти» — фикстура `recwarn` и `len(recwarn)`.
- **Число предупреждений сокращать порогом `max_warnings` (pytest 9.1+).** При превышении код выхода 6.

## 7. monkeypatch, tmp_path, capsys, caplog

- **Чужой и неизменяемый код подменять через `monkeypatch`.** Он откатывает патч после теста. Где ставить патч — по правилам `testing.md`: `monkeypatch.setattr(app.files, "getcwd", fake_getcwd)`. Встроенные `open` и `compile` не патчить — это ломает сам pytest.
- **Подменять зависимость, а не переменную окружения, от которой она по-разному зависит на разных ОС.** Плохо: `monkeypatch.setenv("HOME", ...)` — на Windows `expanduser` смотрит `USERPROFILE`. Отсутствие переменной или ключа — `delenv("USER", raising=False)`, `delitem(config, "user", raising=False)`; дописать путь — `setenv("PATH", value, prepend=os.pathsep)`.
- **Патч на часть теста — `with monkeypatch.context() as m:`; вне фикстуры — `with pytest.MonkeyPatch.context() as mp:` (pytest 6.2+).** Экземпляр `pytest.MonkeyPatch()` сам не откатывается.
- **Повторяющуюся подмену выносить в фикстуру, запрет сети для быстрых тестов — в autouse-фикстуру их conftest.**

```python
# tests/unit/conftest.py
@pytest.fixture(autouse=True)
def no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Запрещает сетевые вызовы в unit-тестах."""
    monkeypatch.delattr("requests.sessions.Session.request")
```

- **Файлы создавать в `tmp_path` (`pathlib.Path`), а не в `tmpdir` (legacy на `py.path`).** Дорогие файлы — один раз через `tmp_path_factory.mktemp("data")` в session-фикстуре. `-p no:legacypath` в `addopts` запрещает `tmpdir`. CLI, зависящий от текущего каталога, — `monkeypatch.chdir(tmp_path)`. `--basetemp` очищается перед запуском: не указывать в нём каталог с данными.
- **Вывод проверять `captured = capsys.readouterr()` и `captured.out`/`captured.err`.** Метод отдаёт накопленное с прошлого вызова, вывод можно проверять порциями. Логи — `caplog.records` и `caplog.messages`. Вывод и в терминал, и в перехват — `capteesys` (pytest 8.4+).
- **Кэш pytest — только для инструментов вроде `--lf`; тесты от прошлых запусков не зависят.** `.pytest_cache` — в `.gitignore`.
- **Имена для doctest добавлять через `doctest_namespace` в autouse-фикстуре корневого conftest.** Запуск — `--doctest-modules`.

## 8. Моки

- **Мокать через `unittest.mock` или `monkeypatch`, а `mocker` из pytest-mock брать, если плагин уже есть в проекте.** Патч `mocker` откатывается сам, без `with` и декораторов. Спецификация обязательна: `mocker.patch.object(cli, "list_tasks", autospec=True, return_value=[])`, `mocker.create_autospec(Gateway, instance=True)`.
- **Повторяющуюся подмену выносить в фикстуру, которую тесты перечисляют в параметрах.**

```python
@pytest.fixture
def gateway() -> PaymentGateway:
    """Платёжный шлюз без сети, со спецификацией настоящего."""
    return create_autospec(PaymentGateway, instance=True)


def test_checkout_charges_order_total(gateway: PaymentGateway) -> None:
    checkout(order=make_order(total=Money(100)), gateway=gateway)

    assert gateway.charge.call_args_list == [call(Money(100))]
```

## 9. Маркеры, skip и xfail

- **Регистрировать каждый свой маркер и включать строгую проверку.** `markers = ["slow: ..."]`; строго — `--strict-markers` (pytest 4.5+) или `strict_markers`/`strict` (pytest 9.0+). Без этого опечатка `@pytest.mark.slwo` молча создаёт новый маркер. С pytest 9.2 проверяются и имена в `-m`. Плагин регистрирует маркер `config.addinivalue_line("markers", ...)` в `pytest_configure`.
- **Указывать причину у `skip`, `skipif`, `xfail`.** В `pytest.skip`, `pytest.fail`, `pytest.exit` — `reason=` (`msg=` удалён в pytest 8.0). Причины в отчёте — `-ra` или `-rsxX`.
- **Условие `skipif` писать выражением, а версии сравнивать кортежами или `packaging.version.Version`.** `skipif(sys.version_info < (3, 13), reason="нужен 3.13")`. Строки-условия — только для совместимости; сравнение версий строками неверно (`"0.10" < "0.2"`). Общие маркеры держать в одном модуле и импортировать.
- **Пропускать императивно `pytest.skip(reason=...)`, только если условие не вычислить при импорте.** Весь модуль — `pytestmark = pytest.mark.skipif(...)` или `pytest.skip(..., allow_module_level=True)`. Нет зависимости — `pytest.importorskip("docutils", minversion="0.3")`; с pytest 9.1 он ловит только `ModuleNotFoundError`, и сломанный установленный пакет роняет тест.
- **Включать строгий xfail.** `xfail_strict = true` (имя `strict_xfail` с pytest 9.0, старое тоже работает), точечно — `xfail(strict=True)`. Иначе XPASS не роняет набор, и починку никто не заметит.
- **Сужать `xfail` до ожидаемой ошибки через `raises=`.** Другое исключение тогда — обычное падение. `xfail` — для неисправленного бага, `pytest.raises` — для исключения, которое код бросает намеренно.
- **Выбирать срезы маркерами `-m "not slow"` и именем `-k "raises and not delete"`, проверяя выборку `--collect-only -q`.** По аргументам маркера — `-m "device(serial='123')"` (pytest 8.3+).

## 10. Async-тесты

- **Async-тесты запускать плагином, который уже есть в проекте (pytest-asyncio, anyio, pytest-trio), в его настроенном режиме.** Сам pytest корутины не выполняет: без плагина async-тест в pytest 8.4+ падает, а раньше пропускался с предупреждением — то есть ничего не проверял.
- **Синхронному тесту не давать async-фикстуру (ошибка с pytest 9.0).** Нужен async-плагин или синхронная фикстура, возвращающая корутину.
- **Объекты, привязанные к циклу событий, создавать в фикстуре того же scope, что и цикл.** Если цикл свой на каждый тест, `Lock`, клиент или пул из session-фикстуры упадут с «attached to a different loop».
- **Зависание ограничивать таймаутом.** pytest-timeout: `--timeout=30` на весь прогон или `@pytest.mark.timeout(5)` на тестах с внешними сервисами; внутри теста — `asyncio.timeout` (3.11+).

## 11. Плагины, хуки, покрытие

- **Прежде чем писать своё, искать готовый плагин.** pytest-xdist (`-n auto`, только если тесты не делят ресурс), pytest-repeat (`--count=50`, чтобы поймать нестабильный тест), pytest-timeout, pytest-cov. Линтеры через pytest (pytest-flake8 и т. п.) не подключать — линтер запускать отдельно.
- **Покрытие смотреть `pytest --cov=pkg --cov-branch --cov-report=term-missing`.** Непокрытые строки и ветки — список недостающих тестов или ненужного кода.
- **Свою опцию командной строки объявлять хуком `pytest_addoption` в корневом conftest, читать через `request.config.getoption(...)`.** `pytest.config` удалён (pytest 5.0): конфиг брать из аргумента хука, `request.config` или фикстуры `pytestconfig`.
- **Хуки помечать `@pytest.hookimpl(tryfirst=True)`, а не маркерами (`@pytest.mark.tryfirst` устарел в pytest 7.2).** В хуках брать `pathlib`-аргументы `collection_path`, `file_path`, `start_path` (`path` и `startdir` удалены в pytest 9.0). `pytest_ignore_collect` возвращает `None`, а не `False`.
- **Снимок состояния при падении (дамп, скриншот) делать хуком `pytest_runtest_makereport`.** Не через приватные атрибуты объектов теста.
- **Свой плагин начинать с хуков в conftest и выносить в пакет, когда он понадобится другим проектам.** Точка входа — `[project.entry-points.pytest11]` в `pyproject.toml`.
- **Плагины и хуки тестировать фикстурой `pytester` (pytest 6.2+; раньше `testdir`).** `pytester.makepyfile(...)`, `result = pytester.runpytest("-v")`, `result.assert_outcomes(passed=1, failed=1)`, `result.stdout.fnmatch_lines([...])`; отсутствие строки — `result.stdout.no_fnmatch_line(...)`.

## 12. Запуск, диагностика, переход с unittest

- **Во время работы запускать точечно, перед сдачей — весь набор.** `pytest tests/unit/test_models.py::TestUpdate::test_bad_id`; `--lf` — только упавшие, `-x` — до первого падения.
- **Разбирать падения по нарастающей.** Сначала `--lf --tb=no -q --maxfail=3` — что падает; затем `--lf -x -l` — traceback и локальные переменные одного теста. Падение, зависящее от порядка тестов, искать через `--setup-show`; медленные тесты и фикстуры — `--durations=10`.
- **unittest-тесты запускать pytest как есть и переводить постепенно.** Убрать `TestCase`, `self.assertEqual(a, b)` → `assert a == b`, `setUp` → фикстура, `assertRaises` → `pytest.raises`, `subTest` → `parametrize`, `@skip` → `pytest.mark.skip(reason=...)`. До конца перевода фикстуру к unittest-классу подключать `@pytest.mark.usefixtures(...)`, данные передавать через `request.cls`. Параметризованные фикстуры с unittest-классами не работают.

## 13. Что появилось в какой версии

| Возможность | pytest | Как использовать |
|---|---|---|
| `caplog`, `capsys.readouterr().out`, `warns(match=)`, `skip(allow_module_level=True)` | 3.3 | логи и вывод в тестах |
| `monkeypatch.context()`, `get_closest_marker` | 3.6 | патч внутри `with`, маркер в фикстуре |
| scope `package` | 3.7 | фикстура до конца пакета |
| `tmp_path`, `tmp_path_factory` | 3.9 | вместо `tmpdir` |
| `--strict-markers` | 4.5 | ошибка на незарегистрированный маркер |
| вызываемый `scope` | 5.2 | scope из опции командной строки |
| `[tool.pytest.ini_options]`, `--import-mode=importlib`, `required_plugins`, `--strict-config` | 6.0 | конфиг в `pyproject.toml` |
| `pytester`, `pytest.MonkeyPatch`, публичные типы фикстур | 6.2 | аннотации `pytest.CaptureFixture[str]` и др. |
| `pythonpath`, `pytest.version_tuple` | 7.0 | `pythonpath = ["src"]` |
| `.pytest.ini`, маски в `testpaths` | 7.2 | `testpaths = ["tests/*"]` |
| `excinfo.group_contains()`, `match` по `__notes__`, `verbosity_assertions` | 8.0 | группы исключений, полный diff |
| `-m "marker(kw=value)"` | 8.3 | выбор по аргументам маркера |
| `pytest.RaisesGroup`, `pytest.RaisesExc`, `raises(check=)`, `capteesys`, `collect_imported_tests`, `pytest.HIDDEN_PARAM` | 8.4 | строгая проверка `ExceptionGroup` |
| `[tool.pytest]`, `pytest.toml`, `strict`, `strict_parametrization_ids`, имя `strict_xfail`, субтесты | 9.0 | нативный TOML, строгий режим |
| `approx` для `datetime`/`timedelta`, `max_warnings`, class-фикстура как `@classmethod` | 9.1 | `approx(dt, abs=timedelta(seconds=1))` |
| `strict_markers` проверяет `-m`, `parametrize_long_str_id_strategy`, `pytest.ParameterSet`, `pytest.Approx` | 9.2 | опечатка в `-m` — ошибка |

## 14. Устарело и удалено → чем заменить

| Старое | Устарело | Удалено | Чем заменить |
|---|---|---|---|
| прямой вызов фикстуры | 3.7 | 4.0 | запросить параметром; `@pytest.fixture(name=...)` |
| маркер на значении `parametrize` | 3.x | 4.0 | `pytest.param(..., marks=...)` |
| `pytest_plugins` в некорневом conftest | 3.5 | 4.0 | корневой `conftest.py` |
| yield-тесты (`yield check, 2, 4`) | — | 4.0, 8.4 (ошибка сбора) | `parametrize` |
| `pytest.config` | 4.1 | 5.0 | `request.config`, аргумент хука |
| `raises(..., message=)`, `raises`/`warns` со строкой кода | 4.1 | 5.0 | форма `with`, `pytest.fail()` в конце блока |
| `"msg" in str(excinfo)` | — | 5.0 (смысл изменён) | `str(excinfo.value)` |
| позиционные аргументы `@pytest.fixture` | 5.2 | 6.0 | `@pytest.fixture(scope="module")` |
| `pytest.yield_fixture` | 6.2 | 10 (план) | `@pytest.fixture` |
| `--strict` | 6.2 | 9.0 (смысл изменён) | `--strict-markers` |
| `tmpdir`, `tmpdir_factory`, `testdir` | legacy с 6.2 | — | `tmp_path`, `tmp_path_factory`, `pytester` |
| `-k '-expr'` | 6.0 | 7.1 | `-k 'not expr'` |
| `assert pytest.approx(actual, expected)` | — | 7.0 | `actual == pytest.approx(expected)` |
| `pytest.warns(None)` | 7.0 | 8.0 | `catch_warnings()` + `simplefilter("error")` |
| `msg=` в `skip`/`fail`/`exit` | 7.0 | 8.0 | `reason=` |
| nose: `setup()`/`teardown()`, `@with_setup` | 7.2 | 8.0 | фикстура или `setup_method` |
| тест возвращает не `None` | 7.2 | 8.4 (тест падает) | `assert` |
| async-тест без плагина | 4.4 (skip) | 8.4 (падает) | pytest-asyncio, anyio |
| sync-тест с async-фикстурой | 8.4 | 9.0 | async-плагин или sync-фикстура, возвращающая корутину |
| маркер на фикстуре | 7.4 | 9.0 | зависимость параметром фикстуры |
| аргументы хуков `path`, `startdir` | 7.0 | 9.0 | `collection_path`, `file_path`, `start_path` |
| `@pytest.mark.tryfirst` на хуках | 7.2 | 10 (план) | `@pytest.hookimpl(tryfirst=True)` |
| `importorskip` ловит любой `ImportError` | 8.2 | 9.1 | только `ModuleNotFoundError`; старое — `exc_type=ImportError` |
| генератор в `argvalues` | 9.1 | — | `list(...)`, `tuple(...)`, `range` |
| class-фикстура как метод экземпляра | 9.1 | 10 (план) | `@classmethod` |
| module/package/session-фикстура как метод экземпляра | 9.2 | 10 (план) | `@classmethod` или `@staticmethod` |
| `request.getfixturevalue()` новой фикстуры в teardown | 9.1 | 10 | запросить до `yield` или в сигнатуре |
| не-строка в строковой опции `[tool.pytest.ini_options]` | 9.2 | 10 | строка или `[tool.pytest]` |
| позиционные `indirect`, `ids`, `scope` в `parametrize` | — | 9.2 | по имени |

## Чек-лист

1. Версия pytest и плагинов определена, а в тестах нет API новее неё и устаревшего, у которого в ней есть замена?
2. Подготовка и очистка — в yield-фикстурах, по одному действию на фикстуру, с минимальным нужным scope и неизменяемыми общими данными?
3. `autouse` только для того, от чего тесты не зависят, фикстуры не вызываются напрямую, `conftest.py` не импортируется?
4. У параметризации читаемые id, `argvalues` — коллекция, `ids`/`indirect` переданы по имени?
5. Исключения проверены `pytest.raises` с `match` и `re.escape`, float — `approx`, тест ничего не возвращает?
6. Предупреждения — ошибки, маркеры зарегистрированы и проверяются строго, у skip/xfail есть причина, xfail строгий?
7. `monkeypatch` и моки патчат имя по месту поиска, со спецификацией и только чужой код?
8. Файлы — в `tmp_path`, встроенные фикстуры аннотированы публичными типами?
9. Async-тесты идут через плагин проекта, а синхронные тесты не получают async-фикстур?
