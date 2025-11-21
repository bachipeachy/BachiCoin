#!/usr/bin/env python3
"""Public API for the BachiCoin cross-module utilities."""

# WRAPPERS for crossmodule_config.py
from BachiCoin.lib_crossmodule.crossmodule_config import (
    NetworkType as _NetworkType,
    Currency as _Currency,
)
NetworkType = _NetworkType
Currency = _Currency

# WRAPPERS for dirs.py
from BachiCoin.lib_crossmodule.dirs import (
    Dirs as _Dirs,
    with_dirs as _with_dirs,
    adapt_context as _adapt_context,
)
Dirs = _Dirs
with_dirs = _with_dirs
adapt_context = _adapt_context

# WRAPPERS for node_context.py
from BachiCoin.lib_crossmodule.node_context import (
    NodeContext as _NodeContext,
    adapt_dirs as _adapt_dirs,
    adapt_context_arg as _adapt_context_arg,
)
NodeContext = _NodeContext
adapt_dirs = _adapt_dirs
adapt_context_arg = _adapt_context_arg

# WRAPPERS for bachicoin_services.py
from BachiCoin.lib_crossmodule.bachicoin_services import (
    initialize_node_context_services as _initialize_node_context_services,
)
initialize_node_context_services = _initialize_node_context_services
