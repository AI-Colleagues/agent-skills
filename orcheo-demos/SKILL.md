---
name: orcheo-demos
description: Run and deploy Orcheo conversational search demos. Use when running demo scripts locally, deploying demos to Orcheo server, or exploring RAG, hybrid search, conversational search, and evaluation workflows from the examples.
license: MIT
metadata:
  author: "AI Colleagues"
  version: "0.1"
---

# Orcheo Demos

## Overview

Run the conversational search demo suite from the Orcheo examples. These demos showcase progressive RAG workflows from basic retrieval to production-grade conversational search with evaluation. The demos can run locally for development or be deployed to an Orcheo server started via the `orcheo` skill.

**Prerequisites**:
1. **Orcheo environment initialized**: This skill assumes the Orcheo environment has been fully set up using the `orcheo` skill, which installs `orcheo`, `orcheo-backend`, and `orcheo-sdk`.
2. **Demo files available locally**: See "Getting the Demo Files" below.

## Getting the Demo Files

This skill requires the conversational search demo files from the Orcheo repository. Download only the demo files using git sparse checkout:

```bash
git clone --filter=blob:none --sparse https://github.com/AI-Colleagues/orcheo.git orcheo-demos
cd orcheo-demos
git sparse-checkout set examples/conversational_search
```

This downloads just the `examples/conversational_search/` directory without the full repository. All paths in this document are relative to this cloned directory (e.g., `orcheo-demos/`).

## Demo Overview

| Demo | Name | Description | Credentials Required |
|------|------|-------------|---------------------|
| 1 | Hybrid Indexing | Web doc ingestion with dense + sparse embeddings to Pinecone | `openai_api_key`, `pinecone_api_key` |
| 2 | Basic RAG | In-memory retrieval pipeline with a demo embedding + grounded generation | `openai_api_key` |
| 3 | Hybrid Search | Dense + sparse + web search with fusion, rerank, and summarization | `openai_api_key`, `pinecone_api_key`, `tavily_api_key` |
| 4 | Conversational Search | Stateful chat with routing, rewriting, and topic shift detection | `openai_api_key`, `pinecone_api_key` |
| 5 | Production | Caching, guardrails, streaming, and multi-hop planning | `openai_api_key`, `pinecone_api_key` |
| 6 | Evaluation | Golden datasets, retrieval metrics, and A/B testing | `openai_api_key`, `pinecone_api_key` |

**Recommended starting point**: Demo 2 works with an in-memory vector store and
no external vector database.

**Note**: Demo 1 must be run before Demos 3-6 to index documents into Pinecone.

## Before Running Demos

### Step 1: Verify Setup

Run the setup checker to verify all prerequisites:

```bash
python examples/conversational_search/check_setup.py
```

This checks:
- Python version (3.12+ required)
- Orcheo CLI installation
- Sample data directory
- Required credentials for each demo

If checks fail, follow the guidance provided by the checker.

### Step 2: Configure Credentials

Create credentials using the Orcheo CLI.

**For Demo 2 (minimum requirement)**:
```bash
orcheo credential create openai_api_key --secret sk-your-openai-key
```

**For Demo 3 (additional)**:
```bash
orcheo credential create tavily_api_key --secret tvly-your-tavily-key
```

**For Demos 1, 3, 4, 5, 6 (additional)**:
```bash
orcheo credential create pinecone_api_key --secret your-pinecone-api-key
```

**IMPORTANT**: Ask the user for their API keys before creating credentials. Never create credentials with placeholder values.

To check existing credentials:
```bash
orcheo credential list
```

## Running Example Workflows

Each demo workflow must be uploaded to the Orcheo server before running. Follow these steps for each demo:

### Step 1: Upload the Workflow

Upload the demo workflow to the Orcheo server:

```bash
orcheo workflow upload examples/conversational_search/demo_<N>_<name>/demo_<N>.py --name "Demo <N>: <Name>"
```

