# Project Context: Content Strategist Agent

## 1. Project Overview
**Goal:** Build an enterprise-grade "Content Strategist" agent, not just a writer. The system mimics a human editorial team to produce authoritative, SEO-optimized articles using internal data (RAG) while maintaining data privacy.

**Core Value Proposition:** "Turn your internal documents into authoritative, SEO-optimized articles without your data ever leaving your infrastructure."

## 2. Technical Stack & Decisions

### Core Architecture
- **Backend:** FastAPI (Python)
- **Frontend:** React
- **Orchestration:** LangGraph (for stateful, multi-step agent workflows)
- **State Persistence:** PostgreSQL (via `langgraph-checkpoint-postgres`) - Required for "Human-in-the-Loop" interrupts.

### AI & Models
- **Cloud Model (Default):** GPT-5 (Target/Placeholder for high-end reasoning)
- **Local Model (Default):** Qwen 3 (Target/Placeholder for local execution)
- **Additional Support:** Must support Llama series models via Ollama.
- **Embedding Models:**
  - *Cloud:* OpenAI `text-embedding-3-small` (1536 dim)
  - *Local:* `nomic-embed-text` or `bge-m3`

### Data Infrastructure (RAG)
- **Vector Database:** Pinecone (MVP choice)
- **PDF Parsing:** PyMuPDF (`fitz`) - Chosen for speed and metadata handling.
- **Chunking Strategy:** Recursive Character Splitter (1024 tokens size, 200 tokens overlap).
- **Search/Scraping:** Firecrawl (API Key available).

## 3. Key Features

### 🔒 Privacy-First Infrastructure
- Hybrid execution: Sensitive data processed locally (Ollama), general reasoning via Cloud.
- "Knowledge Bins": Secure, isolated containers for user documents (PDFs, reports).

### 🧬 Style DNA Extraction
- Analyzes user-provided URLs to extract a "Style Profile" (sentence variance, vocabulary, formatting).
- Ensures output matches the brand voice.

### 🛡️ The "Reflexion" Quality Loop
- **Critic Agent:** Reviews every draft against style rules and negative constraints.
- **Loop:** Draft -> Critic -> Fail? -> Rewrite -> Pass? -> Visuals.

## 4. Workflows (LangGraph)

### Pipeline A: The Librarian (Ingestion)
1.  **Upload:** User uploads PDFs to a specific "Bin".
2.  **Parse:** PyMuPDF extracts text and tables.
3.  **Chunk:** Split text with overlap.
4.  **Embed & Store:** Vectors upserted to Pinecone with Namespace ID (`{user_id}_{bin_id}`).

### Pipeline B: The Editor (Generation)
1.  **Research:**
    - *External:* Firecrawl (Web, Reddit, Arxiv).
    - *Internal:* Query Vector DB (Knowledge Bins).
    - *Style:* Scrape Tone URLs.
2.  **Planning (HITL):**
    - Agent proposes Outline with "Intent" and "Source IDs".
    - **Human-in-the-Loop:** User reviews/edits outline before generation proceeds.
3.  **Drafting:**
    - Section-by-section writing.
    - **Smart Linking:** Insert internal links from sitemap index.
    - **Citation:** Strict adherence to source IDs.
4.  **Reflexion:** Critic Agent reviews. Max 2 retries per section.
5.  **Visuals:** Generate Mermaid.js diagrams or DALL-E 3 prompts.
6.  **Assembly:** Compile to Markdown/HTML.

## 5. Development Guidelines
- **Code Style:** Python (PEP 8), React (Functional Components, Hooks).
- **Documentation:** All major agents and nodes must be documented.
- **Error Handling:** Graceful degradation if Local LLM is offline or Firecrawl fails.
