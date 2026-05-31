# StateProof API

Cryptographic proof of state for automated workflows using Merkle trees. Each workflow maintains an append-only Merkle tree of sessions, and each session maintains its own Merkle tree of events. This allows tamper-evident verification that no event or session has been altered after the fact.

## Features

- **Merkle tree integrity** -- every session and event is hashed into a Merkle tree; proofs can be generated and verified independently
- **Multi-tenant** -- organizations, users, and API-key clients with scoped access
- **User signup with invite flow** -- first user in an org is auto-approved; subsequent users require approval via an invite token
- **JWThe following changes must be applied to the existing StateProof 
FastAPI implementation.

## Change 1 — Two separate tree node tables (not one shared)

Remove any single tree_nodes table with owner_type discriminator.
Replace with two dedicated tables:

### SessionTreeNode
  __tablename__ = "session_tree_nodes"
  id          UUID        PK
  session_id  UUID        FK -> sessions
  hash        VARCHAR(64)
  left_hash   VARCHAR(64) nullable
  right_hash  VARCHAR(64) nullable
  parent_hash VARCHAR(64) nullable
  level       INTEGER               -- 0 = leaf, max = root
  position    INTEGER               -- left-to-right at this level
  is_leaf     BOOLEAN
  sequence_no INTEGER     nullable  -- which event this leaf represents
                                    -- only when is_leaf = true
  # NO event_id FK — no events table

### WorkflowTreeNode
  __tablename__ = "workflow_tree_nodes"
  id          UUID        PK
  workflow_id UUID        FK -> workflows
  hash        VARCHAR(64)
  left_hash   VARCHAR(64) nullable
  right_hash  VARCHAR(64) nullable
  parent_hash VARCHAR(64) nullable
  level       INTEGER
  position    INTEGER
  is_leaf     BOOLEAN
  session_id  UUID        FK -> sessions nullable
                                    -- only when is_leaf = true

Add Alembic migration for both tables.
Add these indexes:

  -- session_tree_nodes
  CREATE INDEX ON session_tree_nodes(session_id);
  CREATE INDEX ON session_tree_nodes(session_id, level, position);
  CREATE INDEX ON session_tree_nodes(session_id) WHERE is_leaf = true;

  -- workflow_tree_nodes
  CREATE INDEX ON workflow_tree_nodes(workflow_id);
  CREATE INDEX ON workflow_tree_nodes(workflow_id, level, position);
  CREATE INDEX ON workflow_tree_nodes(session_id) WHERE is_leaf = true;

## Change 2 — Session tree built from event hashes

On POST /workflows/{id}/sessions:
  Client submits event_hashes (pre-hashed) not raw events.
  Server builds a session tree from these hashes.
  session_hash = root of session tree (not concat hash).
  SessionTreeNode rows persisted for the session tree.

  Updated SessionCreate schema:
  {
    event_hashes: [{ sequence_no: int, hash: str }]  -- min 1
    status: "completed" | "pending" | "failed"
    started_at: datetime
    ended_at: datetime | null
    meta: dict | null
  }

  Updated submit processing:
  1. Validate each hash is valid sha256 hex string (64 chars)
  2. Sort event_hashes by sequence_no
  3. Build session tree: session_tree = build_tree([h.hash for h in event_hashes])
  4. session_hash = session_tree.get_root()
  5. prev_hash = last session leaf_hash for this workflow ("0"*64 if first)
  6. leaf_hash = sha256(session_hash + prev_hash)
  7. Persist Session row (no events column)
  8. Persist SessionTreeNode rows from session tree
     set sequence_no on leaf nodes to match event_hashes order
  9. Append leaf_hash to workflow tree
  10. Persist WorkflowTreeNode rows
  11. Update workflow.hex_root
  12. Increment workflow.session_count
  All in one transaction.

## Change 3 — Verify accepts raw events OR pre-hashed