This returns a workflow ID that you'll use to run the workflow.

### Step 2: Verify Required Credentials

Before running, ensure the required credentials exist in the Orcheo credential vault:

```bash
orcheo credential list
```

If credentials are missing, create them (see "Configure Credentials" section above):

```bash
orcheo credential create <credential_name> --secret <value>
```

**IMPORTANT**: Ask the user for their API keys before creating credentials. Never create credentials with placeholder values.

### Step 3: Run the Workflow

Execute the workflow using the workflow ID from Step 1:

```bash
orcheo workflow run <workflow-id> --inputs '{"message": "your query here"}'
```

---

### Demo 1: Hybrid Indexing (Prerequisite for Demos 4-6)

```bash
# Upload
orcheo workflow upload examples/conversational_search/demo_1_hybrid_indexing/demo_1.py --name "Demo 1: Hybrid Indexing"

# Run (after verifying credentials)
orcheo workflow run <workflow-id> --inputs '{}'
```

**Requires**: `openai_api_key`, `pinecone_api_key`

**What to expect**:
- Loads Orcheo docs from GitHub raw URLs by default (`docs/index.md`,
  `docs/manual_setup.md`)
- Extracts metadata and chunks documents
- Generates both dense (OpenAI) and sparse (BM25) embeddings
- Upserts vectors to Pinecone indexes `orcheo-demo-dense` and
  `orcheo-demo-sparse` under the `hybrid_search` namespace
- Output shows indexing summary for both dense and sparse stores

**Important**: Run this demo before Demos 3-6 to populate the Pinecone indexes
they query.

### Demo 2: Basic RAG (Recommended First Demo)

```bash
# Upload
orcheo workflow upload examples/conversational_search/demo_2_basic_rag/demo_2.py --name "Demo 2: Basic RAG"

# Run (after verifying credentials)
orcheo workflow run <workflow-id> --inputs '{"message": "What is this document about?"}'
```

**Requires**: `openai_api_key`

**What to expect**:
- Routes between ingestion, search, and direct generation based on inputs and
  in-memory vector store state
- Uses a demo embedding function for retrieval (no external vector DB required)
- Output includes routing decisions, retrieval results, and grounded responses

### Demo 3: Hybrid Search

```bash
# Upload
orcheo workflow upload examples/conversational_search/demo_3_hybrid_search/demo_3.py --name "Demo 3: Hybrid Search"

# Run (after verifying credentials)
orcheo workflow run <workflow-id> --inputs '{"message": "your query here"}'
```

**Requires**: `openai_api_key`, `pinecone_api_key`, `tavily_api_key`, and indexed
data in Pinecone (run Demo 1 first)

**What to expect**:
- Fans out across dense, sparse, and web search retrieval
- Fuses and reranks results before generating a cited response

### Demo 4: Conversational Search

```bash
# Upload
orcheo workflow upload examples/conversational_search/demo_4_conversational/demo_4.py --name "Demo 4: Conversational Search"

# Run (after verifying credentials)
orcheo workflow run <workflow-id> --inputs '{"message": "your query here"}'
```

**Requires**: `openai_api_key`, `pinecone_api_key`, and indexed data in Pinecone (run Demo 1 first)

### Demo 5: Production

```bash
# Upload
orcheo workflow upload examples/conversational_search/demo_5_production/demo_5.py --name "Demo 5: Production"

# Run (after verifying credentials)
orcheo workflow run <workflow-id> --inputs '{"message": "your query here"}'
```

**Requires**: `openai_api_key`, `pinecone_api_key`, and indexed data in Pinecone (run Demo 1 first)

### Demo 6: Evaluation

```bash
# Upload
orcheo workflow upload examples/conversational_search/demo_6_evaluation/demo_6.py --name "Demo 6: Evaluation"
# Optional: include default recursion limit/tags
orcheo workflow upload examples/conversational_search/demo_6_evaluation/demo_6.py --config-file examples/conversational_search/demo_6_evaluation/config.json

# Run (after verifying credentials)
orcheo workflow run <workflow-id> --inputs '{}'
```

