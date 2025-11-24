# Content Strategist Agent - Technical Documentation

This document details the internal workings, input parameters, and workflow of the Content Strategist Agent.

## 1. Input Parameters

The agent is triggered via the `POST /api/v1/agent/stream` endpoint. It accepts a JSON payload defined by the `RunRequest` schema.

### Core Inputs
| Field | Type | Description |
| :--- | :--- | :--- |
| `topic` | `string` | **Required.** The main subject or title of the article to be generated. |
| `target_audience` | `string` | Who the article is written for (e.g., "CTOs", "Beginner Python Developers"). |
| `target_domain` | `string` | The domain where the article will be published (e.g., `https://example.com`). Used for generating relative internal links. |
| `extra_context` | `string` | Additional background information, specific requirements, or raw notes to guide the agent. |

### Research Configuration
| Field | Type | Description |
| :--- | :--- | :--- |
| `research_sources` | `List[str]` | Sources to query. Options: `['web', 'social', 'academic', 'internal']`. |
| `selected_bins` | `List[str]` | List of Knowledge Bin IDs (UUIDs) to search if `internal` source is selected. |
| `deep_research_mode` | `boolean` | If `true`, enables the iterative "Deep Research" loop (slower, higher quality). If `false`, runs a single parallel search step. |
| `research_guidelines` | `List[str]` | Specific questions or angles the researcher must investigate. |

### Style & Voice
| Field | Type | Description |
| :--- | :--- | :--- |
| `profile_id` | `UUID` | ID of a saved Style Profile to apply. |
| `tone_urls` | `List[str]` | List of URLs to analyze on-the-fly if no profile is selected. |
| `style_profile` | `Dict` | (Advanced) Direct injection of a style profile object. |

### Execution Settings
| Field | Type | Description |
| :--- | :--- | :--- |
| `use_local` | `boolean` | If `true`, forces the agent to use the configured Local LLM (e.g., Ollama) for all reasoning steps. |
| `model_provider` | `string` | Provider for the LLM (e.g., "openai", "anthropic", "ollama"). |
| `model_name` | `string` | Specific model identifier (e.g., "gpt-4o", "llama3"). |

---

## 2. Agent Workflow (The "Graph")

The agent is orchestrated using **LangGraph**, a stateful graph-based framework. The workflow consists of sequential and conditional nodes.

### Phase 1: Context & Intelligence
1.  **Internal Indexer (`internal_indexer`)**:
    *   Scrapes the `target_domain` sitemap (if available).
    *   Builds a lightweight index of existing blog posts to enable smart internal linking later.
2.  **Style Analyst (`style_analyst`)**:
    *   Fetches content from `tone_urls` or loads the `profile_id`.
    *   Extracts "Style DNA": sentence length variance, vocabulary complexity, formatting patterns, and tone.
3.  **Research Router**:
    *   Decides whether to enter the **Standard Research** or **Deep Research** path based on `deep_research_mode`.

### Phase 2: Research
#### Path A: Standard Research (`researcher`)
*   Executes parallel queries to all selected sources (Firecrawl for Web/Social, Pinecone for Internal).
*   Aggregates results into a single context block.

#### Path B: Deep Research (Iterative Loop)
1.  **Generate Queries (`deep_generate_query`)**: Analyzes the topic and generates specific search queries.
2.  **Web Research (`deep_web_research`)**: Executes searches in parallel.
3.  **Reflection (`deep_reflection`)**: The agent reads the gathered results and asks: *"Do I have enough information to write a comprehensive article?"*
4.  **Loop**:
    *   **No:** Generates *new* queries based on missing information and repeats.
    *   **Yes:** Proceed to finalization.
5.  **Finalize (`deep_finalize`)**: Synthesizes all iterations into a structured research summary.

### Phase 3: Planning (`planner`)
*   Takes the Research Summary and Style DNA.
*   Generates a **Structured Outline** (JSON).
*   Assigns specific **Source IDs** to each section to ensure citations are accurate.
*   **INTERRUPT (`human_approval`)**: The graph pauses here. The state is saved to the database. The user must review/edit the outline in the UI and click "Generate" to resume.

### Phase 4: Production (The "Reflexion" Loop)
The agent iterates through the outline section-by-section.

1.  **Writer (`writer`)**:
    *   Drafts the current section.
    *   Injects internal links from the `internal_indexer`.
    *   Cites sources from the Research Summary.
    *   Mimics the Style DNA.
2.  **Critic (`critic`)**:
    *   Reviews the draft against the Style Guide and negative constraints.
    *   **Pass:** Moves to Visuals.
    *   **Fail:** Sends feedback back to the **Writer** for a retry (max 2 retries).
3.  **Visuals (`visuals`)**:
    *   Analyzes the text to see if a diagram is needed.
    *   Generates **Mermaid.js** code for flowcharts or processes if necessary.
4.  **Loop**: Moves to the next section until the article is complete.

### Phase 5: Assembly (`publisher`)
*   Combines all sections.
*   Generates a "References" section listing all used citations.
*   Produces the final Markdown output.

---

## 3. State Management

The agent maintains a persistent state object (`AgentState`) throughout the lifecycle:

```python
class AgentState(TypedDict):
    # Inputs
    topic: str
    target_domain: str
    target_audience: str
    
    # Research Data
    research_data: List[Dict]      # Raw search results
    internal_links: List[Dict]     # Sitemap data
    
    # Style
    style_profile: Dict            # Extracted voice guidelines
    
    # Planning
    outline: List[Dict]            # The approved outline
    
    # Drafting
    current_section_index: int     # Pointer to current section
    draft_sections: Dict[str, str] # Map of Section ID -> Content
    critique_feedback: Dict        # Feedback from Critic
    section_retries: Dict          # Retry counters
    
    # Output
    final_article: str             # Completed text
```

This state is stored in PostgreSQL after every step, allowing the agent to be paused, resumed, or debugged at any point.
