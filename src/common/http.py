import hashlib, json, os, time
from pathlib import Path
import requests

RATE_LIMITS = {"default": 1.5, "steamspy": 1.0, "reddit": 1.0, "scrape": 1.0}
_last_call: dict[str, float] = {}

def _data_dir() -> Path:
    return Path(os.environ.get("IDLE_DATA_DIR", "data")) / "raw"

def _key(url: str, params: dict | None) -> str:
    raw = url + json.dumps(params or {}, sort_keys=True)
    return hashlib.sha1(raw.encode()).hexdigest()

class _Cached:
    def __init__(self, text: str, status: int = 200):
        self.text = text; self.status_code = status
    def json(self): return json.loads(self.text)

def _live_get(url, params, headers):
    resp = requests.get(url, params=params, headers=headers, timeout=30)
    return resp.text, resp.status_code

def _throttle(rate_key: str):
    gap = RATE_LIMITS.get(rate_key, 1.5)
    last = _last_call.get(rate_key, 0.0)
    wait = gap - (time.time() - last)
    if wait > 0: time.sleep(wait)
    _last_call[rate_key] = time.time()

def cached_get(url, *, source, params=None, headers=None, rate_key="default", refresh=False):
    cdir = _data_dir() / source
    cdir.mkdir(parents=True, exist_ok=True)
    cfile = cdir / f"{_key(url, params)}.cache"
    if cfile.exists() and not refresh:
        return _Cached(cfile.read_text(encoding="utf-8"))
    _throttle(rate_key)
    text, status = _live_get(url, params, headers)
    if status == 200:
        cfile.write_text(text, encoding="utf-8")
    return _Cached(text, status)
