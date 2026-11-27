# asyncio: корутины, задачи и конкурентный I/O

Этот файл нужен, когда код использует `async`/`await`, запускает задачи или конкурентно ждёт сеть, БД и подпроцессы. Главный принцип: цикл событий один и переключает задачи только на `await`. Поэтому его нельзя блокировать, а каждую задачу нужно ограничить по времени, дождаться и обработать её ошибки.

## 1. Когда asyncio, когда потоки и процессы

- **Выбирать модель по нагрузке.** Много одновременных сетевых операций — корутины. Блокирующий I/O через синхронную библиотеку — потоки. Вычисления — процессы: из-за GIL потоки на CPU-задачах не быстрее последовательного кода. Free-threaded сборка (3.14+) и `concurrent.interpreters` (3.14+) включаются не по умолчанию и зависят от C-расширений — на них не рассчитывать.
- **В async-коде брать асинхронную библиотеку.** `httpx.AsyncClient` или `aiohttp`, `asyncpg` — а не `requests` и `psycopg2` внутри корутин: синхронные вызовы там идут по очереди, как без asyncio.
- **В начале проекта решить, куда уходит CPU-работа.** «I/O-bound система» — миф: разбор заголовков, JSON, конвертация форматов понемногу тормозят цикл везде. Выбрать сразу: пул процессов или внешняя очередь задач (Celery, RQ).
- **Переводить код на asyncio постепенно.** Сверху вниз: `async def` у точки входа, блокирующее — в поток, дальше вниз по стеку. Снизу вверх: async-версия листовой функции и временная синхронная обёртка.

## 2. Точка входа и цикл событий

- **Запускать программу одним `asyncio.run(main())`.** Главная корутина создаёт всё остальное, а `run` снимает оставшиеся задачи и закрывает цикл. Несколько запусков на одном цикле или смесь с синхронным кодом — `asyncio.Runner` (3.11+).
  ```python
  # плохо
  loop = asyncio.get_event_loop()
  loop.run_until_complete(main())

  # хорошо
  from asyncio import Runner, run

  run(main())

  with Runner() as runner:
      runner.run(migrate())
      runner.run(serve())
  ```
- **Внутри корутины получать цикл через `get_running_loop()`.** `get_event_loop()` без текущего цикла с 3.12 предупреждает, а с 3.14 бросает `RuntimeError`. Сам цикл нужен редко: ради `run_in_executor`, `add_signal_handler`, `call_later`. Свой цикл (uvloop) — через `run(main(), loop_factory=...)` (3.12+), а не политики, устаревшие в 3.14.
- **Когда непонятно, что тормозит, включать отладочный режим.** `run(main(), debug=True)`, `python -X dev` или `PYTHONASYNCIODEBUG=1`: asyncio логирует шаги дольше 100 мс и корутины, которые так и не дождались. Задачи живого процесса показывает `python -m asyncio pstree PID` (3.14+).
- **Сигналы обрабатывать через `loop.add_signal_handler`, а не `signal.signal`.** Он безопасен для цикла, но работает только на Unix. Обработчик — обычная функция, `await` в нём нельзя. Ctrl+C с 3.11 `run` сам превращает в отмену главной задачи.
- **Цикл рядом с синхронным приложением (GUI) запускать в потоке-демоне через `loop.run_forever()`.** Корутины передавать туда через `run_coroutine_threadsafe(coro, loop)` — он возвращает потокобезопасный `concurrent.futures.Future`. Обычные вызовы, включая отмену, — через `loop.call_soon_threadsafe`. Остальные объекты asyncio не потокобезопасны.

## 3. Корутины и задачи

- **Помнить, что вызов `async def` ничего не выполняет.** Он возвращает объект корутины, а код запускается через `await`, задачу или `run`. `async def` без единого `await` — признак ошибки: внутри блокирующий вызов, или функции незачем быть корутиной.
- **Конкурентность создавать задачами, а не `await` подряд.** `await coro()` выполняется последовательно, как обычный вызов. Задача стартует на ближайшем `await` текущей корутины. Зависимые шаги ждать по очереди, независимые запускать вместе.
  ```python
  # плохо: каждая задача дожидается до создания следующей, 3 × 3 с = 9 с
  pages = [await create_task(fetch(url)) for url in urls]

  # хорошо: всё стартует сразу, итого 3 с
  async with TaskGroup() as tg:
      tasks = [tg.create_task(fetch(url)) for url in urls]
  pages = [task.result() for task in tasks]
  ```
