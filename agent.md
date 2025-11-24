# Project Context: Content Strategist Agent

## 1. Project Overview
**Goal:** Build an enterprise-grade "Content Strategist" agent, not just a writer. The system mimics a human editorial team to produce authoritative, SEO-optimized articles using internal data (RAG) while maintaining data privacy.

**Core Value Proposition:** "Turn your internal documents into authoritative, SEO-optimized articles without your data ever leaving your infrastructure."

## 2. Technical Stack & Decisions

### Core Architecture
- **Backend:** FastAPI (Python)
- **Frontend:** React 19 + Vite + Tailwind CSS (Shadcn UI)
- **Orchestration:** LangGraph (for stateful, multi-step agent workflows)
- **State Persistence:** PostgreSQL (via `langgraph-checkpoint-postgres`) - Required for "Human-in-the-Loop" interrupts.
- **Database:** PostgreSQL + SQLAlchemy/SQLModel (for Users, Knowledge Bins, Documents, Threads, Profiles).
- **Authentication:** JWT (JSON Web Tokens) with OAuth2PasswordBearer.
- **Observability:** Server-Sent Events (SSE) for real-time agent streaming ("Glass Box").

### AI & Models
- **Cloud Model (Default):** GPT-4o (Target/Placeholder for high-end reasoning)
- **Local Model (Default):** Qwen 2.5 / Llama 3 (Target/Placeholder for local execution)
- **Additional Support:** Must support Llama series models via Ollama.
- **Model Factory:** Dynamic switching between Cloud and Local models based on user preference.
- **Embedding Models:**
  - *Cloud:* OpenAI `text-embedding-3-small` (1536 dim)
  - *Local:* `nomic-embed-text` or `bge-m3` (via Ollama/HuggingFace)

### Data Infrastructure (RAG)
- **Vector Database:** Pinecone (Serverless)
- **PDF Parsing:** PyMuPDF (`fitz`) - Chosen for speed and metadata handling.
- **Chunking Strategy:** Recursive Character Splitter (1000 tokens size, 200 tokens overlap).
- **Search/Scraping:** Firecrawl (API Key available) for Web, Reddit, Arxiv.

## 3. Key Features & Requirements

### 🔒 Privacy-First Infrastructure
- **Hybrid Execution:** Sensitive data processed locally (Ollama), general reasoning via Cloud.
- **Knowledge Bins:** Secure, isolated containers for user documents (PDFs, DOCX, TXT), managed via PostgreSQL and Pinecone namespaces.
- **Local LLM Toggle:** User can switch to fully local execution (Ollama) for maximum privacy.
- **Data Sovereignty:** Internal documents processed in "Local Mode" never leave the user's infrastructure (requires local embeddings).

### 👁️ "Glass Box" Observability
- **Real-time Streaming:** Users see the agent's thought process via SSE (Server-Sent Events).
- **Visual Feedback:** UI shows active nodes (Research -> Plan -> Write) and live logs.
- **No Black Boxes:** Every step, tool call, and decision is visible to the user.

### 🧬 Style DNA & Profiles
- **Style DNA Extraction:** Analyzes user-provided URLs to extract a "Style Profile" (sentence variance, vocabulary, formatting).
- **User Profiles:** Users can save "Voice Profiles" (e.g., "Technical Blog", "Marketing Copy") to reuse Style DNA without re-analyzing URLs every time.
- **Brand Consistency:** Ensures output matches the selected voice profile.

### 🛡️ The "Reflexion" Quality Loop
- **Critic Agent:** Reviews every draft against style rules and negative constraints.
- **Loop:** Draft -> Critic -> Fail? -> Rewrite -> Pass? -> Visuals.

### 📚 Knowledge Management ("The Librarian")
- **"Write Once, Cite Forever":** Uploaded documents are processed once and stored.
- **Bin Management:** Create, Rename, Delete Bins. Upload/Delete files.
- **Status Tracking:** Real-time status of documents (Uploaded -> Parsing -> Embedding -> Ready -> Failed).
- **Smart Data Handling:** Auto-extraction of text and tables.

### 🔗 Smart Linking & Research
- **Internal Indexer:** "Lazy scrape" of user's sitemap to build a lightweight index for internal linking.
- **Multi-Source Research:** User selects sources:
  - **Web:** General Google search (Firecrawl).
  - **Social:** Reddit/Quora (Firecrawl).
  - **Academic:** Arxiv/Scholar.
  - **Internal:** Selected Knowledge Bins.

## 4. Workflows (LangGraph)

### Pipeline A: The Librarian (Ingestion)
1.  **User Interaction:** User creates a Bin and uploads files (PDF, DOCX, TXT).
2.  **Record:** Create `Document` record in PostgreSQL (Status: Uploaded).
3.  **Processing (Background Task):**
    - **Text Extraction:** Parse binary files to clean text.
    - **Chunking:** Split into 1000-token chunks with 200-token overlap.
    - **Embedding:** Convert chunks to vectors (Cloud or Local).
    - **Upsert:** Store in Pinecone with Namespace ID (`{user_id}_{bin_id}`).
