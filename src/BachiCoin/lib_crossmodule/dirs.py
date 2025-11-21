from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from functools import wraps

@dataclass(frozen=True)
class Dirs:
    base: Path
    # Factory for interoperability with NodeContext or Dirs
    @classmethod
    def from_context(cls, ctx_or_dirs: Any) -> "Dirs":
        """Strip input to a Dirs instance.
        - Accepts either a Dirs instance or an object with a `node_dirs` attribute.
        """
        # Direct Dirs or Dirs-like
        if isinstance(ctx_or_dirs, cls):
            return ctx_or_dirs

        # NodeContext-like
        node_dirs = getattr(ctx_or_dirs, "node_dirs", None)
        if node_dirs and isinstance(node_dirs, cls):
            return node_dirs

        raise TypeError(
            f"Expected Dirs or NodeContext-like object with 'node_dirs', got {type(ctx_or_dirs)}"
        )

    # Canonical subdirectory accessors
    @property
    def user(self) -> Path:
        return self.base / "user"

    @property
    def wallet(self) -> Path:
        return self.base / "wallet"

    @property
    def tx(self) -> Path:
        return self.base / "tx"

    @property
    def mempool(self) -> Path:
        return self.base / "mempool"

    @property
    def blockchain(self) -> Path:
        return self.base / "blockchain"

    @property
    def validator(self) -> Path:
        return self.base / "validator"

    @property
    def proposer(self) -> Path:
        return self.base / "proposer"

    @property
    def attestor(self) -> Path:
        return self.base / "attestor"

    @property
    def finalizer(self) -> Path:
        return self.base / "finalizer"

    @property
    def net(self) -> Path:
        return self.base / "net"

    @property
    def public(self) -> Path:
        return self.base / "public"

    # -------------------------------------------------------------------
    # Helper utilities
    # -------------------------------------------------------------------
    def ensure(self) -> None:
        """Create all subdirectories if they don’t exist."""
        for p in (
            self.user,
            self.wallet,
            self.tx,
            self.blockchain,
            self.mempool,
            self.validator,
            self.proposer,
            self.attestor,
            self.finalizer,
            self.net,
            self.public,
        ):
            p.mkdir(parents=True, exist_ok=True)


# Decorator for DRY-style functions that consume dirs
def with_dirs(func: Callable) -> Callable:
    """
    Decorator to normalize the first argument into a Dirs instance.
        @with_dirs
        def create_user(dirs: Dirs, user_id: str):
            (dirs.user / f"{user_id}.json").write_text("{}")
    """
    @wraps(func)
    def wrapper(ctx_or_dirs: Any, *args: Any, **kwargs: Any):
        # Use the Dirs.from_context factory method
        dirs_instance = Dirs.from_context(ctx_or_dirs)
        return func(dirs_instance, *args, **kwargs)
    return wrapper

# Helper to adapt context for public API functions
def adapt_context(ctx_or_dirs: Any) -> Dirs:
    """
    Adapts an input (either Dirs or NodeContext) into a Dirs instance.
    This is for public API functions that need a Dirs object but might receive a NodeContext.
    """
    return Dirs.from_context(ctx_or_dirs)