**Requires**: `openai_api_key`, `pinecone_api_key`, and indexed data in Pinecone (run Demo 1 first)

## Deploying Demos to Orcheo Server

Demos can be deployed to an Orcheo server for API access and UI interaction. This requires the Orcheo services to be running (use the `orcheo` skill to start them).

### Prerequisites

1. **Orcheo services running**: Use the `orcheo` skill to start services via `docker compose up -d`
2. **Server URL**: Default is `http://localhost:8000`

### Upload a Demo Workflow

Each demo exposes a `build_graph()` function and `DEFAULT_CONFIG` for server deployment. Upload the demo script to create a workflow:

```bash
orcheo workflow upload examples/conversational_search/demo_2_basic_rag/demo_2.py --name "Basic RAG Demo"
```

### Publish and Access via ChatKit Web UI

After uploading, you can publish a workflow to make it accessible via the ChatKit web interface:

```bash
orcheo workflow publish <workflow-id> --force
```

**Tip**: Once published, the workflow can be visited on the ChatKit web UI for interactive chat-based access.

### Invoke via API

After uploading, invoke the workflow through the Orcheo API:

```bash
# RAG mode (with documents)
curl -X POST http://localhost:8000/api/v1/workflows/<workflow-id>/invoke \
  -H "Content-Type: application/json" \
  -d '{
    "inputs": {
      "documents": [
        {
          "storage_path": "/path/to/document.txt",
          "source": "document.txt",
          "metadata": {"category": "tech"}
        }
      ],
      "message": "What is this document about?"
    }
  }'

# Non-RAG mode (direct generation)
curl -X POST http://localhost:8000/api/v1/workflows/<workflow-id>/invoke \
  -H "Content-Type: application/json" \
  -d '{
    "inputs": {
      "message": "What is the capital of France?"
    }
  }'
```

## Sample Data

The demos include shared sample data located at `examples/conversational_search/data/`:

- **docs/**: Sample knowledge base (Markdown files)
  - `authentication.md` - Authentication patterns
  - `product_overview.md` - Product architecture
  - `troubleshooting.md` - Common issues
- **queries.json**: Sample queries with intents
- **golden/**: Expected answers for evaluation
- **labels/**: Relevance labels for metrics

Demo 1 and Demo 6 default to GitHub raw URLs, but you can override configs or
edit the scripts to point at this local sample data instead.

## Demo-Specific Documentation

Demo READMEs (where available) include workflow diagrams, configuration options,
and expected outputs:

- `examples/conversational_search/demo_2_basic_rag/README.md`
- `examples/conversational_search/demo_3_hybrid_search/README.md`
- `examples/conversational_search/demo_4_conversational/README.md`
- `examples/conversational_search/demo_5_production/README.md`
- `examples/conversational_search/demo_6_evaluation/README.md`

## Troubleshooting

### "Credential not found" errors

Create the missing credential:
```bash
orcheo credential create <credential_name> --secret <value>
```

### "Connection refused" when deploying

The Orcheo server is not running. Use the `orcheo` skill to start services:
```bash
docker compose -f path/to/docker-compose.yml up -d
```

### Import errors when running demos

Ensure the Orcheo environment is fully initialized using the `orcheo` skill. The skill installs all required packages (`orcheo`, `orcheo-backend`, `orcheo-sdk`).

### Demo script not found

Ensure you have downloaded the demo files as described in "Getting the Demo Files" above. The demos are located at `examples/conversational_search/` in the cloned directory.

## Resources

- Demo suite: `examples/conversational_search/`
- Setup checker: `examples/conversational_search/check_setup.py`
- Shared utilities: `examples/conversational_search/utils.py`
- Sample data: `examples/conversational_search/data/`
