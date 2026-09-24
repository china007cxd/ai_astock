import urllib.request, json, ssl

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

req = urllib.request.Request("https://web.ifzq.gtimg.cn/appstock/app/day/query?code=sz000001")
req.add_header("User-Agent", UA)
r = urllib.request.urlopen(req, timeout=10, context=ctx)
d = json.loads(r.read())
data = (d.get("data") or {}).get("sz000001") or {}
print("keys:", list(data.keys()))
for k, v in data.items():
    if isinstance(v, list):
        print("%s: %d items, first: %s" % (k, len(v), json.dumps(v[0], ensure_ascii=False)[:150] if v else "-"))
    else:
        print("%s: %s" % (k, json.dumps(v, ensure_ascii=False)[:200]))