"""Unit tests for the data cache layer."""

import time
from datetime import timedelta

import numpy as np
import pandas as pd
import pytest

from quantfin.data.cache import DataCache


class TestDataCache:
    def test_set_and_get(self, temp_cache_dir):
        """Cache write then read returns the same data."""
        cache = DataCache(temp_cache_dir)
        df = pd.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]})
        cache.set("test/data", df, ttl=timedelta(hours=1))
        result = cache.get("test/data")
        assert result is not None
        pd.testing.assert_frame_equal(df, result)

    def test_cache_miss(self, temp_cache_dir):
        """Non-existent key returns None."""
        cache = DataCache(temp_cache_dir)
        assert cache.get("nonexistent") is None

    def test_expiry(self, temp_cache_dir):
        """Expired cache returns None."""
        cache = DataCache(temp_cache_dir)
        df = pd.DataFrame({"x": [1]})
        cache.set("test/expire", df, ttl=timedelta(seconds=0))
        time.sleep(0.1)  # Let it expire
        assert cache.get("test/expire") is None

    def test_invalidate_prefix(self, temp_cache_dir):
        """Invalidate removes matching keys."""
        cache = DataCache(temp_cache_dir)
        cache.set("spot/a", pd.DataFrame({"x": [1]}), ttl=timedelta(hours=1))
        cache.set("spot/b", pd.DataFrame({"x": [2]}), ttl=timedelta(hours=1))
        cache.set("hist/a", pd.DataFrame({"x": [3]}), ttl=timedelta(hours=1))
        n = cache.invalidate("spot")
        assert n == 2
        assert cache.get("hist/a") is not None

    def test_invalidate_all(self, temp_cache_dir):
        """Invalidate with no prefix removes all."""
        cache = DataCache(temp_cache_dir)
        cache.set("a", pd.DataFrame({"x": [1]}), ttl=timedelta(hours=1))
        cache.set("b", pd.DataFrame({"x": [2]}), ttl=timedelta(hours=1))
        assert cache.invalidate() == 2

    def test_clear_expired(self, temp_cache_dir):
        """Clear expired removes only expired entries."""
        cache = DataCache(temp_cache_dir)
        cache.set("fresh", pd.DataFrame({"x": [1]}), ttl=timedelta(hours=1))
        cache.set("stale", pd.DataFrame({"x": [2]}), ttl=timedelta(seconds=0))
        time.sleep(0.1)
        removed = cache.clear_expired()
        assert removed >= 1
        assert cache.get("fresh") is not None

    def test_fetch_or_cache_hit(self, temp_cache_dir):
        """fetch_or_cache returns cached data when valid."""
        cache = DataCache(temp_cache_dir)
        df = pd.DataFrame({"x": [1, 2]})
        cache.set("test/foc", df, ttl=timedelta(hours=1))
        call_count = 0

        def fetcher():
            nonlocal call_count
            call_count += 1
            return pd.DataFrame({"x": [3, 4]})

        result = cache.fetch_or_cache("test/foc", fetcher)
        assert call_count == 0  # No fetch — cached
        assert result["x"].tolist() == [1, 2]

    def test_fetch_or_cache_miss(self, temp_cache_dir):
        """fetch_or_cache calls fetcher on cache miss."""
        cache = DataCache(temp_cache_dir)
        call_count = 0

        def fetcher():
            nonlocal call_count
            call_count += 1
            return pd.DataFrame({"x": [3, 4]})

        result = cache.fetch_or_cache("test/foc_miss", fetcher)
        assert call_count == 1
        assert result["x"].tolist() == [3, 4]
