# Agent Architecture Review & Improvement Plan

> **Scope:** `backend/app/agent/` — LangGraph graph, all nodes, and the services they depend on.  
> **Date:** March 2026  
> **Status:** Living document — update as improvements are shipped.

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Current Strengths](#2-current-strengths)
3. [Identified Issues & Weaknesses](#3-identified-issues--weaknesses)
4. [Improvement Plan](#4-improvement-plan)
   - [P0 — Bug Fixes (Ship Now)](#p0--bug-fixes-ship-now)
   - [P1 — Reliability & Correctness](#p1--reliability--correctness)
   - [P2 — Performance & Cost](#p2--performance--cost)
   - [P3 — Observability & Maintainability](#p3--observability--maintainability)
   - [P4 — Capability Expansions](#p4--capability-expansions)
5. [Proposed Target Architecture](#5-proposed-target-architecture)
6. [Migration Checklist](#6-migration-checklist)

---

## 1. Architecture Overview

### 1.1 Graph Topology (as-built)

```
START
  │
  ▼
internal_indexer ──► style_analyst
                           │
               ┌───────────┴────────────┐
      deep=False│                        │deep=True
               ▼                        ▼
          researcher          deep_generate_query
               │                 │    ▲
               │      ┌──────────┘    │ (loop ≤ 3)
               │      │               │
               │  ┌───┼───────────┐   │
               │  ▼   ▼           ▼   │
               │ deep_web  deep_social deep_academic
               │  └───┬───────────┘
               │      ▼
               │ deep_reflection ──► deep_finalize
               │                          │
               └──────────────────────────┘
                          │
                          ▼
                       planner
                          │
                          ▼
                   human_approval  ◄──── [INTERRUPT — user edits outline]
                          │
                    (resume via Command)
                          │
              ┌───────────▼──────────┐
              │  for each section     │
              │  writer ──► critic   │
              │     ▲         │      │
              │     └─────────┘      │ (max 1 retry per section)
              │        visuals        │
              └──────────────────────┘
                          │
                          ▼
                       publisher
                          │
                          ▼
                         END
```

### 1.2 State Schema (`AgentState`)

| Group | Fields | Notes |
|-------|--------|-------|
| **Inputs** | `user_id`, `topic`, `tone_urls`, `target_domain`, `selected_bins`, `use_local`, `model_provider`, `model_name`, `research_sources`, `deep_research_mode`, `blog_size`, `target_word_count`, `section_word_budgets`, `research_guidelines`, `target_audience`, `extra_context` | All set at graph invocation |
| **Research** | `research_data`, `deep_research_results`, `research_loop_count`, `is_sufficient`, `generated_queries` | Deep research fields accumulated with `operator.add` |
| **Context** | `style_profile`, `internal_links` | Populated in Phase 1 |
| **Planning** | `outline`, `section_word_budgets` | Set by planner, edited by user |
| **Drafting** | `current_section_index`, `draft_sections`, `critique_feedback`, `section_retries` | Mutated section-by-section |
| **Output** | `final_content` | Set by publisher |

Total: **~25 top-level fields**.

### 1.3 Node Responsibilities

| Node | Phase | LLM Calls | External I/O |
|------|-------|-----------|--------------|
| `internal_indexer` | 1 | 0 | Sitemap HTTP fetch |
| `style_analyst` | 1 | 1 | URL scrape (Firecrawl) |
| `researcher` | 2A | 1 (query gen) | Firecrawl × 2, Arxiv × 1, Pinecone × n |
| `deep_generate_query` | 2B | 1 | — |
| `deep_web_research` | 2B | 0 | Firecrawl × 1 per query |
| `deep_social_research` | 2B | 0 | Firecrawl × 1 (social filter) |
| `deep_academic_research` | 2B | 0 | Arxiv × 1 |
| `deep_reflection` | 2B | 1 | — |
| `deep_finalize` | 2B | 0 | Pinecone (internal search) |
| `planner` | 3 | 2 (outline + budget) | — |
| `human_approval` | 3 | 0 | — |
| `writer` | 4 | 1 per section | — |
| `critic` | 4 | 1 per section | — |
| `visuals` | 4 | 1 per section | — |
| `publisher` | 5 | 1 | — |

**Estimated LLM calls per run:** 7–17 (small) · 13–27 (medium) · 23–47 (large).

---

## 2. Current Strengths

| Strength | Detail |
|----------|--------|
| **Resumable checkpoints** | `AsyncPostgresSaver` persists full graph state after every node; runs survive restarts and support the human-in-the-loop pause. |
| **Reflexion quality loop** | Writer → Critic → Writer retry ensures at least one revision pass per section. |
| **Multi-source parallelism** | Standard researcher runs all four source types concurrently via `asyncio.gather`. Deep research fan-out uses `Send()` for true parallel execution. |
| **Style DNA extraction** | Dedicated `style_analyst` node extracts brand voice from reference URLs before any content is written. |
| **Internal knowledge grounding** | Pinecone RAG with per-user namespacing prevents knowledge contamination across tenants. |
| **Real-time observability** | SSE streaming exposes per-node events to the frontend without polling. |
| **LLM agnosticism** | `llm_service` factory supports OpenAI, Anthropic, Google, and Ollama with a single toggle. |
| **Word-budget enforcement** | Two-pass planner allocates budgets; writer prompt includes hard min/max limits; critic flags violations. |

---

## 3. Identified Issues & Weaknesses

Issues are grouped by severity.

### 3.1 Bugs

#### B-1 · Deep research parallel nodes receive a stripped `Dict`, not `AgentState`
**File:** `graph.py` lines 63–71; `deep_research.py` lines 46, 100, 149  
`Send("deep_web_research", {"query": q})` passes only `{"query": q}`. The node signatures declare `state: Dict`, but they then silently lack `use_local`, `model_provider`, `model_name`, and every other state field. The nodes use hardcoded defaults that silently ignore user preferences.

```python
# graph.py — current
tasks.extend([Send("deep_web_research", {"query": q}) for q in queries])

# nodes/deep_research.py — current (no access to model settings)
async def web_research_node(state: Dict):
    query = state["query"]  # model_provider/use_local unavailable
```

**Impact:** Users who select Google or Ollama as their provider will have deep research silently use whatever Firecrawl defaults to; provider preferences are ignored.

#### B-2 · Deep research loop runs one extra iteration
**File:** `graph.py` line 85  
```python
if state.get("is_sufficient") or state.get("research_loop_count", 0) > 3:
```
`research_loop_count` is incremented *before* reflection (`loop_count + 1` at the end of `generate_query_node`). This means the check fires after counts 4, 5, 6 — i.e., the loop can run **4 times** before the `> 3` guard trips. The intent (≤ 3 loops) is not achieved.

#### B-3 · Critic always triggers a rewrite; "pass" path is unreachable
**File:** `nodes/critic.py` line 10, 132–138  
`CritiqueResult.feedback` is described as: *"If the draft is perfect, provide minor polish suggestions."* The field is never empty — the node unconditionally sends the writer back to `goto="writer"`. There is no "pass" decision; every first-pass draft gets rewritten regardless of quality.

**Impact:** Each section costs 2× writer + 1× critic LLM calls even for already-good drafts.

#### B-4 · `finalize_answer_node` source-type detection is fragile
**File:** `nodes/deep_research.py` lines 247–258  
Source type is inferred by checking whether the *first citation URL* contains `reddit.com`, `x.com`, or `arxiv.org`. A social result without citations, or a web result from `x.com/some-tech-article`, will be mis-categorised, producing incorrect `source_id` prefixes that confuse the planner and citation renderer.

#### B-5 · `research_loop_count` not passed to deep research parallel nodes
**File:** `graph.py` lines 56–73; `nodes/deep_research.py` lines 25–43  
`generate_query_node` increments `research_loop_count` and returns it, but when the next query batch is dispatched via `Send()`, no loop context is forwarded. The per-node prompt says *"If this is a follow-up loop, focus on missing details"* but `loop_count` in the payload is always `0`.

---

### 3.2 Reliability Issues

#### R-1 · No timeout on external API calls
**Files:** `researcher.py`, `deep_research.py`, `internal_indexer.py`  
Every `asyncio.to_thread(firecrawl_service.search, ...)` and `arxiv_service.search(...)` call can hang indefinitely. A slow or unresponsive API will block the entire node (and therefore the checkpoint write), potentially stalling a run for minutes without any user feedback.

#### R-2 · No deduplication of research results
**File:** `researcher.py` lines 244–265; `deep_research.py` `finalize_answer_node`  
The same URL can appear multiple times across queries and across deep research loop iterations. Duplicate content inflates the context window, wastes tokens, and can cause the planner to create redundant citations.

#### R-3 · Planner silently truncates sections without re-balancing budgets
**File:** `nodes/planner.py` lines 142–150  
When the LLM creates too many sections, the code truncates to `max_sections` *after* the budget allocation has already been computed. The budget now references non-existent section IDs, leading to missing word targets for every dropped section fallback.

#### R-4 · Internal search in `deep_finalize` runs after parallel research completes instead of in parallel
**File:** `nodes/deep_research.py` lines 278–280  
`_run_internal_search()` is called sequentially at the end of `finalize_answer_node`. This adds latency that could be eliminated by making internal search another `Send()` target in the deep research fan-out (alongside `deep_web_research`, `deep_social_research`, `deep_academic_research`).

#### R-5 · No per-user concurrency limit
**File:** `api/agent.py` (endpoint handler)  
Nothing prevents a single user from starting multiple generation runs simultaneously. Because all runs share the same PostgreSQL connection pool and Pinecone index, concurrent runs from the same user can interfere and exhaust API-rate quotas.

---

### 3.3 Performance & Cost Issues

#### P-1 · `internal_indexer` and `style_analyst` run sequentially even though they are independent
**File:** `graph.py` lines 44–53  
Both nodes only read from `state` inputs. They write to disjoint state keys (`internal_links` vs. `style_profile`) and could be parallelised using a fan-out / fan-in pattern, saving wall-clock time equal to whichever finishes first.

#### P-2 · Research context is hard-truncated to 500 characters per source
**Files:** `researcher.py` line 53; `planner.py` line 46  
```python
"content": item.get('content', '')[:500]
```
500 characters is typically 80–90 words — barely one paragraph. The planner receives almost no real content, making source-to-section assignment speculative. The writer then receives the same truncated context. For long articles this means citations are often weakly supported.

#### P-3 · Two sequential LLM calls in planner (outline + budget) could be a single structured call
**File:** `nodes/planner.py` lines 50–239  
The planner makes two separate round-trips to the LLM: one for the outline and one for budget allocation. These could be merged into a single call with a combined schema (`OutlineWithBudgets`), saving one API call per run.

#### P-4 · Query generation is repeated on every deep research loop without incorporating previous findings
**File:** `nodes/deep_research.py` lines 14–43  
`generate_query_node` receives only `topic` and `loop_count`. It does not receive the reflection feedback (`feedback` field from `ReflectionOutput`) explaining what information is missing. Loop 2+ queries will be superficially different from loop 1 but will not be targeted at the actual gaps.

---

### 3.4 Maintainability Issues

#### M-1 · Magic numbers and constants scattered across files
Multiple files contain hardcoded constants with no central configuration:
- Loop limit: `> 3` (`graph.py:85`)
- Source content limits: `[:500]`, `[:1500]`, `[:2000]` (researcher, deep_research)
- Query counts: `[:2]` for web search (researcher, deep_research)
- Section count ranges by blog size (planner)
- Word budget tolerances: `* 0.9` and `* 1.1` (writer, critic)

#### M-2 · `print()` used for debugging instead of the structured logger
**Files:** `researcher.py`, `deep_research.py`, `planner.py`, `writer.py`  
~30 `print()` calls are scattered across node files. `llm_logger` exists and is used for LLM call logging, but node-level debug output bypasses it entirely, making log aggregation in production impossible.

#### M-3 · Prompts are defined as inline string templates, not versioned or externalized
All prompts are hardcoded inside function bodies. There is no mechanism to A/B test prompt versions, roll back a bad prompt, or reuse common prompt fragments across nodes.

#### M-4 · `AgentState` mixes inputs, intermediate results, and outputs in a flat TypedDict
The state has no logical separation between fields that are set at invocation, fields that are accumulated during execution, and fields that represent final output. This makes it hard to reason about which node can safely write which field, and creates risk of accidental overwrites.

#### M-5 · No integration or end-to-end tests for the graph
**Directory:** `backend/tests/`  
The test suite does not include graph-level tests that exercise the full agent pipeline, even with mocked external services. Bugs in routing logic, state transitions, and Command navigation cannot be caught before deployment.

---

## 4. Improvement Plan

### P0 — Bug Fixes (Ship Now)

These are correctness bugs with no acceptable workaround.

---

#### P0-1 · Fix parallel node `Send()` payload to include execution context

Pass all runtime settings through the `Send()` payload so parallel nodes can honour user preferences.

```python
# graph.py — proposed
def route_to_research_tasks(state: AgentState):
    queries = state.get("generated_queries", [])
    sources = state.get("research_sources", ["web", "internal"])
    
    # Shared execution context forwarded to every parallel node
    exec_ctx = {
        "model_provider": state.get("model_provider", "anthropic"),
        "model_name": state.get("model_name", "claude-haiku-4-5"),
        "use_local": state.get("use_local", False),
        "loop_count": state.get("research_loop_count", 0),
        "reflection_feedback": state.get("reflection_feedback", ""),
    }
    tasks = []
    if "web" in sources:
        tasks.extend([Send("deep_web_research", {"query": q, **exec_ctx}) for q in queries])
    if "social" in sources and queries:
        tasks.append(Send("deep_social_research", {"query": queries[0], **exec_ctx}))
    if "academic" in sources and queries:
        tasks.append(Send("deep_academic_research", {"query": queries[0], **exec_ctx}))
    return tasks
```

Update all three parallel node signatures to accept and use these fields.

---

#### P0-2 · Fix deep research loop boundary condition

Change `> 3` to `>= 3` so the loop cap is inclusive and the maximum number of iterations is exactly 3.

```python
# graph.py — proposed
def route_after_reflection(state: AgentState):
    if state.get("is_sufficient") or state.get("research_loop_count", 0) >= 3:
        return "deep_finalize"
    return "deep_generate_query"
```

---

#### P0-3 · Add a boolean decision to the critic

Introduce a `passed: bool` field to `CritiqueResult` so the critic can signal that no rewrite is needed, saving an LLM call for already-acceptable drafts.

```python
# nodes/critic.py — proposed
class CritiqueResult(BaseModel):
    passed: bool = Field(
        description="True if the draft meets all quality criteria and no rewrite is needed."
    )
    feedback: str = Field(
        description="Specific, actionable improvement suggestions. "
                    "Leave empty string if passed=True."
    )

# ... in critic_node, after receiving result:
if result.passed:
    return Command(
        update={"critique_feedback": feedback_dict},
        goto="visuals"
    )
else:
    retries_dict[section_id] = current_retries + 1
    return Command(
        update={"critique_feedback": feedback_dict, "section_retries": retries_dict},
        goto="writer"
    )
```

---

#### P0-4 · Fix source-type detection in `finalize_answer_node`

Replace fragile URL-sniffing with an explicit `source_type` field carried through the `ResearchResult` model.

```python
# state.py — proposed: add source_type to ResearchResult
class ResearchResult(BaseModel):
    query: str
    summary: str
    citations: List[Citation]
    source_type: str = "web"  # "web" | "social" | "academic"
```

Each research node sets `source_type` explicitly rather than leaving it to `finalize_answer_node` to infer.

---

#### P0-5 · Pass reflection feedback to `generate_query_node`

Store the reflection's textual feedback in state so subsequent query-generation loops target actual gaps.

```python
# state.py — add field
reflection_feedback: str  # Populated by reflection_node, consumed by generate_query_node

# nodes/deep_research.py — reflection_node
return {
    "is_sufficient": result.is_sufficient,
    "reflection_feedback": result.feedback,
}

# nodes/deep_research.py — generate_query_node prompt
prompt = f"""
Topic: {topic}
Loop: {loop_count}
Missing information identified in last reflection:
{state.get("reflection_feedback", "None — this is the first loop.")}

Generate 3 targeted queries that fill the identified gaps.
"""
```

---

### P1 — Reliability & Correctness

---

#### P1-1 · Add timeouts to all external API calls

Wrap every `asyncio.to_thread` call in `asyncio.wait_for` to cap per-call latency and allow graceful degradation.

```python
# Proposed helper in services/base.py (or inline where needed)
import asyncio

FIRECRAWL_TIMEOUT_SEC = 20
ARXIV_TIMEOUT_SEC = 15
PINECONE_TIMEOUT_SEC = 10

async def call_with_timeout(coro, timeout: float, fallback=None):
    try:
        return await asyncio.wait_for(coro, timeout=timeout)
    except asyncio.TimeoutError:
        logger.warning("External call timed out after %.1fs", timeout)
        return fallback if fallback is not None else []
    except Exception as e:
        logger.error("External call failed: %s", e)
        return fallback if fallback is not None else []

# Usage in researcher.py
web_results = await call_with_timeout(
    asyncio.to_thread(firecrawl_service.search, clean_q, limit=3),
    timeout=FIRECRAWL_TIMEOUT_SEC,
    fallback={"data": []}
)
```

---

#### P1-2 · Deduplicate research results by URL

Add a deduplication step before `research_data` is finalised in both the standard researcher and `finalize_answer_node`.

```python
# Proposed utility (utils/research.py)
def deduplicate_results(results: list[dict]) -> list[dict]:
    """Remove duplicate entries sharing the same URL, keeping the first occurrence."""
    seen_urls: set[str] = set()
    unique = []
    for item in results:
        url = item.get("url", "")
        if url and url not in seen_urls:
            seen_urls.add(url)
            unique.append(item)
        elif not url:  # Always keep items without a URL (e.g., internal KB)
            unique.append(item)
    return unique
```

---

#### P1-3 · Re-run budget allocation after section truncation

Move the budget allocation call *after* any outline truncation so the final `section_word_budgets` always matches the actual `outline` list.

```python
# nodes/planner.py — proposed ordering
outline = [section.model_dump() for section in result.sections]

# Enforce section count FIRST
if len(outline) > max_sections:
    outline = outline[:max_sections]

# THEN allocate budgets against the final outline
section_word_budgets = await _allocate_budgets(llm, outline, target_word_count, blog_size)
```

---

#### P1-4 · Add a `deep_internal_research` node to the fan-out

Add a new `deep_internal_research` node that is dispatched in parallel with the other deep research nodes, removing the sequential internal search at the end of `finalize_answer_node`.

```python
# graph.py — add to deep research fan-out
builder.add_node("deep_internal_research", internal_research_node)

def route_to_research_tasks(state: AgentState):
    ...
    if "internal" in sources and bins:
        tasks.extend([Send("deep_internal_research", {"query": q, **exec_ctx}) for q in queries[:2]])
    return tasks

builder.add_edge("deep_internal_research", "deep_reflection")
```

---

#### P1-5 · Add per-user in-flight run guard

Check for an existing `RUNNING` thread for the user before creating a new one and return a `409 Conflict` if one exists.

```python
# api/agent.py — proposed
existing = await db.execute(
    select(Thread).where(Thread.user_id == current_user.id, Thread.status == "RUNNING")
)
if existing.scalar_one_or_none():
    raise HTTPException(status_code=409, detail="A generation run is already in progress.")
```

---

### P2 — Performance & Cost

---

#### P2-1 · Parallelise `internal_indexer` and `style_analyst`

Replace the sequential edge with a fan-out/fan-in pattern. Both nodes only read initial inputs and write to disjoint state keys.

```python
# graph.py — proposed
builder.add_edge(START, "internal_indexer")
builder.add_edge(START, "style_analyst")          # Run concurrently
builder.add_edge("internal_indexer", "pre_research_sync")
builder.add_edge("style_analyst", "pre_research_sync")
# pre_research_sync is a no-op passthrough node that both edges converge on
```

Alternatively, combine both into a single `context_builder` node that runs the two operations with `asyncio.gather` internally — simpler to implement and avoids adding a new graph node.

```python
# nodes/context_builder.py — proposed
async def context_builder_node(state: AgentState):
    indexer_task = asyncio.create_task(internal_indexer_node(state))
    style_task = asyncio.create_task(style_analyst_node(state))
    indexer_result, style_result = await asyncio.gather(indexer_task, style_task)
    return {**indexer_result, **style_result}
```

---

#### P2-2 · Increase research context depth

Raise the per-source content truncation limit from 500 to 2,000 characters for sources that will be assigned to sections, while keeping a tighter 500-character limit for sources in the planning context (which is already large).

```python
# In researcher.py / finalize_answer_node
PLANNING_CONTENT_LIMIT = 500    # Used in planner context string
WRITING_CONTENT_LIMIT = 2000    # Used in writer context string

# Store full content in research_data; truncate at usage site
"content": content[:WRITING_CONTENT_LIMIT]
```

---

#### P2-3 · Merge the two planner LLM calls into one

Define a combined Pydantic schema and generate outline + budgets in a single structured call.

```python
# nodes/planner.py — proposed
class SectionWithBudget(BaseModel):
    id: str
    title: str
    intent: str
    source_ids: List[str]
    word_budget: int = Field(description="Target word count for this section")
    content: Optional[str] = None

class OutlineWithBudgets(BaseModel):
    sections: List[SectionWithBudget]
    total_words: int = Field(description="Sum of all section word budgets")
    reasoning: str
```

---

#### P2-4 · Cache style profiles between runs

When a `profile_id` is supplied, the style DNA is already stored in the database. Skip the `style_analyst` LLM call and return the cached profile directly.

```python
# nodes/style_analyst.py — proposed early-return
profile_id = state.get("profile_id")
if profile_id:
    profile = await load_profile_from_db(profile_id)
    if profile:
        return {"style_profile": profile.style_dna}
# ... proceed with on-the-fly extraction
```

---

### P3 — Observability & Maintainability

---

#### P3-1 · Replace all `print()` calls with structured logging

Use Python's standard `logging` module (or extend `llm_logger`) with node-scoped loggers. This enables log aggregation, level filtering, and JSON output in production.

```python
# Before
print(f"Generated Queries: {search_queries}")

# After
import logging
logger = logging.getLogger(__name__)
logger.debug("Generated queries", extra={"queries": search_queries, "node": "researcher"})
```

Adopt a consistent log schema:
```json
{
  "timestamp": "...",
  "level": "DEBUG",
  "node": "researcher",
  "thread_id": "...",
  "event": "queries_generated",
  "data": { "queries": [...] }
}
```

---

#### P3-2 · Centralise constants in a configuration module

Create `app/agent/config.py` to replace scattered magic numbers.

```python
# app/agent/config.py — proposed
from dataclasses import dataclass, field

@dataclass(frozen=True)
class ResearchConfig:
    web_queries_standard: int = 2
    social_queries_standard: int = 1
    academic_queries_standard: int = 1
    content_limit_planning: int = 500
    content_limit_writing: int = 2000
    deep_research_max_loops: int = 3

@dataclass(frozen=True)
class WritingConfig:
    word_budget_tolerance: float = 0.10  # ±10%

@dataclass(frozen=True)
class BlogSizeConfig:
    small:  dict = field(default_factory=lambda: {"word_count": 2500,  "min_sections": 3,  "max_sections": 5})
    medium: dict = field(default_factory=lambda: {"word_count": 5500,  "min_sections": 6,  "max_sections": 8})
    large:  dict = field(default_factory=lambda: {"word_count": 10000, "min_sections": 10, "max_sections": 15})

RESEARCH_CONFIG = ResearchConfig()
WRITING_CONFIG = WritingConfig()
BLOG_SIZES = BlogSizeConfig()
```

---

#### P3-3 · Externalise and version prompts

Move all prompts to a `app/agent/prompts/` directory as `.yaml` files or structured Python constants with version tags. This enables:
- Prompt A/B testing without code changes
- Rollback of a bad prompt without a full redeploy
- Diff-friendly version history

```yaml
# app/agent/prompts/writer_v1.yaml
version: "1"
template: |
  Write the following section for a blog post.
  ...
```

```python
# nodes/writer.py
from app.agent.prompts import load_prompt
prompt = load_prompt("writer", version="1")
```

---

#### P3-4 · Split `AgentState` into logical sub-states

Introduce nested typed dataclasses grouped by concern. This prevents accidental writes across concerns and makes the type surface easier to navigate.

```python
# state.py — proposed structure
class ExecutionConfig(TypedDict):
    user_id: str
    model_provider: str
    model_name: str
    use_local: bool

class ResearchConfig(TypedDict):
    topic: str
    target_audience: str
    research_sources: List[str]
    research_guidelines: List[str]
    deep_research_mode: bool
    selected_bins: List[str]
    extra_context: str
    blog_size: str
    target_word_count: int

class ResearchOutput(TypedDict):
    research_data: List[Dict[str, Any]]
    deep_research_results: Annotated[List[ResearchResult], operator.add]
    research_loop_count: int
    is_sufficient: bool
    generated_queries: List[str]
    reflection_feedback: str
    internal_links: List[Dict[str, str]]
    style_profile: Dict[str, Any]

class DraftingState(TypedDict):
    outline: List[Section]
    section_word_budgets: Dict[str, int]
    current_section_index: int
    draft_sections: Dict[str, str]
    critique_feedback: Dict[str, str]
    section_retries: Dict[str, int]

class AgentState(ExecutionConfig, ResearchConfig, ResearchOutput, DraftingState):
    tone_urls: List[str]
    target_domain: str
    final_content: str
```

---

#### P3-5 · Add graph-level integration tests with mocked services

Create a `backend/tests/test_graph.py` file that exercises the full graph with mocked external calls.

```python
# backend/tests/test_graph.py — proposed skeleton
import pytest
from unittest.mock import AsyncMock, patch
from app.agent.graph import build_graph

@pytest.mark.asyncio
async def test_standard_research_path_completes():
    """Full graph run with standard research mode and mocked services."""
    graph = build_graph().compile(checkpointer=MemorySaver())
    initial_state = {
        "topic": "Test Topic",
        "deep_research_mode": False,
        ...
    }
    with patch("app.services.firecrawl_service.search", return_value=mock_firecrawl_response):
        result = await graph.ainvoke(initial_state, config={"thread_id": "test-1"})
    assert result["final_content"] != ""

@pytest.mark.asyncio
async def test_deep_research_loop_does_not_exceed_max():
    """Ensure deep research terminates after MAX_LOOPS even if never sufficient."""
    ...
```

---

### P4 — Capability Expansions

These are future features that require the above reliability work as a foundation.

---

#### P4-1 · Research quality scoring

After research aggregation, have a lightweight LLM call score each source on `[relevance, credibility, freshness]`. Low-scoring sources are filtered before passing to the planner, improving outline quality without increasing token usage in later stages.

---

#### P4-2 · Draft versioning & rollback

Store each section's draft history (before and after critic rewrites) in the state and expose a "revert to previous draft" action in the frontend `OutlineEditor`. This eliminates the frustration of a good first draft being degraded by an unhelpful rewrite.

---

#### P4-3 · Adaptive blog size based on research volume

After research completes, measure the total information volume. If research data is sparse relative to the requested size, downgrade `blog_size` automatically (e.g., `large` → `medium`) and notify the user, rather than writing thin sections to pad the target word count.

---

#### P4-4 · Streaming progress within long-running nodes

The SSE stream currently emits events at the node boundary (`step_start` / `step_complete`). For long nodes (writer producing 1,500-word sections), there can be 30–60 seconds of silence. Add streaming output from within the writer node using `llm.astream()` and forward partial tokens through the SSE channel.

---

#### P4-5 · Prompt-level A/B testing framework

Instrument the prompt loader (P3-3) to randomly select between prompt versions for a configurable percentage of runs. Log which version was used alongside quality metrics (word count accuracy, critic pass rate, user edit rate) to drive data-driven prompt improvements.

---

#### P4-6 · Multi-language support

Extend `AgentState` with an `output_language` field. Propagate it to the style analyst (to analyse reference content in the target language), planner, writer, and critic prompts. This allows non-English blogs without requiring the user to write their own language-specific guidelines.

---

## 5. Proposed Target Architecture

```
START
  │
  ▼
context_builder  ◄── (merged: internal_indexer + style_analyst, parallel)
  │
  ├─── deep_research_mode=True ──► deep_generate_query
  │                                      │
  │              ┌────────┬──────────────┼──────────────┐
  │              ▼        ▼              ▼               ▼
  │       deep_web  deep_social  deep_academic  deep_internal
  │              └────────┴──────────────┴───────────────┘
  │                                      │
  │                               deep_reflection
  │                               ┌──────┴──────────────┐
  │                          sufficient?            loop < MAX
  │                               │                     │
  │                          deep_finalize    deep_generate_query
  │                               │
  └─── deep_research_mode=False ──► researcher (parallel, all sources)
                                         │
                                         ▼ (both paths rejoin here)
                                      planner   ◄── (single LLM call: outline + budgets)
                                         │
                                   human_approval  ◄── [INTERRUPT]
                                         │
                              ┌──────────▼───────────┐
                              │   (section loop)      │
                              │   writer              │
                              │     │  ▼              │
                              │   critic ──pass──► visuals
                              │     │  fail           │
                              │   writer (retry)      │
                              └──────────────────────┘
                                         │
                                      publisher
                                         │
                                        END
```

**Key changes from current architecture:**

| Change | Benefit |
|--------|---------|
| `context_builder` (merged node) | Parallel style + indexing; single graph edge |
| `deep_internal_research` in fan-out | Internal KB searched in parallel, not sequentially |
| Critic `passed` field | Saves 1 writer LLM call per section when first draft is good (~20–30% of cases) |
| Merged planner call | Saves 1 LLM call per run |
| `reflection_feedback` in state | Targeted loop 2+ queries; faster convergence |
| `exec_ctx` in `Send()` payloads | Parallel nodes honour model/provider preferences |

---

## 6. Migration Checklist

Items are ordered by dependency: complete P0 bugs before P1, P1 before P2, etc.

### P0 — Bug Fixes
- [ ] **P0-1** Pass `exec_ctx` (model, provider, use_local, loop_count, reflection_feedback) through `Send()` payloads to parallel research nodes
- [ ] **P0-2** Fix deep research loop boundary: `> 3` → `>= 3`
- [ ] **P0-3** Add `passed: bool` to `CritiqueResult`; route to `visuals` on pass, `writer` on fail
- [ ] **P0-4** Add `source_type` field to `ResearchResult`; set it in each research node explicitly
- [ ] **P0-5** Store `reflection_feedback` in state; pass to `generate_query_node` on subsequent loops

### P1 — Reliability & Correctness
- [ ] **P1-1** Wrap all `asyncio.to_thread` external calls in `asyncio.wait_for` with per-service timeouts
- [ ] **P1-2** Add URL-based deduplication to `research_data` after aggregation
- [ ] **P1-3** Move outline truncation before budget allocation in `planner_node`
- [ ] **P1-4** Add `deep_internal_research` node to the deep research fan-out; remove sequential `_run_internal_search` from `finalize_answer_node`
- [ ] **P1-5** Add per-user in-flight run guard in the `/agent/stream` endpoint (return 409 if a run is already active)

### P2 — Performance & Cost
- [ ] **P2-1** Merge `internal_indexer` + `style_analyst` into a single `context_builder` node using `asyncio.gather`
- [ ] **P2-2** Raise writing-context truncation limit from 500 → 2,000 characters
- [ ] **P2-3** Merge planner's two LLM calls into one using `OutlineWithBudgets` schema
- [ ] **P2-4** Add early-return in `style_analyst` when `profile_id` is supplied and profile is cached

### P3 — Observability & Maintainability
- [ ] **P3-1** Replace all `print()` calls with `logging.getLogger(__name__)` and consistent log schema
- [ ] **P3-2** Create `app/agent/config.py` with typed dataclasses for all tunable constants
- [ ] **P3-3** Move prompt strings to `app/agent/prompts/` YAML files with version numbers
- [ ] **P3-4** Refactor `AgentState` into logical sub-states (`ExecutionConfig`, `ResearchConfig`, etc.)
- [ ] **P3-5** Add `backend/tests/test_graph.py` integration tests with mocked external services

### P4 — Capability Expansions
- [ ] **P4-1** Research quality scoring node (post-aggregation filter)
- [ ] **P4-2** Draft versioning and rollback in state + frontend
- [ ] **P4-3** Adaptive blog size downgrade when research volume is sparse
- [ ] **P4-4** SSE token streaming within writer node using `llm.astream()`
- [ ] **P4-5** Prompt A/B testing framework tied to quality metrics
- [ ] **P4-6** Multi-language support via `output_language` state field

---

*This document was generated from a code review of the `backend/app/agent/` module. All file references and line numbers are accurate against the codebase at time of writing.*
