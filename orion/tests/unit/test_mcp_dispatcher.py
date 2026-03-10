import pytest
import os
from orion.mcp.dispatcher import MCPDispatcher, SearchResult

@pytest.mark.asyncio
async def test_dispatcher_not_configured_returns_empty():
    dispatcher = MCPDispatcher()
    # It is unconfigured by default
    results = await dispatcher.search("test query")
    assert results == []

@pytest.mark.asyncio
async def test_dispatcher_mock_llm_returns_results():
    dispatcher = MCPDispatcher()
    dispatcher.configure("tavily", "fake-key")

    # Ensure MOCK_LLM is true
    os.environ["MOCK_LLM"] = "true"
    from orion.core.config import settings
    settings.MOCK_LLM = True

    results = await dispatcher.search("test query")
    assert len(results) == 2
    assert results[0].title == "Mock Result 1"
    assert results[0].url == "https://example.com/1"
    assert results[0].relevance_score == 0.95
    assert results[1].title == "Mock Result 2"

@pytest.mark.asyncio
async def test_dispatcher_mock_result_contains_query():
    dispatcher = MCPDispatcher()
    dispatcher.configure("tavily", "fake-key")
    from orion.core.config import settings
    settings.MOCK_LLM = True

    query = "my specific query"
    results = await dispatcher.search(query)
    assert query in results[0].snippet

def test_search_result_schema():
    # Must be valid Pydantic model — no validation error
    result = SearchResult(title="t", url="u", snippet="s", relevance_score=0.9)
    assert result.title == "t"
    assert result.url == "u"
    assert result.snippet == "s"
    assert result.relevance_score == 0.9
