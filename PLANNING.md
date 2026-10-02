# OtterThanks - Planning & Architecture Document

**OtterThanks** is the kudos and appreciation web application for **Up-A-Creek Robotics** (FRC Team 1619). It provides an intuitive, Material 3 themed interface where students, mentors, parents, and team members can submit appreciation messages for an individual or the entire team. 

Submitted kudos are stored in a PostgreSQL database. A downstream microservice periodically inspects this database to format and post these kudos into the team's `#kudos` Slack channel.

---

## 1. System Architecture

```
                      +-----------------------------+
                      |       Web Browser           |
                      |   (React + Material 3)      |
                      +--------------+--------------+
                                     |
                         HTTP / REST | (JSON Payload)
                                     v
                      +-----------------------------+
                      |     FastAPI Web Service     |
                      |  - Serves React Frontend    |
                      |  - Validates Kudos Payload  |
                      +--------------+--------------+
                                     |
                            SQLAlchemy (Async)
                                     |
                                     v
                      +-----------------------------+
                      |     PostgreSQL Database     |
                      |  - kudos table              |
                      +-----------------------------+
                                     ^
                                     | (Reads 'pending' kudos)
                      +--------------+--------------+
                      |   Slack Bot Microservice    |
                      |    (External / Future)      |
                      +-----------------------------+
```

---

## 2. Technology Stack

- **Frontend:** React 18+ (TypeScript, Vite), Vanilla CSS implementing Material Design 3 (M3) design tokens and styles.
- **Backend:** Python 3.11+, FastAPI, Uvicorn, SQLAlchemy (asyncio), asyncpg, Pydantic v2.
- **Database:** PostgreSQL 16.
- **Containerization:** Docker multi-stage build + Docker Compose orchestration.

---

## 3. Database Schema

### Table: `kudos`

| Column | Type | Constraints / Defaults | Description |
|---|---|---|---|
| `id` | `INTEGER` | PRIMARY KEY, AUTOINCREMENT | Unique identifier |
| `recipient_type` | `VARCHAR(20)` | NOT NULL | `'individual'` or `'team'` |
| `recipient_name` | `VARCHAR(100)` | NULLABLE | Name of the person (NULL if recipient_type is `'team'`) |
| `message` | `TEXT` | NOT NULL | Kudos message body |
| `sender_name` | `VARCHAR(100)` | NOT NULL DEFAULT `'Anonymous'` | Signature / sender identity |
| `slack_status` | `VARCHAR(20)` | NOT NULL DEFAULT `'pending'` | Processing status: `'pending'`, `'sent'`, `'failed'` |
| `slack_sent_at` | `TIMESTAMP WITH TIME ZONE` | NULLABLE | Timestamp when sent to Slack |
| `created_at` | `TIMESTAMP WITH TIME ZONE` | NOT NULL DEFAULT `NOW()` | Timestamp when kudos was submitted |

---

## 4. API Endpoints

- `POST /api/kudos`: Submit a kudos entry (accepts JSON with `recipient_type`, `recipient_name`, `message`, and `sender_name`).
- `GET /api/kudos`: List submitted kudos with optional filtering (`status=pending`, pagination).
- `GET /api/kudos/{id}`: Retrieve a specific kudos entry.
- `PATCH /api/kudos/{id}/status`: Update `slack_status` and `slack_sent_at` (used by the Slack microservice).
- `GET /api/health`: Health check endpoint for Docker container and database connectivity.

---

## 5. Material 3 Design Specifications

- **Theme & Colors:**
  - Up-A-Creek Robotics branding: Navy Blue (`#003366` / `#1565C0`), Warm Gold (`#FFB300` / `#FFA000`), neutral surface containers (`#FFFFFF` light mode / `#1E1E1E` dark mode).
- **Layout & Components:**
  - **Header:** Branded app bar with Up-A-Creek Robotics OtterThanks logo.
  - **Recipient Switch:** Material 3 Segmented Button or Filter Chips to toggle between "The Whole Team" and "A Specific Person".
  - **Recipient Name Field:** Outlined text input with floating label (only active when "A Specific Person" is selected).
  - **Message Field:** Outlined multiline text area with character counter and clear helper text.
  - **Signature Field:** Outlined text input with "Keep it Anonymous" quick-select toggle.
  - **Submit Button:** Filled primary button with loading indicator during submission.
  - **Snackbar / Toast:** Material 3 notification banner confirming submission.

---

## 6. Project Directory Layout

```
otterthanks/
├── docker-compose.yml
├── Dockerfile
├── .dockerignore
├── .gitignore
├── README.md
├── PLANNING.md
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py              # FastAPI app and static file mounts
│   │   ├── database.py          # SQLAlchemy async session & engine
│   │   ├── models.py            # SQLAlchemy Kudos model
│   │   ├── schemas.py           # Pydantic schemas
│   │   ├── config.py            # App settings (DB URL, limits)
│   │   └── routers/
│   │       ├── kudos.py         # Kudos submission & listing endpoints
│   │       └── health.py        # Healthcheck endpoint
│   ├── requirements.txt
│   └── tests/
│       └── test_kudos.py
├── frontend/
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   ├── index.html
│   ├── public/
│   │   └── logo.png
│   └── src/
│       ├── main.tsx
│       ├── App.tsx
│       ├── App.css              # Material 3 tokens & layout
│       └── components/
│           ├── Header.tsx
│           ├── KudosForm.tsx
│           └── Toast.tsx
```

---

## 7. Implementation Roadmap

1. **Scaffold Project Configs & Documentation:**
   - Create `PLANNING.md` and `README.md`.
   - Setup `.gitignore` and `.dockerignore`.
2. **Backend Development (FastAPI + PostgreSQL):**
   - Write `requirements.txt` and FastAPI application setup.
   - Configure async SQLAlchemy connection, models, and migrations/table initialization.
   - Implement `POST /api/kudos`, `GET /api/kudos`, and `GET /api/health`.
   - Add unit tests for backend endpoints.
3. **Frontend Development (React + TypeScript + Material 3):**
   - Scaffold Vite React project.
   - Implement Material 3 CSS styling and design tokens.
   - Build form components, validation, and toast notifications.
   - Connect frontend to backend API.
4. **Docker & Compose Integration:**
   - Multi-stage `Dockerfile` (frontend build + FastAPI runner).
   - `docker-compose.yml` orchestrating `web` and `db` services with persistent volumes.
   - Verification and end-to-end testing.
