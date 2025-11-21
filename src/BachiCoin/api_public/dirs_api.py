#!/usr/bin/env python3
"""dirs_api.py - Unified Dirs abstraction and utilities for path-based modules.

This module provides:
- `Dirs`: a simple dataclass encapsulating node directory structure.
- `Dirs.from_context()`: a safe factory for use with NodeContext or Dirs.
- `@with_dirs`: a decorator for DRY-style lib functions that need Dirs access.

Design goals:
- KISS: no circular imports, no runtime dependencies on NodeContext.
- Explicit where needed, implicit where convenient.
"""

from __future__ import annotations
from typing import Callable, Any
from functools import wraps

# Import Dirs, with_dirs, and adapt_context from their new canonical location
from BachiCoin.lib_crossmodule.dirs import Dirs as _Dirs, with_dirs as _with_dirs, adapt_context as _adapt_context

# Re-export Dirs, with_dirs, and adapt_context for public API consumers
Dirs = _Dirs
with_dirs = _with_dirs
adapt_context = _adapt_context


# Smoke test (run directly)
if __name__ == "__main__":
    from tests.test_config import dirs as test_dirs_instance

    # Test Dirs re-export
    assert isinstance(test_dirs_instance, Dirs)
    print("✅ Dirs re-exported successfully.")

    # Test @with_dirs decorator
    @with_dirs
    def sample_action(dirs: Dirs, name: str):
        path = dirs.user / f"{name}.txt"
        path.write_text("ok")
        print(f"{path} -> {path.read_text()}")
        return path.exists()

    assert sample_action(test_dirs_instance, "alice")
    print("✅ @with_dirs decorator works with Dirs instance.")

    # Test adapt_context
    class MockNodeContext:
        def __init__(self, node_dirs):
            self.node_dirs = node_dirs
    
    mock_node_context_instance = MockNodeContext(test_dirs_instance)
    adapted_dirs = adapt_context(mock_node_context_instance)
    assert isinstance(adapted_dirs, Dirs)
    print("✅ adapt_context works with NodeContext-like object.")

    print("\n--- dirs_api.py Smoke Test Passed Successfully! ---")
