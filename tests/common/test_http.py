import json
from src.common.http import cached_get

def test_cache_hit_skips_network(tmp_path, monkeypatch):
    monkeypatch.setenv("IDLE_DATA_DIR", str(tmp_path))
    calls = {"n": 0}
    import src.common.http as http
    def fake_live(url, params, headers):
        calls["n"] += 1
        return '{"ok": true}', 200
    monkeypatch.setattr(http, "_live_get", fake_live)
    r1 = cached_get("http://x/api", source="t", rate_key="default")
    r2 = cached_get("http://x/api", source="t", rate_key="default")
    assert r1.json() == {"ok": True}
    assert r2.json() == {"ok": True}
    assert calls["n"] == 1  # second call served from cache
