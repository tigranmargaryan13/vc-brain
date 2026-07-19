"""VC Brain — sourcing layer.

Cold-start Founder Score prototype: turn a public footprint into a
coverage-weighted, evidence-cited score with an honest confidence band.

See docs/sourcing-architecture.md for the design this implements.
"""
import os as _os


def _load_env():
    """Load KEY=VALUE lines from a repo-root .env into os.environ (stdlib, no deps).

    A real shell export always wins — we never overwrite an already-set var.
    Empty values are skipped so the blank template line can't clobber anything.
    """
    root = _os.path.dirname(_os.path.dirname(__file__))
    path = _os.path.join(root, ".env")
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                key = key.strip()
                if key.startswith("export "):
                    key = key[len("export "):].strip()
                val = val.strip().strip('"').strip("'")
                if key and val and key not in _os.environ:
                    _os.environ[key] = val
    except FileNotFoundError:
        pass


_load_env()

from .founder_score import score_github_handle, FounderScore  # noqa: E402

__all__ = ["score_github_handle", "FounderScore"]
