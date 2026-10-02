# 🦦 OtterThanks

> Kudos & appreciation web application for **Up-A-Creek Robotics** (FRC Team 1619).

OtterThanks is a simple, modern Material 3 themed web application that lets students, mentors, parents, and team supporters submit kudos and thank-you messages. Submissions are stored in a PostgreSQL database for consumption by a downstream microservice that broadcasts them to the team's `#kudos` Slack channel.

It also features a **Mentor Portal** protected by **Google Workspace OAuth (OIDC)** and group membership verification, allowing authorized mentors to review, filter, and manage all kudos in the database.

---

## ✨ Features

- **Material 3 Design:** Built with modern Material You / M3 styling tokens, responsive layouts, floating labels, tactile interactions, and dark/light mode compatibility.
- **Flexible Recipient Selection:** Express gratitude to a specific student or mentor, or give kudos to the entire team.
- **Signatures & Anonymity:** Sign your name or choose to remain anonymous with a single click.
- **Mentor Portal & Google Workspace OAuth:** 
  - Mentors authenticate using their team Google Workspace account.
  - Automatically verifies membership against the allowed Google Group (e.g. `mentors@team1619.net` configured in `.env`).
  - Access to a private dashboard to view all kudos, stats (total, pending, delivered), filter by status/search, update Slack status, or delete spam/inappropriate entries.
- **Downstream Slack Ready:** Schema includes `slack_status` (`pending`, `sent`, `failed`) and `slack_sent_at` timestamp flags designed specifically for an automated Slack posting bot.
- **Dockerized Architecture:** Multi-stage build packaging the React frontend and FastAPI backend into a unified container, orchestrated alongside PostgreSQL via Docker Compose.

---

## 🛠️ Tech Stack

- **Frontend:** React 18, TypeScript, Vite, Material 3 (Vanilla CSS).
- **Backend:** Python 3.11+, FastAPI, SQLAlchemy (asyncio), asyncpg, Pydantic v2, PyJWT.
- **Database:** PostgreSQL 16.
- **Auth & Directory:** Google Workspace OAuth 2.0 / OIDC & Google Admin Directory API.
- **DevOps:** Docker, Docker Compose.

---

## ⚙️ Environment Variables & Configuration

Create a `.env` file in the root directory by copying the example:
```bash
cp .env.example .env
```

| Category | Variable | Description | Default / Example |
|---|---|---|---|
| **Database** | `POSTGRES_USER` | PostgreSQL username | `otter` |
| | `POSTGRES_PASSWORD` | PostgreSQL password | `otterpass` |
| | `POSTGRES_DB` | PostgreSQL database name | `otterthanks` |
| **Google OAuth** | `ALLOWED_GOOGLE_GROUP` | **Required group email** for mentor access | `mentors@team1619.org` |
| | `ALLOWED_MENTOR_EMAILS` | Optional comma-separated mentor emails (bypasses Admin SDK limits) | `emilysastranova@team1619.org` |
| | `GOOGLE_CLIENT_ID` | Google Cloud OAuth 2.0 Client ID | `xxx.apps.googleusercontent.com` |
| | `GOOGLE_CLIENT_SECRET` | Google Cloud OAuth 2.0 Client Secret | `GOCSPX-xxx` |
| | `GOOGLE_REDIRECT_URI` | Authorized Redirect URI | `http://localhost:8000/api/auth/callback` |
| **Security** | `SESSION_SECRET_KEY` | Secret key for signing mentor session cookies | *random 64-char string* |
| | `DEV_MODE` | Set to `true` to enable quick mock login for local testing | `false` |
| **Slack** | `SLACK_BOT_TOKEN` | Slack Bot User OAuth Token (`xoxb-...`) | `xoxb-123456789-abcdef` |
| | `SLACK_CHANNEL_ID` | Public Slack Channel ID to post approved kudos into | `C0123456789` |
| | `SLACK_MENTOR_CHANNEL_ID` | Private Slack Channel ID for mentor review buttons (✅ / ❌) | `C9876543210` |
| | `SLACK_SIGNING_SECRET` | Slack Signing Secret for verifying interactive webhook requests | *32-char hex string* |

