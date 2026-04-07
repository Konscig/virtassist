# Mini-Guide: Run v1 Benchmarks on Shared Corpus

## Overview
This guide explains how to calculate KPI metrics for v1 on the shared corpus from v2.

**Target Metrics:**
- **Tier 1 Retrieval**: `HitRate@5`, `MRR`, `NDCG@10`
- **Tier 2 Generation**: `Faithfulness`, `Answer Relevance`
- **Tier 3 End-to-End**: `avg_e2e_score`, `avg_semantic_similarity`
- **Tier UX**: `response_semantic_consistency`

## Prerequisites
1. Both v1 and v2 Docker containers running
2. Z.AI API key with balance (for LLM judge)

## Step 1: Export Corpus from v2

```bash
cd Submodules/voproshalych_v2
POSTGRES_PORT=5433 python3 benchmarks/export_shared_corpus.py \
    --output benchmarks/data/shared_corpus.json \
    --limit 374  # Full corpus
```

## Step 2: Import Corpus to v1

The import requires vector(1024) embeddings. Run inside v1 container or use direct SQL:

```bash
# Option A: Direct SQL (example with 5 chunks)
docker exec -i virtassist-db psql -U postgres -d virtassist < import_script.sql

# Option B: Python script (requires dependencies installed)
docker exec virtassist-qa pip install sentence-transformers pgvector
docker cp benchmarks/data/shared_corpus.json virtassist-qa:/tmp/corpus.json
docker exec virtassist-qa python benchmarks/import_shared_corpus_to_v1.py \
    --input /tmp/corpus.json
```

## Step 3: Generate Synthetic QA Dataset

**⚠️ Requires Z.AI API balance**

```bash
cd Submodules/voproshalych_v2
python3 benchmarks/generate_shared_dataset.py \
    --corpus benchmarks/data/shared_corpus.json \
    --output benchmarks/data/dataset_synthetic.json \
    --max-questions 100
```

If you get "Insufficient balance" error, you need to:
1. Recharge your Z.AI account, OR
2. Create a manual dataset in the required format

### Manual Dataset Format
```json
[
  {
    "question": "Как оформить справку?",
    "canonical_chunk_id": 1,
    "relevant_chunk_ids": [1],
    "answer": "Справка оформляется..."
  }
]
```

## Step 4: Materialize Dataset

```bash
cd Submodules/voproshalych_v2
python3 benchmarks/materialize_shared_dataset.py \
    --dataset benchmarks/data/dataset_synthetic.json \
    --corpus benchmarks/data/shared_corpus.json \
    --output benchmarks/data/dataset_v1.json \
    --target v1
```

## Step 5: Run Benchmark on v1

```bash
cd Submodules/voproshalych

# Run all tiers
python3 benchmarks/run_comprehensive_benchmark.py \
    --tier all \
    --dataset benchmarks/data/dataset_v1.json \
    --output benchmarks/reports/v1_benchmark.json

# Or run specific tier
python3 benchmarks/run_comprehensive_benchmark.py \
    --tier 1 \
    --dataset benchmarks/data/dataset_v1.json
```

## Key Files

| File | Purpose |
|------|---------|
| `v2/benchmarks/export_shared_corpus.py` | Export frozen corpus from v2 |
| `v2/benchmarks/generate_shared_dataset.py` | Generate synthetic QA |
| `v2/benchmarks/materialize_shared_dataset.py` | Convert to v1 IDs |
| `benchmarks/import_shared_corpus_to_v1.py` | Import to v1 |
| `benchmarks/run_comprehensive_benchmark.py` | Run benchmarks |

## Environment Variables

Make sure `.env.benchmark-models` has:
```
BENCHMARKS_JUDGE_MODEL=glm-4-plus
BENCHMARKS_JUDGE_API_KEY=your_zai_key
BENCHMARKS_JUDGE_URL=https://api.z.ai/api/paas/v4
```

## Troubleshooting

### "Insufficient balance" on Z.AI
→ Recharge account or use alternative judge model

### Database connection errors
→ Ensure v1 postgres is running: `docker ps | grep virtassist`

### Import embedding dimension mismatch
→ V1 uses vector(1024), ensure v2 export uses compatible embeddings
