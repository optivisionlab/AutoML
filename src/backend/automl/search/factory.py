from typing import Dict, Type, Optional
from .base import SearchStrategy
import importlib
import pkgutil
import inspect
import os

class SearchStrategyFactory:
    """Factory to create and manage search strategies.
     Responsibilities:
       - Keep a registry of available SearchStrategy subclasses (name -> class)
       - Lazily auto‑discover classes in automl.search.strategies
       - Instantiate strategies with user‑provided kwargs (config)
     Typical usage:
       SearchStrategyFactory.get_strategy("gridsearch", cv=5)
     """

    _strategies: Dict[str, Type[SearchStrategy]] = {}
    _initialized: bool = False

    @classmethod
    def register_strategy(cls, name: str, strategy_class: Type[SearchStrategy]):
        """
            Register a new search strategy

            Args:
                name: The name to register the strategy under
                strategy_class: The strategy class to register

            Raises:
                ValueError: If the strategy is already registered
        """
        if not inspect.isclass(strategy_class) or not issubclass(strategy_class, SearchStrategy):
            raise TypeError("Strategy must be a subclass of SearchStrategy")
        cls._strategies[name.lower()] = strategy_class

    @classmethod
    def unregister_strategy(cls, name: str):
        """Unregister a search strategy from the factory
        Args:
            name: The name of strategy to unregister
        """
        cls._strategies.pop(name.lower(), None)

    @classmethod
    def get_strategy(cls, name: str, **kwargs) -> SearchStrategy:
        """
        Get an instance of the search strategy to create
        **kwargs: Configuration parameters for the strategy

        Returns:
            An instance of the search strategy

        Raises:
            ValueError: If the strategy is not registered
        """
        if not cls._initialized:
            cls._auto_discover_strategies()

        strategy_name = name.lower()
        if strategy_name not in cls._strategies[strategy_name]:
            available = list(cls._strategies.keys())
            raise ValueError(f"Strategy {name} not found. Available strategies: {available}")

        strategy_class = cls._strategies[strategy_name]
        return strategy_class(**kwargs)

    @classmethod
    def list_strategies(cls) -> Dict[str, Type[SearchStrategy]]:
        """List all registered strategies"""
        if not cls._initialized:
            cls._auto_discover_strategies()
        return cls._strategies.copy()

    @classmethod
    def get_strategy_info(cls, name: str) -> Optional[Dict]:
        """Get information about a strategy"""
        if not cls._initialized:
            cls._auto_discover_strategies()

        strategy_name = name.lower()
        if strategy_name not in cls._strategies:
            available = list(cls._strategies.keys())
            raise ValueError(f"Strategy {name} not found. Available strategies: {available}")

        strategy_class = cls._strategies[strategy_name]

        return {
            "name": strategy_name,
            "class": strategy_class.__name__,
            "module": strategy_class.__module__,
            "doc": strategy_class.__doc__,
            "default_config": strategy_class.get_default_config()
        }

    @classmethod
    def _auto_discover_strategies(cls) -> None:
        """Automatically discover and register strategies in automl.search.strategies"""
        if cls._initialized:
            return

        try:
            strategies_package = "automl.search.strategies"
            strategies_path = os.path.join(os.path.dirname(__file__), 'strategies')

            for finder, name, ispkg in pkgutil.iter_modules([strategies_path]):
               if not ispkg and name != "__init__":
                   try:
                       module_name = f"{strategies_package}.{name}"
                       module = importlib.import_module(module_name)

                       for attr_name in dir(module):
                           attr = getattr(module, attr_name)
                           if inspect.isclass(attr) and issubclass(attr, SearchStrategy) and attr != SearchStrategy:
                               strategy_name = attr.__name__.lower()
                               cls._strategies[strategy_name] = attr

                   except ImportError as e:
                       print(f"Error importing strategy {name}: {e}")
        except Exception as e:
            print(f"Error discovering strategies: {e}")

        cls._initialized = True

    def create_strategy_with_config(self, name: str, strategy_config: Dict) -> SearchStrategy:
        """Create a strategy with the given configuration"""

        if name not in strategy_config:
            raise ValueError(f"Strategy {name} not found in configuration")

        strategy_name = strategy_config['name']
        config = {k: v for k, v in strategy_config.items() if k != 'name'}
        return self.get_strategy(strategy_name, **config)

    @classmethod
    def discover_strategies(cls):
        """Discover and register strategies in automl.search.strategies"""
        cls._auto_discover_strategies()