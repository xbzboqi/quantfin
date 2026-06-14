"""Parquet-based caching layer with TTL expiry."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)

DEFAULT_TTL_MAP = {
    "spot": timedelta(minutes=5),
    "hist_daily": timedelta(hours=4),
    "financial": timedelta(days=1),
    "market_valuation": timedelta(hours=1),
    "gold": timedelta(minutes=5),
}


class DataCache:
    """A simple Parquet-based cache with per-category TTL."""

    def __init__(
        self,
        cache_dir: str | Path = "~/.quantfin/cache",
        ttl_map: dict[str, timedelta] | None = None,
    ):
        self.cache_dir = Path(cache_dir).expanduser().resolve()
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl_map = ttl_map or DEFAULT_TTL_MAP

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(self, key: str) -> Optional[pd.DataFrame]:
        """Return cached DataFrame if it exists and is not expired."""
        parquet_path = self._parquet_path(key)
        meta_path = self._meta_path(key)

        if not parquet_path.exists():
            return None

        meta = self._read_meta(meta_path)
        if meta is None:
            return None

        if self._is_expired(meta):
            logger.debug("Cache expired for key=%s", key)
            self._delete(key)
            return None

        logger.debug("Cache HIT for key=%s", key)
        return pd.read_parquet(parquet_path)

    def set(self, key: str, df: pd.DataFrame, ttl: timedelta | None = None) -> None:
        """Write a DataFrame to cache.

        Args:
            key: Unique cache key, e.g. "spot/a_share".
            df: DataFrame to cache.
            ttl: Time-to-live. If None, look up in ttl_map by key prefix;
                 if not found, default to 1 hour.
        """
        parquet_path = self._parquet_path(key)
        meta_path = self._meta_path(key)

        parquet_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(parquet_path, index=False)

        if ttl is None:
            ttl = self._resolve_ttl(key)

        meta = {
            "cached_at": datetime.now().isoformat(),
            "ttl_seconds": int(ttl.total_seconds()),
            "rows": len(df),
        }
        meta_path.write_text(json.dumps(meta), encoding="utf-8")
        logger.debug("Cached key=%s (%d rows, ttl=%s)", key, len(df), ttl)

    def invalidate(self, prefix: str = "") -> int:
        """Remove all cached entries whose key starts with *prefix*.

        Returns number of entries deleted.
        """
        count = 0
        for parquet_path in self.cache_dir.rglob(f"{prefix}*.parquet") if prefix else self.cache_dir.rglob("*.parquet"):
            key = self._path_to_key(parquet_path)
            self._delete(key)
            count += 1
        return count

    def clear_expired(self) -> int:
        """Remove all expired cache entries. Returns count removed."""
        count = 0
        for meta_path in self.cache_dir.rglob("*.meta.json"):
            meta = self._read_meta(meta_path)
            if meta is None or self._is_expired(meta):
                key = meta_path.stem.replace(".meta", "")
                self._delete(key)
                count += 1
        return count

    def fetch_or_cache(
        self,
        key: str,
        fetcher_fn,
        ttl: timedelta | None = None,
        force_refresh: bool = False,
    ) -> pd.DataFrame:
        """Get data from cache or fetch from source if not present/expired.

        Args:
            key: Cache key.
            fetcher_fn: Zero-argument callable that returns a DataFrame.
            ttl: Override TTL for this entry.
            force_refresh: If True, re-fetch even if cached.

        Returns DataFrame from cache or fresh source.
        """
        if not force_refresh:
            cached = self.get(key)
            if cached is not None:
                return cached

        logger.info("Fetching fresh data for key=%s", key)
        df = fetcher_fn()
        if df is not None and not df.empty:
            self.set(key, df, ttl=ttl)
        return df

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _parquet_path(self, key: str) -> Path:
        safe = key.replace("/", "__").replace("\\", "__")
        return self.cache_dir / f"{safe}.parquet"

    def _meta_path(self, key: str) -> Path:
        safe = key.replace("/", "__").replace("\\", "__")
        return self.cache_dir / f"{safe}.meta.json"

    def _path_to_key(self, parquet_path: Path) -> str:
        return parquet_path.stem.replace("__", "/")

    @staticmethod
    def _read_meta(meta_path: Path) -> Optional[dict]:
        if not meta_path.exists():
            return None
        try:
            return json.loads(meta_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None

    def _is_expired(self, meta: dict) -> bool:
        cached_at = datetime.fromisoformat(meta["cached_at"])
        ttl = timedelta(seconds=meta["ttl_seconds"])
        return datetime.now() > cached_at + ttl

    def _resolve_ttl(self, key: str) -> timedelta:
        for prefix, ttl in self.ttl_map.items():
            if key.startswith(prefix) or prefix in key:
                return ttl
        return timedelta(hours=1)

    def _delete(self, key: str) -> None:
        parquet_path = self._parquet_path(key)
        meta_path = self._meta_path(key)
        parquet_path.unlink(missing_ok=True)
        meta_path.unlink(missing_ok=True)
