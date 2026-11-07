import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from gt06 import fix_gps_frame  # noqa: E402
from proxy import make_handler  # noqa: E402

# Реальные кадры из petsee.mitm
LOGIN = bytes.fromhex("78780d010861261022207563020d0a")
HEARTBEAT = bytes.fromhex("7878071361020801640d0a")
GPS = bytes.fromhex("787815101a08050c1e1f9a04aba487009b6cac023c2efff3000d0a")
LOGIN_ACK = bytes.fromhex("787801010d0a")


class FakeServer:
    """TCP-сервер, который пишет всё полученное по соединениям и отвечает на login."""

    def __init__(self, answer_login=False):
        self.answer_login = answer_login
        self.connections: list[bytearray] = []
        self.reads: list[bytes] = []
        self._writers = []

    async def start(self):
        self.server = await asyncio.start_server(self._handle, "127.0.0.1", 0)
        self.port = self.server.sockets[0].getsockname()[1]
        return self

    async def _handle(self, reader, writer):
        got = bytearray()
        self.connections.append(got)
        self._writers.append(writer)
        while data := await reader.read(4096):
            got += data
            self.reads.append(data)
            if self.answer_login and data.startswith(LOGIN):
                writer.write(LOGIN_ACK)
                await writer.drain()
        writer.close()

    def drop_connections(self):
        for w in self._writers:
            w.close()
        self._writers.clear()

    async def stop(self):
        self.drop_connections()
        self.server.close()
        await self.server.wait_closed()


async def until(cond, timeout=2.0):
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while not cond():
        assert loop.time() < deadline, "условие не выполнилось"
        await asyncio.sleep(0.01)


async def start_proxy(vendor_port, mirror_port):
    server = await asyncio.start_server(
        make_handler("127.0.0.1", vendor_port, "127.0.0.1", mirror_port), "127.0.0.1", 0)
    return server, server.sockets[0].getsockname()[1]


def unused_port():
    import socket
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def test_vendor_gets_fixed_traccar_gets_raw():
    async def scenario():
        vendor = await FakeServer().start()
        traccar = await FakeServer(answer_login=True).start()
        proxy, port = await start_proxy(vendor.port, traccar.port)
        _, tracker = await asyncio.open_connection("127.0.0.1", port)

        for frame in (LOGIN, HEARTBEAT, GPS):
            tracker.write(frame)
            await tracker.drain()
            await asyncio.sleep(0.05)

        expected_vendor = LOGIN + HEARTBEAT + fix_gps_frame(GPS)
        await until(lambda: vendor.connections and bytes(vendor.connections[0]) == expected_vendor)
        await until(lambda: traccar.connections and bytes(traccar.connections[0]) == LOGIN + HEARTBEAT + GPS)

        tracker.close()
        proxy.close()
        await vendor.stop()
        await traccar.stop()

    asyncio.run(scenario())


def test_traccar_down_does_not_affect_vendor():
    async def scenario():
        vendor = await FakeServer().start()
        proxy, port = await start_proxy(vendor.port, unused_port())
        _, tracker = await asyncio.open_connection("127.0.0.1", port)

        for frame in (LOGIN, HEARTBEAT, GPS):
            tracker.write(frame)
            await tracker.drain()

        await until(lambda: vendor.connections
                    and bytes(vendor.connections[0]) == LOGIN + HEARTBEAT + fix_gps_frame(GPS))

        tracker.close()
        proxy.close()
        await vendor.stop()

    asyncio.run(scenario())


def test_reconnect_replays_login_before_next_chunk():
    async def scenario():
        vendor = await FakeServer().start()
        traccar = await FakeServer(answer_login=True).start()
        proxy, port = await start_proxy(vendor.port, traccar.port)
        _, tracker = await asyncio.open_connection("127.0.0.1", port)

        tracker.write(LOGIN)
        await tracker.drain()
        await until(lambda: len(traccar.connections) == 1 and bytes(traccar.connections[0]) == LOGIN)

        traccar.drop_connections()  # рестарт Traccar посреди сессии трекера
        await asyncio.sleep(0.05)

        tracker.write(GPS)
        await tracker.drain()
        await until(lambda: len(traccar.connections) == 2 and bytes(traccar.connections[1]) == LOGIN + GPS)
        # login и кадр пришли разными чтениями: Topin-декодер разбирает по одному кадру на чтение
        assert traccar.reads[-2:] == [LOGIN, GPS]

        tracker.close()
        proxy.close()
        await vendor.stop()
        await traccar.stop()

    asyncio.run(scenario())
