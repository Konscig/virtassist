# Deployment Guide - Annotation Service

## Overview

This guide explains how to deploy and update the annotation service on the remote server.

---

## Structure

```
Local machine:
  ~/src/github.com/webmasha/voproshalych-personal/
    ├── deploy_annotation.sh           # Script to sync files to server
    └── Submodules/voproshalych/benchmarks/annotation_service/
        ├── Dockerfile
        ├── docker-compose.yml        # Reference only (not used for startup)
        ├── entrypoint.sh
        ├── restart.sh                 # Script to build and start on server
        ├── annotate_with_ollama.py    # Python annotation script
        ├── monitor_progress.py         # Real-time progress monitor
        └── data/
            ├── confluence_urls.json   # URL mapping file

Remote server:
  /srv/tgu/annotation_service/
    ├── Dockerfile
    ├── docker-compose.yml           # Reference only
    ├── entrypoint.sh
    ├── restart.sh
    ├── annotate_with_ollama.py
    ├── monitor_progress.py
    └── data/
        ├── confluence_urls.json
        └── dataset_from_20250601_to_20260228_20260303_082311_annotated.json
```

---

## Quick Start (First Time)

### 1. On Local Machine

```bash
cd ~/src/github.com/webmasha/voproshalych-personal

# Copy data file to annotation_service/data/
cp Submodules/voproshalych/benchmarks/data/confluence_urls.json Submodules/voproshalych/benchmarks/annotation_service/data/

# Sync all files to server
./deploy_annotation.sh
```

### 2. On Remote Server

```bash
# SSH to server
ssh ave@iv-ml.orienteer.ru

# Navigate to service directory
cd /srv/tgu/annotation_service

# Create data directory
mkdir -p data

# Build and start container
bash restart.sh
```

### 3. Monitor Logs

```bash
# On server
docker logs -f voproshalych-annotation

# Or from local machine
ssh ave@iv-ml.orienteer.ru 'docker logs -f voproshalych-annotation'
```

---

## Updating the Service

### When you change Python code or scripts

**On local machine:**
```bash
cd ~/src/github.com/webmasha/voproshalych-personal

# Sync files to server
./deploy_annotation.sh
```

**On remote server:**
```bash
cd /srv/tgu/annotation_service

# Rebuild and restart
bash restart.sh
```

### When you change Dockerfile or docker-compose.yml

**On local machine:**
```bash
cd ~/src/github.com/webmasha/voproshalych-personal

# Sync files to server
./deploy_annotation.sh
```

**On remote server:**
```bash
cd /srv/tgu/annotation_service

# Rebuild and restart
bash restart.sh
```

### When you change only data files

**On local machine:**
```bash
cd ~/src/github.com/webmasha/voproshalych-personal

# Copy data file
cp benchmarks/data/confluence_urls.json Submodules/voproshalych/benchmarks/annotation_service/data/

# Sync files to server
./deploy_annotation.sh
```

**On remote server:**
```bash
# Just restart container (no rebuild needed)
cd /srv/tgu/annotation_service
docker restart voproshalych-annotation

# View logs
docker logs -f voproshalych-annotation
```

---

## Individual Commands Reference

### Local Machine Commands

```bash
# Navigate to project root
cd ~/src/github.com/webmasha/voproshalych-personal

# Sync files to server (excludes .tar files)
./deploy_annotation.sh

# Manual rsync (if you want more control)
rsync -avz --delete \
  --exclude "*.tar" \
  --exclude "__pycache__" \
  --exclude "*.pyc" \
  Submodules/voproshalych/benchmarks/annotation_service/ \
  ave@iv-ml.orienteer.ru:/srv/tgu/annotation_service/
```

### Remote Server Commands

