import importlib
import inspect
import pkgutil

from app.strategies.base import BaseStrategy


def discover_strategies(package_name: str = "strategies") -> list[BaseStrategy]:
    package = importlib.import_module(package_name)
    strategies: list[BaseStrategy] = []

    for module_info in pkgutil.iter_modules(package.__path__, package.__name__ + "."):
        module = importlib.import_module(module_info.name)
        for _, obj in inspect.getmembers(module, inspect.isclass):
            if obj is BaseStrategy or not issubclass(obj, BaseStrategy):
                continue
            if obj.__module__ != module.__name__:
                continue
            strategy = obj()
            if not strategy.enabled:
                continue
            strategies.append(strategy)

    return sorted(strategies, key=lambda strategy: strategy.name)
