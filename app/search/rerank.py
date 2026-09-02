"""Optional LLM re-ranking pass over the fused hit list - reuses the exact
same multi-provider LLM layer as the /api/generate pipeline
(app.llm.client.call_structured), so this is provider-agnostic for free:
whichever provider LLM_PROVIDER selects handles this too, no separate key
or client needed.

Degrades open, not closed, unlike app/safety.py's guardrail: a rerank
failure just means the fused order is kept as-is - reordering is a quality
improvement on top of an already-valid ranking, not a correctness gate."""

from app.llm.client import call_structured
from app.observability.logging_utils import log_event
from app.schemas.quick_search import RerankOrder
from app.search.hit import Hit


def llm_rerank(query: str, hits: list[Hit]) -> list[Hit]:
    if not hits:
        return hits

    system = (
        "You are a search relevance expert. Given a search query and a list of "
        "candidate passages (by index), reorder the indices from most to least "
        "relevant to the query. Return every index exactly once."
    )
    candidates_block = "\n".join(f"{i}. {hit.text}" for i, hit in enumerate(hits))
    user_message = f"Query: {query}\n\nCandidates:\n{candidates_block}"

    try:
        result = call_structured(system, user_message, RerankOrder, max_tokens=500)
    except Exception as e:
        log_event("quick_search_rerank_failed", query=query, error=str(e))
        return hits

    order = result.parsed.ranked_indices
    if sorted(order) != list(range(len(hits))):
        # The model dropped, duplicated, or invented an index - not a valid
        # permutation, so don't trust it; keep the fused order.
        log_event("quick_search_rerank_invalid_order", query=query, order=order)
        return hits

    return [hits[i] for i in order]
