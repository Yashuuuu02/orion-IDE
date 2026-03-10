import logging
from typing import Optional
from pydantic import BaseModel
from orion.core.config import settings

logger = logging.getLogger(__name__)

class SearchResult(BaseModel):
    title: str
    url: str
    snippet: str
    relevance_score: float

class MCPDispatcher:
    """
    Routes MCP tool calls to configured search providers.
    Default provider: Tavily (if API key configured).
    Fallback: Brave, Perplexity (if configured).
    Provider is swappable via OrionSettings — no code change needed.
    """

    def __init__(self):
        self._provider: Optional[str] = None
        self._api_keys: dict[str, str] = {}

    def configure(self, provider: str, api_key: str):
        self._provider = provider
        self._api_keys[provider] = api_key

    def is_configured(self) -> bool:
        return self._provider is not None and self._provider in self._api_keys

    async def search(
        self,
        query: str,
        context_file: Optional[str] = None
    ) -> list[SearchResult]:
        """
        Calls active search provider.
        If context_file provided: append file content summary to query.
        If MOCK_LLM=true: return mock results without calling real API.
        If not configured: return empty list with warning log.
        """
        if not self.is_configured():
            logger.warning("MCPDispatcher: no search provider configured")
            return []

        if settings.MOCK_LLM:
            return [
                SearchResult(
                    title="Mock Result 1",
                    url="https://example.com/1",
                    snippet=f"Mock snippet for query: {query}",
                    relevance_score=0.95
                ),
                SearchResult(
                    title="Mock Result 2",
                    url="https://example.com/2",
                    snippet=f"Another mock result for: {query}",
                    relevance_score=0.87
                )
            ]

        # Real provider call — wrap in try/except
        try:
            if self._provider == "tavily":
                return await self._search_tavily(query, context_file)
            elif self._provider == "brave":
                return await self._search_brave(query, context_file)
            else:
                logger.warning(f"Unknown provider: {self._provider}")
                return []
        except Exception as e:
            logger.error(f"MCPDispatcher search failed: {e}")
            return []

    async def _search_tavily(
        self,
        query: str,
        context_file: Optional[str]
    ) -> list[SearchResult]:
        import httpx
        if context_file:
            query = f"{query} [context: {context_file[:200]}]"
        api_key = self._api_keys["tavily"]
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.tavily.com/search",
                json={"query": query, "api_key": api_key, "max_results": 5},
                timeout=10.0
            )
            data = response.json()
            return [
                SearchResult(
                    title=r.get("title", ""),
                    url=r.get("url", ""),
                    snippet=r.get("content", ""),
                    relevance_score=r.get("score", 0.0)
                )
                for r in data.get("results", [])
            ]

    async def _search_brave(
        self,
        query: str,
        context_file: Optional[str]
    ) -> list[SearchResult]:
        import httpx
        api_key = self._api_keys["brave"]
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://api.search.brave.com/res/v1/web/search",
                params={"q": query},
                headers={"X-Subscription-Token": api_key},
                timeout=10.0
            )
            data = response.json()
            results = data.get("web", {}).get("results", [])
            return [
                SearchResult(
                    title=r.get("title", ""),
                    url=r.get("url", ""),
                    snippet=r.get("description", ""),
                    relevance_score=0.8
                )
                for r in results[:5]
            ]

mcp_dispatcher = MCPDispatcher()