> **Note on Database Connection:** You do not need to configure a full `DATABASE_URL`. Docker Compose automatically strings together `POSTGRES_USER`, `POSTGRES_PASSWORD`, and `POSTGRES_DB` into the async PostgreSQL connection string (`postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@db:5432/${POSTGRES_DB}`) for the backend service.

---

## 🔐 Google Workspace OAuth & Mentor Group Setup

Mentors log into OtterThanks via Google Workspace OAuth. The application queries the Google Directory API to ensure the user belongs to the designated mentor group.

### Google Cloud Console Configuration
1. Go to [Google Cloud Console](https://console.cloud.google.com/) -> **APIs & Services** -> **Credentials**.
2. Create an **OAuth 2.0 Client ID** (Web application).
3. Under **Authorized redirect URIs**, add:
   - `http://localhost:8000/api/auth/callback` (for local development/Docker)
   - `https://your-domain.com/api/auth/callback` (for production)
4. Enable the **Admin SDK API** in your Google Cloud project so the backend can verify group membership.
5. In your Google Workspace Admin Console, ensure the group (e.g. `mentors@team1619.org`) allows group members to view membership.

---

## 🤖 Slack Bot Setup & Interactive Mentor Review

Mentors can review and release kudos without opening the web dashboard! When a student or mentor submits a kudos, an interactive review card is automatically dispatched to your **private mentor Slack channel** with **✅ Approve & Release** and **❌ Reject** buttons.

### 1. Create a Slack App
1. Go to [api.slack.com/apps](https://api.slack.com/apps) and click **Create New App** -> **From scratch**.
2. Name your app (e.g., `OtterThanks`) and select your workspace (e.g., `Up-A-Creek Robotics`).

### 2. Configure Bot Scopes
1. Under **Features**, select **OAuth & Permissions**.
2. Scroll to **Scopes** -> **Bot Token Scopes**, and add:
   - `chat:write` (Allows posting messages)
   - `chat:write.public` (Allows posting to public channels without needing to manually invite the bot)

### 3. Install to Workspace & Copy Tokens
1. Scroll up on the **OAuth & Permissions** page and click **Install to Workspace**.
2. Allow permissions and copy the **Bot User OAuth Token** (starts with `xoxb-`).
3. Set this token as `SLACK_BOT_TOKEN` in your `.env`.
4. Go to **Settings** -> **Basic Information** -> **App Credentials** and copy the **Signing Secret**.
5. Set this secret as `SLACK_SIGNING_SECRET` in your `.env`.

### 4. Enable Interactivity (For ✅ / ❌ Buttons)
1. In your Slack App settings, click **Interactivity & Shortcuts** in the left sidebar.
2. Toggle **Interactivity** to **On**.
3. In the **Request URL** field, enter your public OtterThanks interactions endpoint:
   - `https://your-domain.com/api/slack/interactions` (or your ngrok / Cloudflare tunnel URL for local dev).
4. Click **Save Changes**.

### 5. Get Channel IDs
1. **Public Kudos Channel (`SLACK_CHANNEL_ID`):** Right-click `#kudos` -> **View channel details** -> copy the **Channel ID** at the bottom.
2. **Private Mentor Channel (`SLACK_MENTOR_CHANNEL_ID`):** 
   - Create or open your private mentor review channel (e.g., `#mentor-kudos-review`).
   - Invite your bot into the private channel by typing: `/invite @OtterThanks`.
   - Right-click the channel name -> **View channel details** -> copy the **Channel ID** at the bottom.
3. Save all IDs in your `.env`.

When a kudos is submitted:
- The private mentor channel receives the review card with **✅ Approve & Release** and **❌ Reject** buttons.
- Clicking **✅** broadcasts the kudos to `#kudos` and updates the review card to show who released it and when.
- Clicking **❌** dismisses the kudos and marks it as rejected.

---

## 🚀 Quickstart with Docker

### Prerequisites
- [Docker](https://docs.docker.com/get-docker/) & [Docker Compose](https://docs.docker.com/compose/) installed.

### Running OtterThanks

1. **Clone and Configure:**
   ```bash
   git clone <repo-url>
   cd otterthanks
   cp .env.example .env
   # Edit .env with your Google OAuth credentials and group
   ```

2. **Start Services:**
   ```bash
   docker compose up --build -d
   ```

3. **Access the Application:**
   - **Kudos Submission Form:** [http://localhost:8000](http://localhost:8000)
   - **Mentor Portal:** [http://localhost:8000/mentors](http://localhost:8000/mentors)
   - **API Docs (Swagger UI):** [http://localhost:8000/docs](http://localhost:8000/docs)
   - **Healthcheck:** [http://localhost:8000/api/health](http://localhost:8000/api/health)

4. **Stop Services:**
   ```bash
   docker compose down
   ```

---

## 🗄️ Database Schema & Slack Microservice Integration

OtterThanks stores kudos in a PostgreSQL table named `kudos`:

```sql
CREATE TABLE kudos (
    id SERIAL PRIMARY KEY,
    recipient_type VARCHAR(20) NOT NULL,    -- 'individual' or 'team'
    recipient_name VARCHAR(100),            -- Name if individual, NULL if team
    message TEXT NOT NULL,                  -- Thank you message
    sender_name VARCHAR(100) NOT NULL,      -- Signee or 'Anonymous'
    slack_status VARCHAR(20) DEFAULT 'pending', -- 'pending' | 'sent' | 'failed'
    slack_sent_at TIMESTAMPTZ,              -- Set when posted to Slack
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### How the Slack Microservice Works:
1. Connects to the same PostgreSQL database.
2. Polls for records where `slack_status = 'pending'`.
3. Posts a formatted message (Block Kit) into `#kudos`.
4. Updates the record in PostgreSQL:
   ```sql
   UPDATE kudos
   SET slack_status = 'sent', slack_sent_at = NOW()
   WHERE id = :kudos_id;
   ```

---

## 📁 Repository Structure

```
otterthanks/
├── docker-compose.yml       # Production/local compose setup
├── Dockerfile               # Multi-stage build for frontend & backend
├── .env.example             # Example environment configuration
├── PLANNING.md              # Detailed architecture and planning spec
├── README.md                # Project documentation
├── backend/
│   ├── app/
│   │   ├── main.py          # FastAPI application entrypoint
│   │   ├── database.py      # Async SQLAlchemy engine & session
│   │   ├── models.py        # Database models
│   │   ├── schemas.py       # Pydantic validation schemas
│   │   ├── config.py        # Environment settings (OAuth, groups, DB)
│   │   ├── auth.py          # Session tokens & Google group checking
│   │   └── routers/
│   │       ├── auth.py      # OAuth login, callback, session endpoints
│   │       ├── mentor.py    # Protected mentor kudos dashboard endpoints
│   │       ├── kudos.py     # Kudos submission & public endpoints
│   │       └── health.py    # Health check
│   ├── requirements.txt     # Python dependencies
│   └── tests/
│       └── test_kudos.py    # Backend test suite (100% pass)
└── frontend/
    ├── package.json
    ├── vite.config.ts
    ├── src/
    │   ├── App.tsx          # Main React component & router
    │   ├── App.css          # Material 3 styling & mentor dashboard styles
    │   └── components/
    │       ├── Header.tsx   # App Bar with navigation to Mentor Portal
    │       ├── KudosForm.tsx # Student kudos submission form
    │       ├── MentorDashboard.tsx # Mentor dashboard with Google sign-in & table
    │       └── Toast.tsx    # Material 3 snackbars
    └── index.html
```

---

## 📄 License

This project is licensed under the [GNU General Public License v3.0](LICENSE) (GPL-3.0). See the [LICENSE](LICENSE) file for the full license text.

Maintained for **Up-A-Creek Robotics** (FRC Team 1619).
