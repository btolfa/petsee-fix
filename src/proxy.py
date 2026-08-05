"""
Автономный TCP-прокси для исправления координат трекера apptrackpets.
Без зависимостей (только stdlib). Альтернатива mitmproxy-аддону.

    python3 src/proxy.py --listen 0.0.0.0:5455 --upstream apptrackpets.com:5455

Трекер направляете на этот прокси; прокси правит GPS-пакеты клиент->сервер
и прозрачно проксирует остальное в обе стороны.
"""

import argparse
import asyncio
import os

from gt06 import iter_frames, is_gps_frame, parse_gps, fix_gps_frame, app_display


async def pump_client_to_server(reader, writer):
    """Клиент(трекер) -> сервер: разбираем кадры и правим GPS."""
    buf = b""
    try:
        while True:
            chunk = await reader.read(65536)
            if not chunk:
                break
            buf += chunk
            frames, buf = iter_frames(buf)
            out = bytearray()
            for frame in frames:
                if is_gps_frame(frame):
                    fix = parse_gps(frame)
                    new_frame = fix_gps_frame(frame)
                    if new_frame != frame:
                        was = app_display(fix)               # что показывало приложение
                        now = app_display(parse_gps(new_frame))  # что покажет после фикса
                        print(f"[coord-fix] {fix.datetime_str}  приложение: "
                              f"{was[0]:+.5f},{was[1]:+.5f} -> "
                              f"{now[0]:+.5f},{now[1]:+.5f}", flush=True)
                    out += new_frame
                else:
                    out += frame
            if out:
                writer.write(bytes(out))
                await writer.drain()
    finally:
        writer.close()


async def pump_raw(reader, writer):
    """Сервер -> клиент: прозрачно."""
    try:
        while True:
            chunk = await reader.read(65536)
            if not chunk:
                break
            writer.write(chunk)
            await writer.drain()
    finally:
        writer.close()


def make_handler(upstream_host, upstream_port):
    async def handle(client_reader, client_writer):
        peer = client_writer.get_extra_info("peername")
        print(f"[+] подключение {peer}", flush=True)
        try:
            srv_reader, srv_writer = await asyncio.open_connection(
                upstream_host, upstream_port)
        except OSError as e:
            print(f"[!] апстрим недоступен: {e}", flush=True)
            client_writer.close()
            return
        await asyncio.gather(
            pump_client_to_server(client_reader, srv_writer),
            pump_raw(srv_reader, client_writer),
            return_exceptions=True,
        )
        print(f"[-] отключение {peer}", flush=True)

    return handle


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--listen", default=os.environ.get("LISTEN", "0.0.0.0:5455"))
    ap.add_argument("--upstream",
                    default=os.environ.get("UPSTREAM", "apptrackpets.com:5455"))
    args = ap.parse_args()

    lh, lp = args.listen.rsplit(":", 1)
    uh, up = args.upstream.rsplit(":", 1)

    server = await asyncio.start_server(make_handler(uh, int(up)), lh, int(lp))
    print(f"[*] слушаю {args.listen}, апстрим {args.upstream}", flush=True)
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