Updated VerifyWorkflowRequest:
  Each session item accepts either format:
  {
    session_id: uuid,

    # Option A — client sends raw events (server hashes, discards)
    events?: [{
      sequence_no: int,
      payload: dict
    }]

    # Option B — client already hashed
    event_hashes?: [{
      sequence_no: int,
      hash: str
    }]
  }
  At least one of events or event_hashes must be provided per session.

  Hashing convention when raw events provided:
    event_hash = sha256(
        str(sequence_no) +
        json.dumps(payload, sort_keys=True, separators=(",", ":"))
    )

  CRITICAL: raw event data is NEVER written to DB under any path.
  Hash in memory, use for verification, discard immediately.
  This is the same convention clients use when hashing locally.

  Updated verify processing per session:
  1. If events provided: compute event_hashes server-side using convention above
  2. If event_hashes provided: use directly
  3. Sort by sequence_no
  4. Rebuild session tree: build_tree(hashes)
  5. computed_root = session_tree.get_root()
  6. Load stored session.session_hash from DB
  7. If computed_root != stored session_hash:
       mark invalid, reason = "event log does not match stored session root"
       continue to next session
  8. Get proof_path from WorkflowTreeNode for this session
  9. verify_proof(session.leaf_hash, proof_path, workflow.hex_root)
  10. If proof fails: mark invalid, reason = "session not in workflow tree"
  11. Discard all raw data and computed hashes — nothing written to DB

## Change 4 — Event-level proof endpoint (new)

Add new endpoint:
  GET /api/v1/workflows/{workflow_id}/sessions/{session_id}/events/{sequence_no}/proof
  Auth: JWT user token required

  Walk SessionTreeNode to build proof path for one event leaf:
  1. Find node WHERE session_id = ? AND sequence_no = ? AND is_leaf = true
  2. Walk up tree collecting sibling hash + direction at each level
  3. Stop at root (parent_hash is null)

  Returns EventProofResponse:
  {
    session_id:   uuid,
    sequence_no:  int,
    event_hash:   str,   -- the stored leaf hash for this event
    proof_path:   [{ hash: str, direction: "left"|"right" }],
    session_hash: str    -- use as hex_root in POST /api/v1/verify
  }

  Client verifies a specific event using:
    POST /api/v1/verify
    {
      leaf_hash:  their_computed_event_hash,
      proof_path: from this response,
      hex_root:   session_hash from this response
    }
  Client computes their own event_hash using the same convention:
    sha256(str(sequence_no) + json.dumps(payload, sort_keys, no spaces))

## Change 5 — Remove events storage entirely

Remove from Session model:
  events column (JSONB) if it exists

Session model must NOT store any event data.
Only these fields:
  id, workflow_id, session_hash, leaf_hash, prev_hash,
  event_count, status, started_at, ended_at, metadata

event_count = len(event_hashes) from submit payload.

Drop events table if it exists.
Remove Event model if it exists.
Add Alembic migration for these removals.

## Change 6 — Stateless verify works for both tree levels

POST /api/v1/verify (already exists, public, no auth)
No changes to the endpoint itself.
Add a comment in the code clarifying it works for both:

  # For event-level verify:
  #   leaf_hash = client computed event hash
  #   proof_path = from GET .../events/{seq}/proof
  #   hex_root = session.session_hash
  #
  # For session-level verify:
  #   leaf_hash = session.leaf_hash
  #   proof_path = from GET .../sessions/{id}/proof
  #   hex_root = workflow.hex_root

## Summary of what changes
  - tree_nodes table -> split into session_tree_nodes + workflow_tree_nodes
  - Session submit now builds TWO trees (session tree + workflow tree)
  - SessionCreate.event_hashes replaces SessionCreate.events
  - VerifyWorkflowRequest accepts raw events OR pre-hashed
  - New endpoint: GET .../events/{sequence_no}/proof
  - Session model has no events/payload storage of any kind
  - Event model and events table removed entirely

## What does NOT change
  - Auth model (JWT user vs client token separation)
  - Workflow CRUD endpoints
  - Session list/get endpoints
  - Existing session proof endpoint (workflow level)
  - Stateless POST /api/v1/verify endpoint
  - WorkflowResponse, SessionSubmitResponse schemas
  - Organization, User, Client, Workflow models
  - Hashing: sha256 throughout
  - All existing indexes on other tablesT authentication** -- access tokens (short-lived) and refresh tokens (revocable)