- **Хранить ссылку на каждую задачу.** Цикл держит задачи слабыми ссылками: задачу, созданную без сохранения, сборщик мусора может собрать посреди работы. Фоновые задачи — в `TaskGroup` на время жизни сервиса или во множестве, из которого задача удаляет себя сама. Имя задачи (`name=`) видно в отладке и логах.
  ```python
  background: MutableSet[Task[None]] = set()

  task = create_task(handle_client(reader, writer), name="client")
  background.add(task)
  task.add_done_callback(background.discard)
  ```
- **Последовательные шаги писать двумя `await`, а не колбэками.** `add_done_callback` в прикладной логике — устаревший приём. Исключение — служебные действия вроде снятия задачи с учёта.
- **Чтобы задачи начинали работу сразу при создании, ставить `eager_task_factory` (3.12+), а не `await sleep(0)`.** `loop.set_task_factory(eager_task_factory)`: задача выполняется синхронно до первого `await`.
- **Декоратор корутины делать корутиной.** Синхронная обёртка вокруг `async def` замерит лишь создание корутины и вернёт не то. Вид функции определять через `inspect.iscoroutinefunction` (`asyncio.iscoroutinefunction` устарел в 3.14) и возвращать `async def wrapper` — либо завести два декоратора.
- **Состояние на задачу (id запроса, адрес клиента) хранить в `ContextVar`, а не в `threading.local`.** Поток один, и `threading.local` общий для всех задач. `ContextVar` копируется в задачи, созданные из текущей, и не виден снаружи. С 3.14 `with request_id.set(rid):` сам вернёт прежнее значение.

## 4. Конкурентный запуск

- **Группу задач по умолчанию запускать в `TaskGroup` (3.11+).** На выходе из блока все задачи завершены или сняты. При первой ошибке группа снимает остальные задачи и поднимает все ошибки разом как `ExceptionGroup`. Досрочно закрыть группу без ошибки — `tg.cancel()` (3.15+). Ниже 3.11 — `gather`, а при ошибке снимать оставшиеся задачи вручную.
- **`gather(..., return_exceptions=True)` брать, когда нужен частичный результат.** Падение одной задачи не снимает другие. Исключения приходят в списке на месте результата, порядок — как у аргументов. `gather` без этого флага не брать: при ошибке остальные задачи продолжают работать, а видна только первая ошибка.
  ```python
  results = await gather(*(fetch(url) for url in urls), return_exceptions=True)
  for url, result in zip(urls, results, strict=True):
      if isinstance(result, Exception):
          logger.warning("fetch failed", extra={"url": url, "error": repr(result)})
  ```
- **Результаты по мере готовности обрабатывать через `as_completed`.** Иначе медленный запрос задерживает обработку быстрых. С 3.13 `async for task in as_completed(tasks)` отдаёт исходные задачи. Раньше он отдавал новые объекты, и чей это результат, не узнать. `timeout=` бросает `TimeoutError`, но оставшиеся задачи не снимает.
- **Гонку «кто первый» и частичный результат к сроку делать через `wait`.** `done, pending = await wait(tasks, timeout=2, return_when=FIRST_COMPLETED)`. `wait` не бросает исключений и не снимает задачи: `pending` снимать вручную, ошибки брать через `task.exception()` у задач из `done`. Передавать только задачи: корутины с 3.11 дают `TypeError`. Так же ждать две бесконечные задачи (чтение сети и ввод) и снимать оставшуюся.
- **Связывать задачу с входными данными словарём.** `tasks = {tg.create_task(fetch(pid)): pid for pid in product_ids}`: при разборе ошибок видно, какой запрос упал.

## 5. Таймауты и отмена

- **Ставить срок на каждое сетевое ожидание.** В 3.11+ — `async with timeout(...)` вокруг блока. Ниже — `wait_for(aw, 5)`: он не устарел и годится для одного awaitable. С 3.11 `asyncio.TimeoutError` — это встроенный `TimeoutError`, ловить его.
  ```python
  # до 3.11
  report = await wait_for(fetch_report(), 5)

  # 3.11+: один срок на весь блок
  async with timeout(5):
      report = await fetch_report()
      await save(report)
  ```
