import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from gt06 import (  # noqa: E402
    is_gps_frame, parse_gps, fix_gps_frame, iter_frames,
    PROTO_GPS, PROTO_WIFI,
)

# Реальный GPS-кадр из petsee.mitm (Хихон, 2026-08-05 12:30:31)
GPS_FRAME = bytes.fromhex("787815101a08050c1e1f9a04aba487009b6cac023c2efff3000d0a")
HEARTBEAT = bytes.fromhex("7878071361020801640d0a")
WIFI_FRAME = bytes.fromhex(
    "7878071a260805122535ecbedd5b004c46e6461724f5fa46c8b422dfbeff486c"
    "4cbc8aaf0049e019545d9084539636544d5ea6559636544d5eaa560300d60700"
    "000ce80000104c5a00000ce80000104d6400000ce80000104c5a000d0a")


def test_identify():
    assert is_gps_frame(GPS_FRAME)
    assert not is_gps_frame(HEARTBEAT)
    assert not is_gps_frame(WIFI_FRAME)
    assert GPS_FRAME[3] == PROTO_GPS
    assert WIFI_FRAME[3] == PROTO_WIFI


def test_parse_gijon():
    fx = parse_gps(GPS_FRAME)
    assert fx.datetime_str == "2026-08-05 12:30:31"
    # Стандартный GT06-декод должен давать правильный Хихон (N, W)
    assert abs(fx.lat - 43.53202) < 1e-4
    assert abs(fx.lon - (-5.65883)) < 1e-4
    assert fx.positioned
    assert fx.course == 46


def test_fix_flips_hemispheres():
    fixed = fix_gps_frame(GPS_FRAME)
    assert fixed != GPS_FRAME
    assert len(fixed) == len(GPS_FRAME)
    # меняются только 2 байта статуса (offset 20..21): 0x3c2e -> 0x302e
    assert fixed[20:22] == b"\x30\x2e"
    assert fixed[:20] == GPS_FRAME[:20]
    assert fixed[22:] == GPS_FRAME[22:]

    orig = parse_gps(GPS_FRAME)
    corr = parse_gps(fixed)
    # знаки обеих координат инвертированы, магнитуда сохранена
    assert abs(corr.lat + orig.lat) < 1e-9
    assert abs(corr.lon + orig.lon) < 1e-9
    # курс не тронут
    assert corr.course == orig.course


def test_fix_is_noop_for_non_gps():
    assert fix_gps_frame(HEARTBEAT) == HEARTBEAT
    assert fix_gps_frame(WIFI_FRAME) == WIFI_FRAME


def test_iter_frames_splits_and_buffers():
    stream = GPS_FRAME + HEARTBEAT
    frames, rest = iter_frames(stream)
    assert frames == [GPS_FRAME, HEARTBEAT]
    assert rest == b""

    # неполный хвост придерживается
    frames, rest = iter_frames(GPS_FRAME + HEARTBEAT[:-1])
    assert frames == [GPS_FRAME]
    assert rest == HEARTBEAT[:-1]
