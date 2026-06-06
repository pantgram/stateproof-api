# StateProof API

Cryptographic proof of state for automated workflows using Merkle trees. Each session maintains a Merkle tree of events. This allows tamper-evident verification that no event has been altered after the fact.

## Features

- **Session-level Merkle trees** -- every session has an event-level tree; proofs can be generated and verified independently
- **Multi-tenant** -- organizations, users, and API-key clients with scoped access
- **User signup with invite flow** -- first user in an org is auto-approved; subsequent users require admin approval via an invite token
- **JWT authentication** -- access tokens (short-lived) and refresh tokens (revocable, with rotation reuse detection)
- **API key clients** -- machine-to-machine auth via API keys with key rotation
- **Password reset** -- token-based password reset flow via email
- **Stateless verification** -- verify any Merkle proof against a known root hash without database access
- **Rate limiting** -- IP-based rate limiting on sensitive auth endpoints

## Tech Stack

- Python 3.14, FastAPI, Uvicorn
- SQLAlchemy 2.0 (async) + asyncpg
- PostgreSQL
- Alembic (migrations)
- PyJWT + bcrypt
- Pydantic Settings
- uv (package manager)
- Docker / Docker Compose

## Quick Start

### Local Development

```bash
cp .env.example .env
uv sync
uv run uvicorn src.main:app --reload
```

Requires a running PostgreSQL instance. Update `DATABASE_URL` in `.env` accordingly.

### Docker

```bash
cp .env.example .env
docker compose up --build
```

The API will be available at `http://localhost:8000`.

Interactive API docs: `http://localhost:8000/docs`

### Running Tests

```bash
uv sync --group dev
uv run pytest
```

### Database Migrations

```bash
uv run alembic upgrade head
uv run alembic revision --autogenerate -m "description"
```

## API Overview

All endpoints are under `/api/v1`. Authentication uses `Bearer` tokens.

### Health

| Method | Endpoint | Auth |
|--------|----------|------|
| GET | `/health` | No |

### Auth

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/auth/signup` | Register a user and optionally an organization |
| POST | `/auth/login` | Email/password login |
| POST | `/auth/token` | Exchange API key for JWT tokens |
| POST | `/auth/refresh` | Refresh an access token |
| POST | `/auth/revoke` | Revoke a refresh token |
| POST | `/auth/approve/{token}` | Approve a pending user via invite token (admin) |
| GET | `/auth/clients` | List API key clients (admin) |
| POST | `/auth/clients` | Create an API key client (admin) |
| DELETE | `/auth/clients/{client_id}` | Delete an API key client (admin) |
| POST | `/auth/clients/{client_id}/rotate` | Rotate an API key (admin) |
| GET | `/auth/me` | Get current user profile |
| POST | `/auth/forgot-password` | Request a password reset email |
| POST | `/auth/reset-password` | Reset password with token |
| GET | `/auth/pending-invites` | List pending invite tokens (admin) |

### Workflows

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/workflows` | Any | Create a workflow |
| GET | `/workflows` | Any | List workflows |
| GET | `/workflows/{id}` | Any | Get workflow details |
| PATCH | `/workflows/{id}` | Any | Update workflow name/metadata |
| POST | `/workflows/{id}/sessions` | API Key | Submit a session with events |
| GET | `/workflows/{id}/sessions` | Any | List sessions |
| GET | `/workflows/{id}/sessions/{sid}` | Any | Get session details |
| GET | `/workflows/{id}/sessions/{sid}/events/{seq}/proof` | Any | Get Merkle proof for an event |
| GET | `/workflows/{id}/sessions/{sid}/tree-nodes` | Any | List session tree nodes |

### Verification

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/verify` | No | Stateless Merkle proof verification |

## Project Structure

```
src/
├── main.py              # FastAPI app factory and lifespan
├── api/v1/              # API v1 route handlers
│   ├── router.py        # Root router with health check
│   ├── auth.py          # Auth and client management endpoints
│   ├── workflows.py     # Workflow, session, proof, and verify endpoints
│   └── verify.py        # Stateless verification endpoint
├── db/                  # Database engine and session setup
├── middleware/
│   ├── config.py        # Pydantic settings (env-based)
│   ├── auth.py          # JWT decoding, user/client resolution, dependencies
│   └── rate_limit.py    # slowapi IP-based rate limiter
├── models/
│   ├── base.py          # SQLAlchemy declarative base, Workflow, Session, SessionTreeNode
│   └── auth.py          # Organization, User, Client, token models
├── schemas/             # Pydantic request/response schemas
└── services/
    ├── auth_service.py  # User/client signup, login, token management
    ├── workflow_service.py  # Workflow CRUD and root hash updates
    ├── session_service.py   # Session creation, Merkle tree building, proofs, verification
    └── merkle.py        # Core Merkle tree implementation (build, proof, verify)

tests/
├── conftest.py          # Test fixtures, auth override
├── test_api.py          # End-to-end API tests
├── test_auth.py         # Auth flow tests
└── test_merkle.py       # Merkle tree unit tests

alembic/                 # Database migrations
```

## How It Works

### Session-Level Merkle Trees

Each session maintains a Merkle tree where leaves are event hashes. Session leaf hashes incorporate a chain of previous hashes, making the structure append-only and tamper-evident.

```
Session Tree
     Root
    /    \
E1_leaf   E2_leaf
   |         |
event_hash  event_hash
```

### Event Hashing

Events are submitted as raw `{ sequence_no, payload }` pairs. The server computes event hashes using SHA-256:

```
event_hash = SHA-256(str(sequence_no) + json.dumps(payload, sort_keys=True, separators=(",", ":")))
```

Raw event data is **never persisted** to the database -- only the hashes are stored as leaves in the session Merkle tree.

### Session Submission Flow

1. A client authenticates via API key and submits events to a workflow
2. Events are sorted by `sequence_no` and hashed using the convention above
3. A session Merkle tree is built from the event hashes; `session_hash` is the root
4. A `leaf_hash` is computed: `SHA-256(session_hash + prev_leaf_hash)` to chain sessions
5. The session is persisted
6. Tree nodes for the session are persisted for proof generation

### Verification

- **Event proof** (`GET .../events/{seq}/proof`): generates a Merkle proof from the event leaf to the session root
- **Stateless verify** (`POST /verify`): verify a proof against a known root hash with no database access

## Configuration

Configuration is loaded from `.env` (see `.env.example`):

| Variable | Default | Description |
|----------|---------|-------------|
| `APP_NAME` | `StateProof` | Application name |
| `DEBUG` | `false` | Enable debug mode and SQL echoing |
| `VERSION` | `0.1.0` | API version |
| `HOST` | `0.0.0.0` | Bind host |
| `PORT` | `8000` | Bind port |
| `CORS_ORIGINS` | `["*"]` | Allowed CORS origins (JSON array) |
| `DATABASE_URL` | `postgresql+asyncpg://...` | Async PostgreSQL connection string |
| `TEST_DATABASE_URL` | `postgresql+asyncpg://...` | Test database connection string |
| `JWT_SECRET_KEY` | `change-me-in-production` | Secret key for JWT signing |
| `JWT_ALGORITHM` | `HS256` | JWT signing algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `15` | Access token lifetime |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `30` | Refresh token lifetime |
