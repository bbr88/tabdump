"""Data models for tab post-processing."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class Item:
    title: str
    url: str
    norm_url: str
    clean_url: str
    domain: str
    browser: Optional[str]
