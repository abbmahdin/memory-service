# Memory-as-a-Service

**Persistent context storage for AI agents** — built on FastAPI, PostgreSQL (+pgvector), Redis, and Drizzle.

## Description

Memory-as-a-Service (MaaS) is a persistent context/memory layer for AI agents. It provides:

- **Agent registration** — register agents with unique IDs and names
- **Context storage** — store, retrieve, update, and delete agent contexts with optional TTL
- **Versioning** — create new versions of contexts with optimistic locking
- **Redis caching** — fast in-memory caching layer for contexts with TTL
- **Search** — vector-based context search (via pgvector)

Perfect for multi-agent systems (Hermes, OpenClaw, etc.) that need persistent memory across sessions.

## Stack

- **Backend** : FastAPI (Python 3.12) + SQLAlchemy async
- **Database** : PostgreSQL (with pgvector for vector search)
- **Cache** : Redis
- **Tests** : pytest + pytest-asyncio + faker

## Prérequis

- Docker + Docker Compose
- Python 3.12+ (optionnel, pour le dev local)

## Lancement rapide (Docker)

```bash
docker-compose up --build -d
```

L'API sera disponible sur [http://localhost:8000](http://localhost:8000)
Docs Swagger : [http://localhost:8000](http://localhost:8000)

## Lancement local (sans Docker)

```bash
# Créer un virtualenv
python3.12 -m venv .venv
source .venv/bin/activate

# Installer les dépendances
pip install -r requirements.txt

# Démarrer PostgreSQL + Redis (ou utiliser docker-compose)
docker-compose up -d postgres redis

# Appliquer les migrations
# (utiliser alembic si configuré)

# Lancer l'API
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## Tests

```bash
.venv/bin/python -m pytest -q
```

> 80%+ de couverture requise. Tous les tests doivent passer avant commit.

## API

### Authentification

Aucune authentification par défaut (à ajouter pour la production).

### Endpoints

#### Agents

```bash
# Register un agent
curl -X POST http://localhost:8000/api/v1/agents/ \
  -H "Content-Type: application/json" \
  -d '{"agent_id": "openclaw-01", "name": "OpenClaw Agent"}'

# Récupérer un agent
curl http://localhost:8000/api/v1/agents/openclaw-01

# Supprimer un agent
curl -X DELETE http://localhost:8000/api/v1/agents/openclaw-01
```

#### Contextes

```bash
# Stocker un contexte (avec TTL optionnel en secondes)
curl -X POST http://localhost:8000/api/v1/contexts/openclaw-01 \
  -H "Content-Type: application/json" \
  -d '{"key": "session_state", "data": "données de session", "ttl": 3600}'

# Récupérer un contexte
curl http://localhost:8000/api/v1/contexts/openclaw-01/<context_id>

# Lister les contextes d'un agent
curl http://localhost:8000/api/v1/contexts/openclaw-01

# Mettre à jour un contexte
curl -X PUT http://localhost:8000/api/v1/contexts/openclaw-01/<context_id> \
  -H "Content-Type: application/json" \
  -d '{"data": "données mises à jour"}'

# Supprimer un contexte
curl -X DELETE http://localhost:8000/api/v1/contexts/openclaw-01/<context_id>

# Supprimer TOUS les contextes d'un agent
curl -X DELETE http://localhost:8000/api/v1/contexts/openclaw-01

# Créer une nouvelle version d'un contexte
curl -X POST http://localhost:8000/api/v1/contexts/openclaw-01/<context_id>/version \
  -H "Content-Type: application/json" \
  -d '{"key": "session_state", "data": "nouvelle version"}'

# Lister les versions d'un contexte
curl http://localhost:8000/api/v1/contexts/openclaw-01/<context_id>/versions
```

#### Recherche

```bash
# Recherche vectorielle (endpoints à documenter selon l'implémentation)
curl http://localhost:8000/api/v1/search/?query=...
```

#### Health

```bash
curl http://localhost:8000/health
```

## Architecture

```
memory-service/
├── app/
│   ├── api/              # Routeurs FastAPI
│   │   ├── v1/
│   │   │   ├── contexts.py    # CRUD contextes
│   │   │   ├── agents.py      # CRUD agents
│   │   │   ├── search.py      # Recherche vectorielle
│   │   │   └── health.py      # Health check
│   ├── core/
│   │   ├── config.py      # Settings Pydantic
│   │   └── database.py    # DB session
│   ├── models/           # Modèles SQLAlchemy
│   ├── schemas/           # Schémas Pydantic
│   ├── services/          # Logique métier
│   └── main.py            # Application FastAPI
├── tests/
└── docker-compose.yml
```

## Variables d'environnement

```bash
# .env
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/memorydb
REDIS_URL=redis://localhost:6379/0
```