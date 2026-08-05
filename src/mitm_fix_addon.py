"""
mitmproxy-аддон: на лету исправляет GPS-координаты трекера apptrackpets.

Запуск (reverse-режим, как в исходном дампе):

    mitmdump --mode reverse:tcp://apptrackpets.com:5455 -p 5455 \
             -s src/mitm_fix_addon.py

Трекер должен ходить на ваш хост:5455 (подмените DNS/hosts или настройте
на сам трекер). Аддон разбирает поток, находит GPS-пакеты (proto 0x10),
инвертирует биты полушарий и пересылает исправленный кадр серверу.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gt06 import (  # noqa: E402
    iter_frames, is_gps_frame, parse_gps, fix_gps_frame, app_display,
)


class TrackerCoordFix:
    def __init__(self):
        # буфер незавершённых кадров на каждое направление каждого потока
        self._buffers = {}

    def tcp_message(self, flow):
        msg = flow.messages[-1]
        # правим только трафик клиента (трекера) к серверу
        if not msg.from_client:
            return

        key = (id(flow), msg.from_client)
        buf = self._buffers.get(key, b"") + bytes(msg.content)
        frames, rest = iter_frames(buf)
        self._buffers[key] = rest

        out = bytearray()
        for frame in frames:
            if is_gps_frame(frame):
                fix = parse_gps(frame)
                new_frame = fix_gps_frame(frame)
                if new_frame != frame:
                    corrected = parse_gps(new_frame)
                    was = app_display(fix)
                    now = app_display(corrected)
                    print(f"[coord-fix] {fix.datetime_str}  приложение: "
                          f"{was[0]:+.5f},{was[1]:+.5f} -> "
                          f"{now[0]:+.5f},{now[1]:+.5f} "
                          f"(status 0x{fix.status:04x}->0x{corrected.status:04x})")
                out += new_frame
            else:
                out += frame

        # Детерминированно пересобираем поток: пересылаем только полные кадры,
        # неполный хвост (rest) осядет в буфере и уйдёт со следующим сообщением.
        # Так гарантируем отсутствие дублей и корректный реврайт.
        msg.content = bytes(out)


addons = [TrackerCoordFix()]
