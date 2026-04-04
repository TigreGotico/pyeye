"""Tests for Phase 2: HTTP data loading and caching."""

from __future__ import annotations

import os
import tempfile

from pyeye import execute


class TestHTTPLoading:
    """FR 2i.41-43: HTTP data loading with caching."""

    def test_cache_dir_parameter(self):
        """cache_dir parameter is accepted without error."""
        # Can't test actual HTTP in CI, but verify the parameter works
        with tempfile.TemporaryDirectory() as tmpdir:
            # Use a local file to verify cache_dir doesn't break anything
            data = "@prefix : <http://ex.org/> .\n:a :p :b ."
            data_file = os.path.join(tmpdir, "data.ttl")
            with open(data_file, "w") as f:
                f.write(data)

            r = execute(
                data_paths=[data_file],
                cache_dir=tmpdir,
            )
            # Should work normally with local files
            assert r.stats["derived"] == 0

    def test_local_file_still_works(self):
        """Local files work alongside cache_dir."""
        with tempfile.TemporaryDirectory() as tmpdir:
            data = "@prefix : <http://ex.org/> .\n:a :p :b ."
            data_file = os.path.join(tmpdir, "data.ttl")
            with open(data_file, "w") as f:
                f.write(data)

            r = execute(
                data_paths=[data_file],
                cache_dir=tmpdir,
            )
            assert r.stats["derived"] == 0
