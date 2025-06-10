from dataclasses import dataclass, field
from typing import Dict, List, Optional

@dataclass
class Book:
    """Simple representation of a tracked book."""

    title: str
    isbns: Dict[str, Dict]
    notes: Optional[str] = None
