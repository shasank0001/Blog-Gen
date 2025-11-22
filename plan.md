# Implementation Plan: Content Strategist

## Phase 1: Foundation & Infrastructure (Backend)
**Goal:** Establish the API server, database connections, and basic RAG capabilities.

- [x] **Project Setup**
    - Initialize FastAPI project structure (`app/main.py`, `app/api`, `app/services`).
    - Configure environment variables (`.env`) for OpenAI, Firecrawl, Pinecone, and Postgres.
    - Set up Docker Compose for local PostgreSQL (for LangGraph persistence).
- [x] **Database & Vector Store**
    - Implement `PineconeService`:
        - Initialize with `ServerlessSpec` (AWS/us-east-1).
        - Create index `content-strategist-index` (1536 dim) if not exists.
    - Implement `PostgresService`:
        - Setup connection pool for LangGraph checkpointer.
- [x] **RAG Pipeline ("The Librarian")**
    - Implement `PDFParser` using `PyMuPDF` (`fitz`):
        - Extract text and table structures.
        - Extract metadata (page numbers).
    - Implement `ChunkingService`:
        - Use `RecursiveCharacterTextSplitter` (1024 chunk / 200 overlap).
    - Create `IngestionRouter` (`POST /api/v1/upload`):
        - Flow: Upload -> Parse -> Chunk -> Embed (OpenAI) -> Upsert to Pinecone (Namespace: `{user_id}_{bin_id}`).
- [x] **Search Services**
    - Implement `FirecrawlService` (using `firecrawl-py`):
        - Method `search(query)`: Use v2 API with `scrapeOptions` for markdown.
        - Method `scrape(url)`: For Style DNA extraction.

**✅ Phase 1 Verification:**
- [ ] Run `docker-compose up` and verify Postgres is accepting connections.
- [ ] Call `POST /upload` with a sample PDF. Verify chunks appear in Pinecone Console.
- [ ] Call `FirecrawlService.search("test")` and verify structured JSON response.

## Phase 2: The Agentic Core (LangGraph)
**Goal:** Build the state machine that orchestrates research, planning, and writing.

- [x] **State Definition**
    - Define `AgentState` (TypedDict):
        - `topic`: str
        - `style_profile`: dict
        - `research_data`: list
        - `outline`: list[dict] (Section headers, intents, source_ids)
        - `draft_sections`: dict[section_id, text]
        - `critique_feedback`: dict
- [x] **Research Nodes**
    - `StyleAnalystNode`:
        - Input: List of URLs.
        - Action: `Firecrawl.scrape()` -> LLM Analysis -> Returns Style JSON.
    - `ResearcherNode`:
        - Action: Parallel execution of `Firecrawl.search()` (External) and `Pinecone.query()` (Internal).
        - Output: Synthesized context list.
- [x] **Planning Node & HITL**
    - `PlannerNode`:
        - Action: LLM generates JSON outline based on research.
    - `HumanApprovalNode`:
        - Action: Call `interrupt({"outline": state["outline"]})`.
        - Resume Logic: Expect `Command(resume={"approved_outline": ...})`.
- [x] **Drafting & Reflexion Loop**
    - `WriterNode`:
        - Action: Generate section text using `approved_outline` and `style_profile`.
    - `CriticNode`:
        - Action: LLM reviews draft against constraints.
        - Logic: If score < 0.8, return `Command(goto="WriterNode")`. Else `Command(goto="VisualsNode")`.
- [x] **Graph Compilation**
    - Compile graph with `PostgresSaver` checkpointer.
    - Expose via API: `POST /api/v1/agent/run` and `POST /api/v1/agent/resume`.

**✅ Phase 2 Verification:**
- [ ] Run the graph with a test topic.
- [ ] Verify execution pauses at `HumanApprovalNode`.
- [ ] Send a resume command via API and verify the graph continues to `WriterNode`.
- [ ] Check Postgres database to ensure state is persisted between API calls.

## Phase 3: Frontend (React)
**Goal:** Create a user-friendly interface for the complex agent workflow.

- [ ] **Project Setup**
    - Initialize Vite + React + TypeScript.
    - Install Tailwind CSS and `shadcn/ui` components.
- [ ] **Knowledge Bin UI**
    - Component: `FileUploader` (Drag & Drop).
    - Component: `BinList` (Show created bins and file counts).
- [ ] **Generation Wizard**
    - **Step 1: Setup:** Form for Topic, Tone URLs, and Bin Selection.
    - **Step 2: Research:** Progress bar showing "Scraping Web...", "Reading PDFs...".
    - **Step 3: The Blueprint (HITL):**
        - Drag-and-drop list for Outline sections.
        - "Edit Intent" modal for each section.
        - "Approve & Generate" button (triggers `resume` API).
    - **Step 4: Live Production:**
        - Stream updates as sections are completed.
        - Markdown renderer for final output.

**✅ Phase 3 Verification:**
- [ ] Upload a file via UI and see it appear in the list.
- [ ] Start a generation task.
- [ ] Verify the UI shows the "Outline Approval" screen when the backend pauses.
- [ ] Click "Approve" and watch the blog post appear section by section.

## Phase 4: Local LLM Integration
**Goal:** Enable privacy-first mode using Ollama.

- [ ] **Ollama Setup**
    - Ensure Ollama is running with `qwen2.5` or `llama3.1`.
- [ ] **Model Factory**
    - Create `LLMFactory` class in Python.
    - Logic: If `env.USE_LOCAL_LLM=true`, return `ChatOllama(model="qwen2.5")`. Else return `ChatOpenAI(model="gpt-5")`.
- [ ] **Embedding Switch**
    - Update `IngestionRouter` to support `OllamaEmbeddings` (`nomic-embed-text`) if configured.

**✅ Phase 4 Verification:**
- [ ] Set `USE_LOCAL_LLM=true`.
- [ ] Disconnect internet (optional) or monitor network traffic.
- [ ] Run a full generation flow and verify Ollama logs show activity.

## Phase 5: QA & Polish
- [ ] **Unit Tests:** `pytest` for all Nodes and Services.
- [ ] **E2E Tests:** Cypress/Playwright test for the full UI flow.
- [ ] **Prompt Engineering:** Refine the "Style Analyst" prompt to better capture nuances.
- [ ] **Error Handling:** Add retries for Firecrawl and LLM timeouts.