- **Уменьшать таймауты HTTP-клиента.** У aiohttp по умолчанию 5 минут. `ClientTimeout(total=1, connect=0.1)` задать на сессию и переопределять на отдельном запросе.
- **Помнить, что отмена срабатывает только на `await`.** `task.cancel()` бросает `CancelledError` в точке, где задача ждёт. CPU-код без `await` продолжит работать. `finally` выполнится — в нём освобождать ресурсы. После `cancel()` задачу дожидаться.
- **Не глотать `CancelledError`.** С 3.8 это `BaseException`, и `except Exception` её не ловит — так и оставить. Если перехватили ради очистки — пробросить дальше.
  ```python
  # плохо: задача не снимается, TaskGroup и timeout ломаются
  try:
      await sync_inventory()
  except BaseException:
      logger.exception("sync failed")

  # хорошо
  try:
      await sync_inventory()
  except Exception:
      logger.exception("sync failed")
  finally:
      await connection.close()
  ```
- **Работу, которую нельзя бросать по таймауту, защищать `shield`.** По сроку сообщить пользователю, но не прерывать задачу.
  ```python
  task = create_task(build_report())
  try:
      async with timeout(5):
          await shield(task)
  except TimeoutError:
      await notify("report is almost ready")
      await task
  ```
- **Таймаут на подпроцесс процесс не останавливает.** В `except TimeoutError` вызвать `process.terminate()` или `kill()` — они только шлют сигнал. Затем `await process.wait()`, при необходимости тоже со сроком.
- **Повторы делать фабрикой корутины, со сроком на каждую попытку.** Корутину нельзя ждать дважды, поэтому передавать `partial(client.get, url)`. Повторять только сетевые и временные ошибки, с растущей паузой и случайным разбросом (tenacity, backoff). После исчерпания попыток — своё исключение. Перед постоянно медленной зависимостью — circuit breaker из готовой библиотеки: после серии ошибок запросы сразу отклоняются, а не ждут таймаут.
- **Останавливать сервис в три шага.** Перестать принимать новую работу, дождаться текущих задач с общим сроком, снять оставшиеся. Очередь дренировать с ограничением: `async with timeout(10): await queue.join()`, а в `finally` снять воркеров.

## 6. Ошибки в задачах и группах

- **Каждую задачу дожидаться или обрабатывать её ошибки внутри неё.** Иначе исключение превратится в «Task exception was never retrieved», да и то лишь когда задачу соберёт сборщик мусора. Если ссылка на задачу лежит в списке, ошибку не увидят до остановки.
- **Ошибки `TaskGroup` разбирать через `except*`.** Группа поднимает `ExceptionGroup` даже при одной ошибке, обычный `except ValueError` её не поймает. Каждый `except*` получает подгруппу своих исключений.
  ```python
  try:
      async with TaskGroup() as tg:
          for order in orders:
              tg.create_task(ship(order))
  except* TimeoutError as group:
      logger.warning("carrier timed out", extra={"failed": len(group.exceptions)})
  except* CarrierRejected as group:
      await requeue([error.order for error in group.exceptions])
  ```
- **Долгоживущий обработчик (клиент сервера, воркер очереди) защищать изнутри.** `except Exception` с `logger.exception(...)`, в `finally` — закрыть соединение. Одна упавшая задача не должна ронять сервис или вешать очередь.
- **Ошибку завершившейся задачи логировать через `exc_info`.** `logger.error("fetch failed", exc_info=task.exception(), extra={"product_id": tasks[task]})`. `result()` и `exception()` вызывать только у завершённых задач.
- **В ответе различать таймаут и сбой зависимости.** Обязательный сервис не ответил вовремя — `HTTPStatus.GATEWAY_TIMEOUT`, упал — `HTTPStatus.INTERNAL_SERVER_ERROR`. В обоих случаях снять остальные запросы. Необязательные данные при сбое заменить на `None` и снять их задачи. Так клиент решит, повторять ли запрос.

## 7. Блокирующий и CPU-код внутри async

- **Не вызывать в корутине ничего блокирующего.** `time.sleep`, файловый I/O, `requests`, синхронный драйвер БД, `input()` замораживают все задачи. Блокирующий вызов — `await to_thread(f, *args)` (3.9+), а не `run_in_executor(None, partial(f, x))`. Дробить CPU-цикл через `await sleep(0)` — заплатка: такую работу — в поток или процесс.
  ```python
  # плохо
  async def save_flag(path: Path, image: bytes) -> None:
      path.write_bytes(image)

  # хорошо
  async def save_flag(path: Path, image: bytes) -> None:
      await to_thread(path.write_bytes, image)
  ```
