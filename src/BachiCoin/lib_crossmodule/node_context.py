#!/usr/bin/env python3
"""node_context.py — bridge Dirs-based code with NodeContext injection."""

from typing import Dict, Any, Optional, Union, Callable
from dataclasses import dataclass, field
from BachiCoin.lib_crossmodule.dirs import Dirs # Changed import to lib_crossmodule.dirs


#  NodeContext Dataclass
@dataclass
class NodeContext:
    """Container for a node’s runtime services, configuration, and ephemeral state."""

    # --- Core Services ---
    user_service: Optional[Any] = None
    wallet_service: Optional[Any] = None
    blockchain_service: Optional[Any] = None
    mempool_service: Optional[Any] = None
    validator_service: Optional[Any] = None
    tx_service: Optional[Any] = None
    proposer_service: Optional[Any] = None
    attestor_service: Optional[Any] = None
    finalizer_service: Optional[Any] = None

    # --- Configuration ---
    node_dirs: Optional[Dirs] = None
    port: Optional[int] = None
    network: Optional[str] = None
    currency: Optional[str] = None

    # --- Derived Contexts ---
    consensus_context: Dict[str, Any] = field(default_factory=dict)
    address_map: Dict[str, str] = field(default_factory=dict)

    # --- Dynamic runtime service ---
    network_service: Optional[Any] = None

    # ---- Constructors ----
    @classmethod
    def from_dirs(cls, dirs: Dirs) -> "NodeContext":
        if not isinstance(dirs, Dirs):
            raise TypeError(f"Expected Dirs, got {type(dirs)}")
        return cls(node_dirs=dirs)

    @classmethod
    def from_args(cls, **kwargs) -> "NodeContext":
        """Construct from either `dirs` or explicit fields."""
        if "dirs" in kwargs and "node_dirs" not in kwargs:
            kwargs["node_dirs"] = kwargs.pop("dirs")
        return cls(**kwargs)

#  Adaptation Utilities
def adapt_dirs(ctx_or_dirs: Union[NodeContext, Dirs]) -> Dirs:
    """Return a Dirs instance from either a NodeContext or Dirs input."""
    if isinstance(ctx_or_dirs, NodeContext):
        if ctx_or_dirs.node_dirs is None:
            raise ValueError("NodeContext.node_dirs is missing.")
        return ctx_or_dirs.node_dirs
    if isinstance(ctx_or_dirs, Dirs):
        return ctx_or_dirs
    raise TypeError(f"Expected NodeContext or Dirs, got {type(ctx_or_dirs)}")


def adapt_context(ctx_or_dirs: Union[NodeContext, Dirs]) -> NodeContext:
    """Return a NodeContext instance from either a NodeContext or Dirs input."""
    if isinstance(ctx_or_dirs, NodeContext):
        return ctx_or_dirs
    if isinstance(ctx_or_dirs, Dirs):
        return NodeContext(node_dirs=ctx_or_dirs)
    raise TypeError(f"Expected NodeContext or Dirs, got {type(ctx_or_dirs)}")


def adapt_context_arg(factory_func: Callable, *args, **kwargs):
    """Wrapper enabling factories to accept either NodeContext or Dirs."""
    if "node_context" in kwargs:
        node_ctx = kwargs.pop("node_context")
        return factory_func(node_ctx, *args, **kwargs)
    if "dirs" in kwargs:
        node_ctx = NodeContext.from_dirs(kwargs.pop("dirs"))
        return factory_func(node_ctx, *args, **kwargs)
    if args:
        first, *rest = args
        if isinstance(first, NodeContext):
            return factory_func(*args, **kwargs)
        if isinstance(first, Dirs):
            node_ctx = NodeContext.from_dirs(first)
            return factory_func(node_ctx, *rest, **kwargs)
    raise TypeError("Expected NodeContext or Dirs as first positional or keyword arg.")


#  Smoke Test / Example Usage

if __name__ == "__main__":
    from tests.test_config import dirs

    def _smoke_test():
        """Quick self-test showing how adapt_* functions behave."""

        # --- NodeContext.from_dirs ---
        ctx = NodeContext.from_dirs(dirs)
        print(f" ctx -> {ctx}")
        assert isinstance(ctx, NodeContext)

        # --- adapt_dirs ---
        assert adapt_dirs(dirs) is dirs
        assert adapt_dirs(ctx) is dirs

        # --- adapt_context ---
        assert adapt_context(ctx) is ctx
        c2 = adapt_context(dirs)
        print(f" c2 -> {c2}")
        assert isinstance(c2, NodeContext) and c2.node_dirs is dirs

        # --- adapt_context_arg ---
        def demo_factory(node_ctx, label="x"):
            return f"ok:{isinstance(node_ctx, NodeContext)}:{label}"

        assert adapt_context_arg(demo_factory, dirs) == "ok:True:x"
        assert adapt_context_arg(demo_factory, node_context=ctx) == "ok:True:x"

        print("✅ NodeContext smoke test passed.")


    _smoke_test()
