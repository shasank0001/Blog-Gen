# Content Strategist Agent (Blog-Gen)

An AI-powered agent that researches, plans, and writes SEO-optimized blog posts based on your internal documents and brand voice.

## Features

- **RAG-based Research**: Upload PDFs to "Knowledge Bins" (Pinecone) for grounded content generation.
- **Style Analysis**: Analyze existing blog posts to mimic your brand's tone and formatting.
- **Human-in-the-Loop**: Review and edit the generated outline before the agent writes the full article.
- **Agentic Workflow**: Powered by LangGraph to orchestrate research, planning, critiquing, and writing steps.

## Tech Stack

- **Backend**: FastAPI, LangGraph, LangChain, PostgreSQL (AsyncPostgresSaver), Pinecone, Firecrawl.
- **Frontend**: React, Vite, Tailwind CSS, Shadcn UI.
- **Infrastructure**: Docker Compose.

## Getting Started

### Prerequisites

- Docker & Docker Compose
- Node.js 18+
- Python 3.11+
- API Keys: OpenAI, Pinecone, Firecrawl.

### Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/shasank0001/Blog-Gen.git
   cd Blog-Gen
   ```

2. **Environment Variables**
   Create a `.env` file in `backend/` with your API keys (see `backend/app/core/config.py` for required fields).

3. **Run with Docker**
   ```bash
   cd backend
   docker-compose up -d
   ```

4. **Run Frontend**
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

5. **Access**
   - Frontend: http://localhost:5173
   - Backend API: http://localhost:8000/docs