- **Помнить, что работу в потоке нельзя отменить.** Таймаут снимет ожидание, но поток доработает, и долгий поток не даст `run` завершиться.
- **Не раздувать пул потоков.** По умолчанию в нём `min(32, ядра + 4)` потоков. Начинать с «ядра + немного» и увеличивать по замеру до плато.
- **CPU-работу отдавать `ProcessPoolExecutor` через `loop.run_in_executor`.** Пул создать один раз и в `with`, иначе процессы утекут, а запуск — под `if __name__ == "__main__"`. Аргументы и результаты должны сериализоваться pickle: `asyncpg.Record` перед возвратом превращать в `dict`. `run_in_executor` возвращает future, их собирают `gather` и `as_completed`.
  ```python
  async def count_words(lines: Sequence[str], pool: ProcessPoolExecutor) -> Sequence[WordCounts]:
      loop = get_running_loop()
      futures = [
          loop.run_in_executor(pool, count_chunk, chunk)
          for chunk in batched(lines, 60_000)
      ]
      return await gather(*futures)
  ```
- **Размер порции для процессов подбирать замером.** Мелкие порции съедает сериализация, крупные оставляют ядра без дела. Параллелить только то, где вычисление дороже передачи данных.
- **При смешанной нагрузке запускать свой цикл в каждом процессе.** Разбор ответов тоже тратит CPU, и один цикл становится узким местом: `run_in_executor(pool, run_in_new_loop, part)`, внутри — `asyncio.run(...)`.
- **Потоки для CPU брать, только если библиотека отпускает GIL.** Это `hashlib` на больших данных, `scrypt`, части NumPy. Выигрыш проверять замером.

## 8. Ограничение конкурентности и синхронизация

- **Ограничивать одновременные обращения к внешнему API семафором с лимитом из договора.** `Semaphore(10)` при тарифе на 10 одновременных запросов — вместо того чтобы получать 429 и повторять. Держать семафор только вокруг самого запроса. Для HTTP есть альтернатива — лимит пула соединений (`TCPConnector(limit=...)`). Подпроцессы — `Semaphore(os.cpu_count())`.
  ```python
  async def fetch(client: AsyncClient, semaphore: Semaphore, url: str) -> bytes:
      async with semaphore:
          response = await client.get(url)
      response.raise_for_status()
      return response.content
  ```
- **Не ждать от семафора ограничения частоты.** Он ограничивает число одновременных операций и не сглаживает всплески. Лимит «N запросов в секунду» требует token bucket или leaky bucket.
- **При ручных `acquire`/`release` брать `BoundedSemaphore` и `try/finally`.** Лишний `release` у обычного семафора молча поднимает лимит, у `BoundedSemaphore` — даёт `ValueError`. По возможности — `async with`.
- **Искать гонки там, где состояние читают до `await`, а пишут после.** Между двумя `await` код атомарен: `counter += 1` в ста задачах даст 100, а `current = counter; await sleep(0); counter = current + 1` — 1. Типичный случай: рассылка по словарю сокетов, пока другая задача закрывает сокет отключившегося клиента и удаляет его.
- **Сначала убрать изменение общего состояния через `await`, потом брать `Lock`.** Неизменяемые данные, работа со снимком: `for socket in tuple(clients.values()):`. Если без замка не обойтись — `async with lock:` вокруг и чтения, и записи.
- **Создавать `Lock`, `Semaphore`, `Queue` внутри работающего цикла.** Объект, переиспользованный между разными `run` (например, глобальный в тестах), падает с «attached to a different loop». Создавать в `main` или фабрике и передавать параметром.
- **`Event` брать для разового сигнала «готово», а не для потока событий.** После `set()` все ожидающие просыпаются, и новые `wait()` проходят сразу. Несколько срабатываний подряд занятый потребитель увидит как одно. Если важна каждая единица работы — очередь. `Condition` нужен редко: дождаться состояния ресурса и сразу получить к нему исключительный доступ.

## 9. Очереди и producer/consumer

