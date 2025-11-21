#!/usr/bin/env python3
# storage_config.py

import os
from enum import Enum

class StorageType(Enum):
    """Supported storage types."""
    FILE = "file"
    SQLITE = "sqlite"