```bash
# Navigate to service directory
cd /srv/tgu/annotation_service

# Full restart (stop, rebuild, start)
bash restart.sh

# Or manually:
docker stop voproshalych-annotation || true
docker rm voproshalych-annotation -f
docker buildx build --platform linux/amd64 --load -f Dockerfile -t voproshalych-annotation .
docker run -d \
  --name voproshalych-annotation \
  --restart unless-stopped \
  --entrypoint "" \
  --cpu-shares 100 \
  -p 11434:11434 \
  -v $(pwd)/data:/app/data \
  -v ollama_models:/root/.ollama/models \
  -e OLLAMA_FLASH_ATTENTION=false \
  -e OLLAMA_NUM_THREAD=16 \
  -e OLLAMA_NUM_GPU_LAYERS=0 \
  voproshalych-annotation:latest \
  /app/entrypoint.sh

# Just restart container (no rebuild)
docker restart voproshalych-annotation

# View logs
docker logs -f voproshalych-annotation

# Check container status
docker ps | grep voproshalych-annotation

# Check annotation status
docker exec voproshalych-annotation python3 /app/annotate_with_ollama.py \
    --input /app/data/dataset_from_20250601_to_20260228_20260303_082311_annotated.json \
    --status

# Request soft stop (after next batch)
docker exec voproshalych-annotation python3 /app/annotate_with_ollama.py \
    --input /app/data/dataset_from_20250601_to_20260228_20260303_082311_annotated.json \
    --stop

# Monitor progress in real time (optional)
docker exec -it voproshalych-annotation python3 /app/monitor_progress.py
```

---

## Troubleshooting

### Container not starting

```bash
# Check logs
docker logs voproshalych-annotation

# Check container status
docker ps -a | grep voproshalych-annotation

# Force stop and remove
docker rm voproshalych-annotation -f
docker rmi voproshalych-annotation:latest -f

# Rebuild from scratch
cd /srv/tgu/annotation_service
bash restart.sh
```

### Docker volume issues

```bash
# List volumes
docker volume ls

# Backup model volume
docker run --rm -v annotation_service_ollama_models:/data -v $(pwd):/backup \
  alpine tar czf /backup/ollama_models.tar.gz -C /data .

# Remove and recreate volume
docker stop voproshalych-annotation || true
docker rm voproshalych-annotation -f || true
docker volume rm annotation_service_ollama_models
cd /srv/tgu/annotation_service
bash restart.sh
```

### Sync issues

```bash
# Force sync all files (delete remote files not in local)
rsync -avz --delete \
  Submodules/voproshalych/benchmarks/annotation_service/ \
  ave@iv-ml.orienteer.ru:/srv/tgu/annotation_service/

# Dry run to see what will be synced
rsync -avz --delete --dry-run \
  Submodules/voproshalych/benchmarks/annotation_service/ \
  ave@iv-ml.orienteer.ru:/srv/tgu/annotation_service/
```

---

## Monitoring Annotation Progress

### Current Implementation

**How it works:**

1. **Startup:** entrypoint.sh launches script with `--batch-size 10 --delay 0`
2. **Saving:** Overwrites file every **10 processed questions**
3. **File:** `/app/data/dataset_from_20250601_to_20260228_20260303_082311_annotated_annotated.json`
4. **Final save:** Additionally saves entire file at the end of work

### Checking Progress

**1. Watch logs in real time:**
```bash
docker logs -f voproshalych-annotation
```

You'll see messages:
- `Processing question X/1305 (index: Y)`
- `Processed 10/1305 questions`
- `Saved progress to /app/data/..._annotated_annotated.json`

**2. Check status via command:**
```bash
docker exec voproshalych-annotation python3 /app/annotate_with_ollama.py \
    --input /app/data/dataset_from_20250601_to_20260228_20260303_082311_annotated.json \
    --status
```

Output:
```
Статус аннотации:
  Всего вопросов: 1305
  Проаннотировано: XXX
  Осталось: XXX
  Прогресс: XX.X%
  Файл: /app/data/..._annotated_annotated.json
```

**3. Check file directly on server:**
```bash
ssh ave@iv-ml.orienteer.ru
cd /srv/tgu/annotation_service/data

# View last entry (second-to-last line of JSON file)
tail -50 dataset_from_20250601_to_20260228_20260303_082311_annotated_annotated.json | grep annotate_is_small_talk | tail -1
```