- **Producer/consumer строить на `asyncio.Queue` с фиксированным числом воркеров.** Число воркеров — предел конкурентности. `task_done()` — в `finally`, исключения ловить внутри воркера: иначе `join()` не завершится. Остановка в 3.13+ — `queue.shutdown()`: воркеры доберут остаток и получат `QueueShutDown`. Ниже 3.13 — `await queue.join()`, затем снять воркеров.
  ```python
  async def worker(queue: Queue[Order]) -> None:
      while True:
          try:
              order = await queue.get()
          except QueueShutDown:
              return None
          try:
              await process(order)
          except Exception:
              logger.exception("order processing failed", extra={"order_id": order.id})
          finally:
              queue.task_done()


  async def main() -> None:
      queue: Queue[Order] = Queue(maxsize=100)
      async with TaskGroup() as tg:
          for _ in range(10):
              tg.create_task(worker(queue))
          async for order in incoming_orders():
              await queue.put(order)
          queue.shutdown()
  ```
- **Ограничивать очередь через `maxsize`.** Это защищает память и даёт обратное давление: `await put()` ждёт свободного места. Чтобы HTTP-обработчик быстро отказывал, использовать `put_nowait` и при `QueueFull` отвечать `HTTPStatus.SERVICE_UNAVAILABLE`. Не крутить `get_nowait` с перехватом `QueueEmpty` — это холостой цикл на 100 % CPU.
- **Не держать в `asyncio.Queue` то, что нельзя потерять.** Очередь живёт в памяти процесса: при падении или перезапуске работа пропадёт. Важное — в БД или во внешний брокер.
- **В `PriorityQueue` класть dataclass с приоритетом и счётчиком порядка.** Куча неустойчива: элементы с равным приоритетом выходят в произвольном порядке, а сравнение данных может упасть.
  ```python
  @dataclass(order=True, frozen=True, slots=True)
  class WorkItem:
      priority: int
      sequence: int
      job: Job = field(compare=False)


  counter = count()
  await queue.put(WorkItem(priority=1, sequence=next(counter), job=job))
  ```

## 10. Асинхронные генераторы, итераторы и контекстные менеджеры

- **Захват и освобождение асинхронного ресурса оформлять через `async with`.** Подключение, пул, транзакция, сессия, захват подключения из пула. Свой менеджер без состояния — `@asynccontextmanager`, с состоянием — класс с `__aenter__`/`__aexit__`.
- **Асинхронный итератор писать асинхронным генератором и аннотировать `AsyncIterator[T]`.** Не класс с `__aiter__`/`__anext__`. Генератор отдаёт элементы последовательно, не конкурентно. Вместо `await it.__anext__()` — встроенные `aiter`/`anext` (3.10+). Async-версий `itertools` в stdlib нет, операции над потоком даёт библиотека aiostream.
- **Большие выборки читать курсором через `async for`, а не `fetch` целиком.** Цена — больше обращений к серверу; альтернатива — `LIMIT` с повторными запросами.
  ```python
  async def stream_orders(conn: Connection) -> AsyncIterator[Order]:
      async with conn.transaction():
          async for row in conn.cursor("SELECT id, total FROM orders"):
              yield Order(id=row["id"], total=row["total"])
  ```
- **Генератор, который держит ресурс, закрывать явно через `aclosing` (3.10+).** `async with aclosing(stream_orders(conn)) as orders:` вместо `try/finally: await agen.aclose()`. Иначе после `break` генератор закроется когда-нибудь потом, при сборке мусора.
- **После `writer.write()` вызывать `await writer.drain()`.** `write` — обычная функция и только кладёт данные в буфер: при медленной сети он растёт до исчерпания памяти. Закрывать так: `writer.close()`, затем в `finally` — `await writer.wait_closed()`, иначе ошибки закрытия не видны.
- **Сетевые клиенты и серверы писать на потоках данных.** Клиент — `open_connection`, сервер — `start_server(handle, host, port)` и `async with server: await server.serve_forever()`. Сокеты и Transport/Protocol — низкоуровневый API для авторов библиотек.

## 11. Ресурсы: сессии, пулы, транзакции, подпроцессы

