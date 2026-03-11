import asyncio, time, hashlib, logging
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
from dataclasses import dataclass, field
import httpx
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import LLM_CONFIGS, LLMConfig

logger = logging.getLogger(__name__)

@dataclass
class CacheEntry:
    response: str
    expires_at: datetime

_cache: Dict[str, CacheEntry] = {}

def _cache_key(llm_name, prompt):
    return hashlib.md5(f"{llm_name}:{prompt}".encode()).hexdigest()

def _get_cache(key):
    e = _cache.get(key)
    if e and datetime.now() < e.expires_at:
        return e.response
    return None

def _set_cache(key, response, ttl=15):
    _cache[key] = CacheEntry(response, datetime.now() + timedelta(minutes=ttl))

@dataclass
class RateLimiter:
    rpm: int
    _ts: list = field(default_factory=list)
    def can(self):
        now = time.time()
        self._ts = [t for t in self._ts if now - t < 60]
        return len(self._ts) < self.rpm
    def record(self):
        self._ts.append(time.time())
    async def wait(self):
        while not self.can():
            await asyncio.sleep(5)
        self.record()

_rl = {n: RateLimiter(c.requests_per_minute) for n, c in LLM_CONFIGS.items()}

async def _openai_compat(cfg, sys_p, usr_p):
    headers = {"Authorization": f"Bearer {cfg.api_key}", "Content-Type": "application/json"}
    payload = {"model": cfg.model, "messages": [{"role": "system", "content": sys_p}, {"role": "user", "content": usr_p}], "max_tokens": cfg.max_tokens, "temperature": cfg.temperature}
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(f"{cfg.base_url}/chat/completions", headers=headers, json=payload)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip()

async def _claude(cfg, sys_p, usr_p):
    headers = {"x-api-key": cfg.api_key, "anthropic-version": "2023-06-01", "Content-Type": "application/json"}
    payload = {"model": cfg.model, "max_tokens": cfg.max_tokens, "system": sys_p, "messages": [{"role": "user", "content": usr_p}]}
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(f"{cfg.base_url}/messages", headers=headers, json=payload)
        r.raise_for_status()
        return r.json()["content"][0]["text"].strip()

async def _gemini(cfg, sys_p, usr_p):
    url = f"{cfg.base_url}/models/{cfg.model}:generateContent?key={cfg.api_key}"
    payload = {"system_instruction": {"parts": [{"text": sys_p}]}, "contents": [{"parts": [{"text": usr_p}]}], "generationConfig": {"maxOutputTokens": cfg.max_tokens, "temperature": cfg.temperature}}
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(url, json=payload)
        r.raise_for_status()
        return r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()

async def call_llm(name, sys_p, usr_p, use_cache=True, retries=3):
    cfg = LLM_CONFIGS.get(name)
    if not cfg: return False, f"LLM {name} tidak ditemukan"
    if not cfg.enabled: return False, f"{cfg.name} dinonaktifkan"
    if not cfg.is_available: return False, f"{cfg.name}: API key belum diisi"
    ck = _cache_key(name, usr_p)
    if use_cache:
        cached = _get_cache(ck)
        if cached: return True, cached
    await _rl[name].wait()
    for i in range(1, retries+1):
        try:
            if name == "claude": resp = await _claude(cfg, sys_p, usr_p)
            elif name == "gemini": resp = await _openai_compat(cfg, sys_p, usr_p)
            else: resp = await _openai_compat(cfg, sys_p, usr_p)
            if use_cache: _set_cache(ck, resp)
            return True, resp
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                await asyncio.sleep(2**i * 5)
            elif e.response.status_code in (401, 403):
                return False, f"{cfg.name}: API key tidak valid"
            else:
                if i == retries: return False, f"{cfg.name}: HTTP {e.response.status_code}"
                await asyncio.sleep(2**i)
        except Exception as e:
            if i == retries: return False, f"{cfg.name}: {e}"
            await asyncio.sleep(2**i)
    return False, f"{cfg.name}: Gagal"

async def call_all_llms(sys_p, usr_p, names=None):
    targets = names or list(LLM_CONFIGS.keys())
    tasks = {n: call_llm(n, sys_p, usr_p) for n in targets if LLM_CONFIGS[n].enabled}
    results = await asyncio.gather(*tasks.values(), return_exceptions=True)
    return {n: (False, str(r)) if isinstance(r, Exception) else r for n, r in zip(tasks.keys(), results)}
