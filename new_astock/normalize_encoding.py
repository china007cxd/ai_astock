from pathlib import Path

root = Path(__file__).parent
target = root / "ascii_copy.py"
payload = target.read_bytes()
print(repr(payload[:40]))
print("nul", payload.count(b"\x00"), "bom", payload.count(b"\xef\xbb\xbf"), "cr", payload.count(b"\r"))
try:
    payload.decode("utf-8")
    print("utf8-ok", len(payload))
except UnicodeDecodeError as exc:
    print("utf8-error", exc, repr(payload[exc.start - 8 : exc.end + 8]))
(root / "main_copy.py").write_text(payload.decode("utf-8"), encoding="utf-8")
(root / "ascii_copy.py").write_bytes(payload.decode("utf-8").encode("ascii", "replace").replace(b"\r\n", b"\n"))