- **Держать один HTTP-клиент на приложение и передавать его параметром.** В `aiohttp.ClientSession` и `httpx.AsyncClient` — пул подключений и куки. Клиент на каждый запрос теряет переиспользование соединений. У каждого запроса — таймаут и `raise_for_status()`.
- **Не выполнять конкурентные запросы на одном подключении к БД.** Одно подключение — один сокет: `gather` двух запросов на нём падает с `readexactly() called while another coroutine is already waiting`. Для конкурентности — пул (`create_pool(dsn, min_size=..., max_size=...)`), размер подбирать нагрузочным тестом: больше не значит лучше. Подключение брать через `async with pool.acquire() as conn:`, иначе оно не вернётся в пул и приложение зависнет.
- **Транзакцию оформлять через `async with conn.transaction():`.** Это коммит при успехе и откат при исключении. Вложенная транзакция — точка сохранения: её ошибку можно поймать, не откатывая внешнюю. Параметры — через `$1..$N` и `executemany`, а не форматированием строки.
- **Общие ресурсы веб-приложения создавать при старте и закрывать при остановке.** Starlette и FastAPI — `lifespan`, aiohttp 3.9+ — `cleanup_ctx` и `web.AppKey`. Состояние в памяти процесса (список вебсокетов) верно только при одном воркере, иначе нужно внешнее хранилище.
- **Асинхронную инициализацию выносить из `__init__`.** `__init__` не может быть корутиной, а корутины в `__getattr__` и `__getitem__` не вызывать. Объект получает готовые зависимости, а создаёт их асинхронная фабрика.
  ```python
  class OrderGateway:
      def __init__(self, pool: Pool) -> None:
          self._pool = pool

      @classmethod
      async def connect(cls, dsn: str) -> Self:
          return cls(await create_pool(dsn))
  ```
- **Подпроцесс запускать через `create_subprocess_exec(program, *args)`, а не `create_subprocess_shell`.** Оболочки на машинах различаются. Число одновременных подпроцессов ограничивать семафором.
- **При `stdout=PIPE` читать вывод одновременно с ожиданием процесса.** Плохо: `stdout=PIPE` и сразу `await process.wait()` — буфер заполнится, процесс ждёт нас, мы ждём процесс. Хорошо: `await process.communicate(input)` или отдельная задача, читающая `process.stdout`. `communicate` держит весь вывод в памяти — для длинного вывода и диалога с процессом читать поток.

## 12. Типичные ошибки

| Симптом | Причина | Что делать |
|---|---|---|
| `RuntimeWarning: coroutine ... was never awaited` | вызвали `async def` без `await` | дождаться или создать задачу |
| async-код не быстрее последовательного | `await` подряд, `[await ... for ...]` или блокирующий вызов в корутине | задачи в `TaskGroup`; `to_thread` или async-библиотека |
| другие задачи замирают на секунды | блокирующий или CPU-код в цикле | найти через `debug=True`, вынести в поток или процесс |
| `Task exception was never retrieved` | задачу не дождались | `TaskGroup`, `await` или обработка внутри задачи |
| `except SomeError` не ловит ошибку из группы | `TaskGroup` поднимает `ExceptionGroup` | `except*` |
| задача не останавливается по таймауту | CPU-код без `await` или проглоченная `CancelledError` | вынести вычисления; пробрасывать отмену |
| `run` не завершается после Ctrl+C | долгий поток в executor | поток не отменить — ограничить работу в нём |
| `queue.join()` висит | воркер упал или не вызвал `task_done()` | `try/finally` в воркере |
| `attached to a different loop` | примитив создан вне цикла или переиспользован | создавать в работающем цикле |
| `readexactly() called while another coroutine is already waiting` | конкурентные запросы на одном подключении | пул подключений |

## Чек-лист

1. Нет ли в корутинах блокирующих вызовов и тяжёлых вычислений — всё такое ушло в `to_thread` или пул процессов?
2. Независимые операции запущены конкурентно, а зависимые ждутся по очереди?
3. Каждая задача дождана или живёт в `TaskGroup`, на фоновые задачи есть ссылка?
4. У каждого сетевого ожидания есть срок, а у повторов — срок на попытку и растущая пауза?
5. `CancelledError` нигде не проглатывается, ресурсы освобождаются в `finally` или `async with`?
6. Ошибки группы разбираются через `except*`, долгоживущие воркеры логируют свои ошибки и не падают?
7. Конкурентность ограничена семафором, пулом или числом воркеров, очереди — `maxsize`?
8. Нет ли гонки, где состояние читается до `await` и пишется после?
9. HTTP-клиент и пул БД — по одному на приложение, создаются при старте и закрываются при остановке?
10. Используется API версии проекта: `TaskGroup` и `timeout` в 3.11+, `get_running_loop()` вместо `get_event_loop()`?
