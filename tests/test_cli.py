"""Tests for pyeye.cli — command-line interface."""

from __future__ import annotations

import subprocess
import sys
import tempfile
import os

import pytest


CLI = [sys.executable, "-m", "pyeye.cli"]


def run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(CLI + list(args), capture_output=True, text=True)


class TestCLI:
    def test_help(self):
        r = run_cli("--help")
        assert r.returncode == 0
        assert "pyeye" in r.stdout

    def test_no_args_empty_output(self):
        r = run_cli()
        assert r.returncode == 0
        assert r.stdout == ""

    def test_nope_passthrough(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".ttl", delete=False) as f:
            f.write('@prefix : <http://ex.org/> .\n:a :p :b .\n')
            f.flush()
            fname = f.name
        try:
            r = run_cli("--n3", fname, "--nope")
            assert r.returncode == 0
            assert ":p" in r.stdout or "http://ex.org/p" in r.stdout
        finally:
            os.unlink(fname)

    def test_parse_error_clean_message(self):
        """Invalid N3 file produces clean error, not traceback."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".n3", delete=False) as f:
            f.write("=> {:a :b :c} .\n")
            f.flush()
            fname = f.name
        try:
            r = run_cli("--n3", fname)
            assert r.returncode == 1
            # Should have a clean error message, not a traceback
            assert "pyeye: error" in r.stderr
            assert "Traceback" not in r.stderr
        finally:
            os.unlink(fname)

    def test_missing_file_error(self):
        """Non-existent file produces clean error."""
        r = run_cli("--n3", "/nonexistent/file.n3")
        assert r.returncode == 1
        assert "pyeye: error" in r.stderr

    def test_statistics_flag(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".ttl", delete=False) as f:
            f.write('@prefix : <http://ex.org/> .\n:a :p :b .\n')
            f.flush()
            data_file = f.name
        with tempfile.NamedTemporaryFile(mode="w", suffix=".n3", delete=False) as f:
            f.write('@prefix : <http://ex.org/> .\n{?X :p ?Y} => {?X :q ?Y} .\n')
            f.flush()
            rule_file = f.name
        try:
            r = run_cli("--n3", data_file, "--query", rule_file, "--statistics")
            assert r.returncode == 0
            assert "steps=" in r.stderr
            assert "derived=" in r.stderr
            assert "time=" in r.stderr
        finally:
            os.unlink(data_file)
            os.unlink(rule_file)

    def test_quiet_suppresses_stderr(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".ttl", delete=False) as f:
            f.write('@prefix : <http://ex.org/> .\n:a :p :b .\n')
            f.flush()
            data_file = f.name
        with tempfile.NamedTemporaryFile(mode="w", suffix=".n3", delete=False) as f:
            f.write('@prefix : <http://ex.org/> .\n{?X :p ?Y} => {?X :q ?Y} .\n')
            f.flush()
            rule_file = f.name
        try:
            r = run_cli("--n3", data_file, "--query", rule_file, "--statistics", "--quiet")
            assert r.returncode == 0
            assert r.stderr == ""
        finally:
            os.unlink(data_file)
            os.unlink(rule_file)

    def test_tactic_limited_answer(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".ttl", delete=False) as f:
            f.write('@prefix : <http://ex.org/> .\n:a :p :b .\n:c :p :d .\n:e :p :f .\n')
            f.flush()
            data_file = f.name
        with tempfile.NamedTemporaryFile(mode="w", suffix=".n3", delete=False) as f:
            f.write('@prefix : <http://ex.org/> .\n{?X :p ?Y} => {?X :q ?Y} .\n')
            f.flush()
            rule_file = f.name
        try:
            r = run_cli("--n3", data_file, "--query", rule_file,
                        "--tactic", "limited-answer", "2", "--pass")
            assert r.returncode == 0
            # Should have at most 2 derived triples
            lines = [l for l in r.stdout.strip().split("\n") if l and not l.startswith("@prefix")]
            # 3 input + 2 derived = 5 total, but limited to 2 derivations
            assert len(lines) <= 5  # could be 5 (3 input + 2 limited)
        finally:
            os.unlink(data_file)
            os.unlink(rule_file)

    def test_prefix_flag(self):
        r = run_cli("--prefix", "x=http://x.org/")
        assert r.returncode == 0

    def test_max_inferences_flag(self):
        r = run_cli("--max-inferences", "0")
        assert r.returncode == 0
