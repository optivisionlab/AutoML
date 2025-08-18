from typing import Dict, Type, Optional
from .base import SearchStrategy
import importlib
import pkgutil
import inspect

class SearchStrategyFactory:
    """Factory to create and manage search strategies"""

    _strategies: Dict[str, Type[SearchStrategy]] = {}

    @classmethod
    def register_strategy(cls, name: str, strategy_class: Type[SearchStrategy]):