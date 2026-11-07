"""
Mirror: неизменённая копия потока трекера в Traccar (протокол Topin).

Traccar — пассивный наблюдатель: всё, что он отвечает, выбрасывается, а его
падение или медленность никак не влияет на путь Tracker -> Vendor Cloud.
Поэтому feed() никогда не ждёт: запись в Traccar буферизуется, при
переполнении буфера данные Mirror отбрасываются.

Сессия Topin в Traccar начинается с login-кадра. Mirror кэширует login
текущей сессии трекера и при переподключении к Traccar (лениво — на
следующем куске потока) сначала отправляет login, ждёт ответ и только потом
сам кусок. Без ожидания Topin-декодер (у него нет frame decoder'а) получит
login и кадр одним TCP-чтением и разберёт только login.
"""

import asyncio

PROTO_LOGIN = 0x01
MAX_BUFFER = 64 * 1024
CONNECT_TIMEOUT = 5
LOGIN_ACK_TIMEOUT = 5


def is_login(frame: bytes) -> bool:
    return len(frame) > 3 and frame[3] == PROTO_LOGIN


class Mirror:
    def __init__(self, host: str, port: int, log=print):
        self._host = host
        self._port = port
        self._log = log
        self._login: bytes | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._task: asyncio.Task | None = None

    def feed(self, chunk: bytes, frames: list[bytes]) -> None:
        """Отдать в Mirror сырой кусок потока трекера и разобранные из него кадры."""
        for frame in frames:
            if is_login(frame):
                self._login = frame

        if self._writer is not None:
            if self._writer.transport.get_write_buffer_size() < MAX_BUFFER:
                self._writer.write(chunk)
            return

        # не подключены: подключаемся, если ещё не; кусок, пришедший во время
        # подключения, теряется (best-effort)
        if self._task is None:
            self._task = asyncio.create_task(self._run(chunk))

    async def close(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _run(self, first_chunk: bytes) -> None:
        writer = None
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(self._host, self._port), CONNECT_TIMEOUT)

            if self._login is not None and not first_chunk.startswith(self._login):
                writer.write(self._login)
                await asyncio.wait_for(reader.read(256), LOGIN_ACK_TIMEOUT)
            writer.write(first_chunk)
            self._writer = writer

            while await reader.read(4096):  # ответы Traccar выбрасываем
                pass
            self._log(f"[mirror] Traccar {self._host}:{self._port} закрыл соединение")
        except (OSError, TimeoutError) as e:
            self._log(f"[mirror] Traccar {self._host}:{self._port} недоступен: {e!r}")
        finally:
            self._writer = None
            self._task = None
            if writer is not None:
                writer.close()