### Summary

- ✅ **Batches:** Yes, file is rewritten every 10 questions
- ✅ **Progress saved:** Yes, after each batch and at the end
- ✅ **Resume:** On restart scans file and continues from last annotation

---

## Real-Time Progress Monitoring

### Using monitor script

The monitor script shows real-time progress with simple text output:

\`\`\`bash
docker exec -it voproshalych-annotation python3 /app/monitor_progress.py
\`\`\`

**Output example:**
\`\`\`
Progress: 42.5% (555/1305)
Remaining: 750 questions
Speed: 0.095 questions/sec (5.7 questions/min)
ETA: 2h 11min
\`\`\`

**Features:**
- Simple text output (no progress bar, no special characters)
- Progress percentage with questions done/remaining
- Real-time speed (questions/sec and questions/min)
- Estimated time remaining (ETA)
- Auto-refreshes every 2 seconds

**To stop:**
- Press \`Ctrl+C\`

---
## Performance Tuning

### CPU Configuration

**CPU shares in restart.sh:**
- Fixed at `100` (0.1 CPU) in docker run command

**To change CPU limit:**
Edit `restart.sh` and change `--cpu-shares 100` to desired value:
- `100` - low load (0.1 CPU)
- `512` - medium load (0.5 CPU)
- `1024` - full load (1.0 CPU)

**Edit entrypoint.sh for Ollama threads:**
```bash
NUM_THREADS=${OLLAMA_NUM_THREAD:-16}  # Number of CPU threads
```

### Environment Variables

In `restart.sh` (passed to docker run):
```bash
-e OLLAMA_FLASH_ATTENTION=false    # Disabled for CPU
-e OLLAMA_NUM_THREAD=16           # CPU threads for Ollama
-e OLLAMA_NUM_GPU_LAYERS=0         # 0 for CPU mode
```

### Annotation Parameters

In `entrypoint.sh`:
```bash
python3 annotate_with_ollama.py \
    --input /app/data/dataset_from_20250601_to_20260228_20260303_082311_annotated.json \
    --model qwen3.5:35b-a3b \
    --batch-size 10 \           # Save progress every N questions
    --delay 0                  # No artificial delay
```

---

## File Summary

### Files to sync (via rsync)
- `Dockerfile`
- `restart.sh`
- `entrypoint.sh`
- `annotate_with_ollama.py`
- `monitor_progress.py`
- `data/confluence_urls.json` (URL mapping file)

### Files NOT synced (kept for reference)
- `docker-compose.yml` (not used - restart.sh uses docker run)
- `*.tar` (Docker images - build on server)
- `*.md` (Documentation)
- `data/dataset_*.json` (annotation progress - stays on server)
- `__pycache__/` (Python cache)

### Files NOT to sync
- `*.tar` (Docker images - build on server)
- `*.md` (Documentation)
- `data/dataset_*.json` (annotation progress - stays on server)
- `__pycache__/` (Python cache)

### Files that stay on server
- `/srv/tgu/annotation_service/data/dataset_*.json` (annotation progress)
- Docker volumes (Ollama models)

---

## SSH Shortcuts

Add to `~/.ssh/config`:
```
Host forecast
    HostName iv-ml.orienteer.ru
    User ave
    ForwardAgent yes
```

Then use:
```bash
ssh forecast
```

---

## Quick Reference

| Task | Command |
|------|---------|
| Sync files | `./deploy_annotation.sh` |
| Build & start | `cd /srv/tgu/annotation_service && bash restart.sh` |
| View logs | `docker logs -f voproshalych-annotation` |
| Monitor progress (real-time) | `docker exec -it voproshalych-annotation python3 /app/monitor_progress.py` |
| Check status | `docker ps \| grep voproshalych-annotation` |
| Soft stop | `docker exec voproshalych-annotation python3 ... --stop` |
| Check progress | `docker exec voproshalych-annotation python3 ... --status` |
| Restart only | `docker restart voproshalych-annotation` |
| Full rebuild | `bash restart.sh` |
