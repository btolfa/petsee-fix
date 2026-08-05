"""
Офлайн-анализатор дампа mitmproxy (petsee.mitm): парсит tnetstring-формат,
извлекает TCP-сообщения и декодирует GT06-кадры.

    python3 src/decode_dump.py petsee.mitm
"""

import sys

from gt06 import iter_frames, is_gps_frame, parse_gps, PROTO_WIFI, PROTO_HEARTBEAT


def _parse_tnetstring(data, pos):
    """Минимальный парсер tnetstring в варианте mitmproxy."""
    colon = data.index(b":", pos)
    length = int(data[pos:colon])
    payload = data[colon + 1:colon + 1 + length]
    typ = data[colon + 1 + length:colon + 2 + length]
    nextpos = colon + 2 + length
    if typ in (b",", b";"):
        return payload, nextpos
    if typ == b"#":
        return int(payload), nextpos
    if typ == b"^":
        return float(payload), nextpos
    if typ == b"!":
        return payload == b"true", nextpos
    if typ == b"~":
        return None, nextpos
    if typ == b"]":
        out, p = [], colon + 1
        while p < colon + 1 + length:
            v, p = _parse_tnetstring(data, p)
            out.append(v)
        return out, nextpos
    if typ == b"}":
        out, p = {}, colon + 1
        while p < colon + 1 + length:
            k, p = _parse_tnetstring(data, p)
            v, p = _parse_tnetstring(data, p)
            out[k] = v
        return out, nextpos
    raise ValueError(f"неизвестный тип {typ!r}")


def load_flows(path):
    data = open(path, "rb").read()
    pos, flows = 0, []
    while pos < len(data):
        while pos < len(data) and data[pos:pos + 1] in (b"\n", b"\r", b" "):
            pos += 1
        if pos >= len(data):
            break
        v, pos = _parse_tnetstring(data, pos)
        flows.append(v)
    return flows


def describe(frame):
    proto = frame[3] if len(frame) > 3 else None
    if is_gps_frame(frame):
        fx = parse_gps(frame)
        return (f"GPS   {fx.datetime_str}  {fx.lat:+.5f},{fx.lon:+.5f}  "
                f"sat=0x{fx.satellites:02x} spd={fx.speed} crs={fx.course} "
                f"status=0x{fx.status:04x}")
    if proto == PROTO_WIFI:
        return f"WIFI/LBS proto=0x1a len={len(frame)}"
    if proto == PROTO_HEARTBEAT:
        return f"heartbeat proto=0x13 {frame.hex()}"
    return f"proto=0x{proto:02x} len={len(frame)} {frame.hex()}"


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "petsee.mitm"
    flows = load_flows(path)
    print(f"# потоков: {len(flows)}")
    for fi, flow in enumerate(flows):
        print(f"\n=== FLOW {fi} type={flow.get(b'type')} ===")
        for frm, content, _ts in flow.get(b"messages", []):
            direction = "C->S" if frm else "S->C"
            frames, _ = iter_frames(bytes(content))
            for frame in frames:
                print(f"  {direction}  {describe(frame)}")


if __name__ == "__main__":
    main()
