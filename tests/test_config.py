from pathlib import Path
from BachiCoin.api_public.dirs_api import Dirs

# Define the base path for all test data
base_path = Path.home() / "BachiCoin"

# --- Single Directory Setup (for single-node tests) ---
dirs = Dirs(base=base_path / "ztemp")
dirs.ensure() # Keep this for the simple, single-node tests

# --- Multi-Directory Setup (for multi-node simulation) ---
# Define the directory paths but do not create them here.
# The test orchestrator (libtest_multinode_main.py) is responsible for their lifecycle.
dirs_0 = Dirs(base=base_path / "ztemp_0")
dirs_1 = Dirs(base=base_path / "ztemp_1")
dirs_2 = Dirs(base=base_path / "ztemp_2")
dirs_3 = Dirs(base=base_path / "ztemp_3")
dirs_4 = Dirs(base=base_path / "ztemp_4")

all_node_dirs = [dirs_0, dirs_1, dirs_2, dirs_3, dirs_4]
