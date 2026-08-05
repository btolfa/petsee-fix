"""
GT06-подобный протокол трекера apptrackpets (порт 5455).

Реверс по дампу petsee.mitm. Кадр:

    78 78 | FLAG(1) | PROTO(1) | ...payload... | 0D 0A

  * 78 78          — магический заголовок
  * FLAG           — байт флагов/подтипа (НЕ длина, как в классическом GT06!)
  * PROTO          — тип пакета: 0x10 = GPS-фикс, 0x1a = WiFi/LBS-скан,
                     0x13 = heartbeat, и т.д.
  * 0D 0A          — стоп-байты (кадр разделяется по ним)

GPS-пакет (PROTO = 0x10), payload:

    datetime(6) | sat(1) | lat(4 BE) | lon(4 BE) | speed(1) | status(2 BE) | ...хвост

  * datetime   — YY MM DD hh mm ss (YY — год от 2000)
  * lat/lon    — |градусы| * 1 800 000, беззнаковое (магнитуда)
  * status     — «course & status», 16 бит:
                   bit12 (0x1000) — есть фикс
                   bit11 (0x0800) — долгота западная (lon отрицательна)  [станд. GT06]
                   bit10 (0x0400) — широта северная (lat положительна)   [станд. GT06]
                   bit0..9        — курс (0..360)

БАГ apptrackpets: приложение интерпретирует биты полушарий инверсно
стандарту, из-за чего N/W Хихон отображается как S/E в Атлантике.
Фикс — инвертировать bit10 и bit11: status ^ 0x0C00.
"""

from dataclasses import dataclass

MAGIC = b"\x78\x78"
STOP = b"\x0d\x0a"

PROTO_GPS = 0x10
PROTO_WIFI = 0x1A
PROTO_HEARTBEAT = 0x13

COORD_SCALE = 1_800_000
HEMISPHERE_MASK = 0x0C00  # bit10 (широта) | bit11 (долгота)


@dataclass
class GpsFix:
    flag: int
    year: int
    month: int
    day: int
    hour: int
    minute: int
    second: int
    satellites: int
    lat: float          # знаковая, после применения бит полушарий
    lon: float          # знаковая, после применения бит полушарий
    speed: int
    course: int
    positioned: bool
    status: int         # сырое слово course&status
    trailing: bytes

    @property
    def datetime_str(self) -> str:
        return (f"20{self.year:02d}-{self.month:02d}-{self.day:02d} "
                f"{self.hour:02d}:{self.minute:02d}:{self.second:02d}")


def is_gps_frame(frame: bytes) -> bool:
    """Похож ли кадр на GPS-пакет (0x10) с валидной датой и достаточной длиной."""
    if len(frame) < 24 or frame[0:2] != MAGIC or frame[3] != PROTO_GPS:
        return False
    year, month, day, hour, minute, second = frame[4:10]
    return (0 <= year <= 99 and 1 <= month <= 12 and 1 <= day <= 31
            and hour <= 23 and minute <= 59 and second <= 61)


def parse_gps(frame: bytes) -> GpsFix:
    """Разобрать полный GPS-кадр (с 0x7878 и 0x0d0a) в GpsFix."""
    if not is_gps_frame(frame):
        raise ValueError("не GPS-кадр")
    flag = frame[2]
    year, month, day, hour, minute, second = frame[4:10]
    sat = frame[10]
    lat_raw = int.from_bytes(frame[11:15], "big")
    lon_raw = int.from_bytes(frame[15:19], "big")
    speed = frame[19]
    status = int.from_bytes(frame[20:22], "big")
    trailing = frame[22:-2] if frame.endswith(STOP) else frame[22:]

    lat = lat_raw / COORD_SCALE
    lon = lon_raw / COORD_SCALE
    # Стандартный GT06: bit10 set => North, bit11 set => West (lon отрицательна)
    if not (status & 0x0400):
        lat = -lat
    if status & 0x0800:
        lon = -lon

    return GpsFix(
        flag=flag, year=year, month=month, day=day, hour=hour,
        minute=minute, second=second, satellites=sat,
        lat=lat, lon=lon, speed=speed, course=status & 0x03FF,
        positioned=bool(status & 0x1000), status=status, trailing=trailing,
    )


def fix_gps_frame(frame: bytes) -> bytes:
    """
    Скорректировать GPS-кадр под баг apptrackpets: инвертировать биты
    полушарий (bit10/bit11) статус-слова. Остальные байты не трогаем,
    длина не меняется (CRC в этом протоколе нет).

    Не-GPS-кадры возвращаются без изменений.
    """
    if not is_gps_frame(frame):
        return frame
    status = int.from_bytes(frame[20:22], "big")
    fixed = status ^ HEMISPHERE_MASK
    return frame[:20] + fixed.to_bytes(2, "big") + frame[22:]


def app_display(fix: "GpsFix") -> tuple:
    """
    Что покажет приложение apptrackpets для данного кадра.

    Наблюдение из дампа: стандартный GT06-декод статуса 0x3c2e даёт
    правильный Хихон (N,W), но приложение показывает mid-Atlantic (S,E) —
    т.е. приложение трактует биты полушарий инверсно стандарту. Значит
    отображаемые координаты = инверсия знаков стандартного декода.
    """
    return (-fix.lat, -fix.lon)


def iter_frames(buffer: bytes):
    """
    Извлечь полные кадры (7878 ... 0d0a) из буфера потока.
    Возвращает (список_кадров, остаток_буфера).
    Разбор по стоп-байтам 0d0a; неполный хвост отдаётся как остаток.
    """
    frames = []
    i = 0
    n = len(buffer)
    while True:
        start = buffer.find(MAGIC, i)
        if start < 0:
            return frames, b""
        end = buffer.find(STOP, start + 2)
        if end < 0:
            return frames, buffer[start:]  # ждём остаток кадра
        frame = buffer[start:end + 2]
        frames.append(frame)
        i = end + 2
        if i >= n:
            return frames, b""