4.  **Finalize:** Update `Document` status to `Ready`.

### Pipeline B: The Editor (Generation)
1.  **Configuration:** User selects Topic, Style Profile, Target Domain, and Knowledge Bins.
2.  **Stream Start:** Agent execution begins, streaming events via SSE.
3.  **Phase 1: Strategy & Intelligence**
    - **Node A (Style Analyst):** Loads selected Style Profile (or scrapes if new).
    - **Node B (Internal Indexer):** Scrapes sitemap for internal links.
    - **Node C (Deep Researcher):** Parallel search on Web, Social, Academic, and Internal Bins.
4.  **Phase 2: The Blueprint (HITL)**
    - **Planner:** Synthesizes research into a JSON Outline with Intents and Source IDs.
    - **Interrupt:** Graph pauses. UI shows Drag-and-Drop Outline Editor.
    - **Resume:** User approves/edits outline and clicks "Generate".
5.  **Phase 3: The Production Line (Reflexion)**
    - **Writer:** Drafts section-by-section using Style Profile and Smart Linking.
    - **Citation:** Strictly cites sources using `assigned_source_ids`.
    - **Critic:** Reviews draft. If FAIL, feedback loop (max 2 retries). If PASS, proceed.
    - **Visuals:** Generates Mermaid.js code or Image Prompts.
6.  **Phase 4: Assembly**
    - **Publisher:** Compiles sections, appends References.
    - **Output:** Final Markdown/HTML ready for export.

## 5. Current Gaps (as of Nov 24, 2025)
- **Bin Management:** Frontend missing edit/delete/status features. Backend namespace mismatch.
- **Profiles:** No persistence for Style DNA.
- **Auth:** Agent endpoints bypass auth.
- **Local Mode:** Embeddings still use Cloud.
- **History:** No thread tracking or export options.

## 6. Bugs & Issues (Tracked)

### Resolved
- **Missing `internal_index` Table:** `UndefinedTableError` encountered. Fixed by adding Alembic migration `b8f8c2ac5f5d`.
- **Sitemap Index Parsing:** `InternalIndexerNode` failed to extract links from `evolutyz.com` because it only looked for `<url>` tags and ignored `<sitemap>` tags (Sitemap Index).
  - *Fix:* Updated `internal_indexer.py` to recursively fetch child sitemaps when a Sitemap Index is detected.
  - *Verification:* Verified with `test_sitemap.py`. Runtime verification pending.
- **Deep Research Missing Social & Academic:** Deep Research mode only supported web search, missing social and academic sources available in regular mode.
  - *Fix:* Implemented `social_research_node` and `academic_research_node` for deep research with parallel execution.
  - *Implementation:* Added conditional routing based on `research_sources` selection. Source categorization logic detects and labels sources as web/social/academic.
  - *Verification:* All unit tests pass (3/3). Graph builds successfully. See `DEEP_RESEARCH_INTEGRATION.md` for details.
  - *Date:* Nov 24, 2025

### Active / Monitoring
- **Server Restart Requirement:** Code changes to `internal_indexer.py` required a manual server restart to take effect. Ensure server is restarted after applying fixes.

## 7. Recent Enhancements (Nov 24, 2025)

### Deep Research Multi-Source Integration
**What Changed:**
- Added Social Research (Reddit/Twitter) and Academic Research (Arxiv) to Deep Research mode
- Implemented parallel execution of web, social, and academic searches
- Added smart source categorization in finalization node
- Updated graph routing to conditionally spawn research tasks based on `research_sources`

**Technical Details:**
- New Nodes: `social_research_node`, `academic_research_node`
- Graph Update: Conditional fan-out using LangGraph `Send()` based on selected sources
- Source Detection: URL pattern matching (reddit.com/x.com → social, arxiv.org → academic)
- Source IDs: Sequential per type (e.g., social_1_1, acad_2_1, web_3_1)

**Usage:**
```json
{
  "deep_research_mode": true,
  "research_sources": ["web", "social", "academic", "internal"]
}
```

**Benefits:**
- Parity with regular research mode (now supports all 4 source types)
- Better quality through diverse sources (social discussions + academic papers + web content)
- Maintained rate limiting (1 query for social/academic, 3 for web per loop)
- Proper source attribution for citations

**Files Modified:**
- `backend/app/agent/nodes/deep_research.py`: Added 2 new nodes, improved finalization
- `backend/app/agent/graph.py`: Updated routing and node registration
- `backend/app/services/arxiv_service.py`: Fixed HTTP→HTTPS redirect

**Testing:**
- Unit tests: `backend/test_deep_research_integration.py` (3/3 passing)
- Import verification: ✓ Successful
- Graph build: ✓ Successful