- **API key clients** -- machine-to-machine auth via API keys with key rotation
- **Stateless verification** -- verify any Merkle proof without database access
- **Event types** -- structured events with types (`tool_call`, `decision`, `approval`, `api_call`, `error`, `trigger`) and executors (`agent`, `rpa`, `human`, `integration`, `job`, `system`)

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
| POST | `/auth/approve/{token}` | Approve a pending user via invite token |
| GET | `/auth/clients` | List API key clients |
| POST | `/auth/clients` | Create an API key client |
| DELETE | `/auth/clients/{client_id}` | Delete an API key client |
| POST | `/auth/clients/{client_id}/rotate` | Rotate an API key |
| GET | `/auth/me` | Get current user profile |

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
| GET | `/workflows/{id}/sessions/{sid}/proof` | Any | Get Merkle proof for a session |
| POST | `/workflows/{id}/verify` | Any | Verify multiple sessions against the workflow tree |
| GET | `/workflows/{id}/sessions/{sid}/events` | Any | List events in a session |
| GET | `/workflows/{id}/sessions/{sid}/events/{eid}` | Any | Get event details |
| GET | `/workflows/{id}/sessions/{sid}/events/{eid}/proof` | Any | Get Merkle proof for an event |
| POST | `/workflows/{id}/sessions/{sid}/verify` | Any | Verify events against the session tree |

### Verification

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/verify` | Any | Stateless Merkle proof verification |

## Project Structure

```
src/
├── main.py              # FastAPI app factory and lifespan
├── api/v1/              # API v1 route handlers
│   ├── router.py        # Root router with health check
│   ├── auth.py          # Auth and client management endpoints
│   ├── workflows.py     # Workflow, session, event, and verify endpoints
│   └── verify.py        # Stateless verification endpoint
├── db/                  # Database engine and session setup
├── middleware/
│   ├── config.py        # Pydantic settings (env-based)
│   └── auth.py          # JWT decoding, user/client resolution, dependencies
├── models/
│   ├── base.py          # SQLAlchemy declarative base, Workflow/Session/Event/TreeNode models
│   └── auth.py          # Organization, User, Client, token models
├── schemas/             # Pydantic request/response schemas
└── services/
    ├── auth_service.py  # User/client signup, login, token management
    ├── workflow_service.py  # Workflow CRUD and root hash updates
    ├── session_service.py   # Session creation, Merkle tree building, workflow verification
    ├── event_service.py     # Event batch creation, session tree building, event verification
    └── merkle.py        # Core Merkle tree implementation (build, proof, verify)

tests/
├── conftest.py          # Test fixtures, auth override
├── test_api.py          # End-to-end API tests
└── test_merkle.py       # Merkle tree unit tests

alembic/                 # Database migrations
```

## How It Works

### Merkle Trees

Each workflow maintains a Merkle tree where leaves are session hashes. Each session maintains its own Merkle tree where leaves are event hashes. Leaf hashes incorporate a chain of previous hashes, making the structure append-only and tamper-evident.

```
Workflow Tree                    Session Tree
     Root                           Root
    /    \                         /    \
  N1      N2                  E1_leaf   E2_leaf
 /  \     |                     |         |
S1   S2   S3               event_hash  event_hash
```

### Session Submission Flow

1. A client authenticates via API key and submits events to a workflow
2. Events are sorted by `sequence_no` and hashed (SHA-256)
3. Each event leaf chains to the previous leaf hash (append-only)
4. A session Merkle tree is built from the event leaf hashes
5. The session hash is set to the root of the event tree
6. The session is appended as a leaf to the workflow tree
7. The workflow root hash is updated
8. Tree nodes are persisted for proof generation

### Verification

- **Session proof**: generates a Merkle proof from the session leaf to the workflow root
- **Event proof**: generates a Merkle proof from the event leaf to the session root
- **Workflow verify**: recompute hashes from raw events, verify they match stored hashes and Merkle proofs
- **Stateless verify**: verify a proof against a known root hash with no database access

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
| `JWT_SECRET_KEY` | `change-me-in-production` | Secret key for JWT signing |
| `JWT_ALGORITHM` | `HS256` | JWT signing algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `15` | Access token lifetime |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `30` | Refresh token lifetime |
