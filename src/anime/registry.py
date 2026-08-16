"""Provider registry for anime providers."""
from typing import Dict, List, Type, Optional
from .base import AnimeProvider


class ProviderRegistry:
    """Registry of anime providers."""

    def __init__(self):
        self._providers: Dict[str, AnimeProvider] = {}

    def register(self, provider: AnimeProvider) -> None:
        """Register a provider instance."""
        self._providers[provider.name] = provider

    def get(self, name: str) -> Optional[AnimeProvider]:
        """Get a provider by name."""
        return self._providers.get(name)

    def list(self) -> List[str]:
        """List registered provider names."""
        return list(self._providers.keys())

    def all(self) -> List[AnimeProvider]:
        """Get all registered providers."""
        return list(self._providers.values())


# Global registry instance
registry = ProviderRegistry()