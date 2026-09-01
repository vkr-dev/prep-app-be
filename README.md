# prep-app-be

FastAPI backend for the Learning Tool - an interview-prep question generator.

## What it does

Given a topic, generates a full set of interview questions organized by subtopic, each with reading content plus practice Q&A. Runs a multi-step agentic pipeline (RAG retrieval, question generation, dedupe/refine, categorization, explanation, eval) backed by a swappable LLM provider, a vector store for retrieval, and Postgres for caching, auth, and per-user history. Also serves curated (hand-authored, non-LLM) content for a set of core topics, and enforces a content-safety guardrail on all free-text topic input.

## Tech stack

- **Framework**: FastAPI, Python
- **Database/ORM**: Postgres (Neon), SQLModel
- **LLM providers**: Anthropic Claude, Google Gemini, Groq - swappable via config, single shared interface
- **Vector store**: Chroma (retrieval + embeddings via Google's embedding API)
- **Auth**: JWT, bcrypt password hashing, owner/guest approval model
- **Deployment**: Render
