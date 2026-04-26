# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

open-zread is an automated code analysis tool that generates structured documentation (wiki) from source code repositories. It uses LLM agents with ReAct loops to explore a codebase, produce a table of contents (TOC), and then generate detailed markdown documents for each topic — all written to `.zread/wiki/` in the target project.

The codebase and all prompts are in Chinese (中文). Documentation output language is configurable via `settings.json`.

## Running

```bash
# Install dependencies (uses uv package manager)
uv sync

# Run the pipeline against the current working directory
uv run python main.py
```

The pipeline reads `settings.json` from the current directory (or falls back to built-in defaults). Environment variables like `DEEPSEEK_API_KEY` are loaded from `.env`.

## Configuration

- **`settings.json`** — Model tiers (`lite`, `pro`, `max`), parallelism settings, document language. `api_key` fields support `${ENV_VAR}` interpolation.
- **`.env`** — API keys (`DEEPSEEK_API_KEY`), Langfuse credentials (`LANGFUSE_SECRET_KEY`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_BASE_URL`).
- **Langfuse Prompt Management** — Prompts are synced to Langfuse via `prompt/langfuse_prompt_init.py`. At runtime, `prompt/langfuse_prompt.py` fetches compiled prompts from Langfuse, not from local Python strings.

## Architecture

Two-phase pipeline orchestrated in `pipeline/run.py`:

1. **Phase 1 — TOC Generation** (`pipeline/explorer.py`): Uses `pro` model config. An LLM agent explores the project with filesystem tools, outputs an XML table of contents. Parsed into `Topic` objects by `util/utils.py:parse_toc_xml`.

2. **Phase 2 — Content Generation** (`pipeline/researcher.py`): Uses `max` model config. For each topic, a separate LLM agent generates detailed markdown content. Topics are processed in parallel (configurable via `research_parallel` / `research_threads`).

### Key components

- **`provider/`** — Dual-provider abstraction (`openai` and `anthropic` protocols). `provider/adaptor.py` (LLMAdaptor) routes to the correct API module based on `settings.json`. Both providers implement `stream_events()`, `call()`, and message conversion.
- **`agent/react_agent.py`** — ReAct loop implementation. Streams events for each step, handles tool execution, and includes automatic context compression when conversation exceeds 200K chars.
- **`base/types.py`** — Core types: `Event`, `EventType`, `Tool`, message classes (`SystemMessage`, `UserMessage`, `AssistantMessage`, `ToolMessage`), and the `@tool` decorator that introspects function signatures to build tool schemas.
- **`tool/fs_tool.py`** — Filesystem tools available to agents: `get_dir_structure`, `view_file_in_detail`, `run_bash` (read-only, whitelist-enforced).
- **`prompt/`** — Prompt definitions (`pipeline_prompts.py`, `react_prompts.py`) and Langfuse integration. Prompts use Python `{variable}` format strings locally, converted to Langfuse `{{variable}}` template syntax on sync.
- **`setting/settings.py`** — Loads and merges `settings.json` with defaults, expands env vars, auto-appends `/anthropic` to base URLs for the Anthropic provider.

### Data flow

```
main.py → pipeline/run.py (run_pipeline)
  ├─ Phase 1: explorer.py → LLMAdaptor(pro) → react_agent → XML TOC → parse_toc_xml → Topic[]
  └─ Phase 2: researcher.py → LLMAdaptor(max) → react_agent → <blog> markdown → extract_blog_content
Output: .zread/wiki/versions/<timestamp>/wiki.json + <slug>.md files
```
