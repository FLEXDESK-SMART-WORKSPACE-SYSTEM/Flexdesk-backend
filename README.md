# FLEXDESK Backend

FastAPI REST backend for the FLEXDESK smart workspace booking POC. It uses PostgreSQL, SQLAlchemy, Pydantic, and Uvicorn.

## Requirements

- Python 3.11+
- PostgreSQL running locally
- Database password configured in `.env`

## Install

From this directory:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install -r requirements.txt
```

## Environment

The backend `.env` contains the PostgreSQL connection:

```env
DATABASE_URL=postgresql+psycopg://postgres:5432@127.0.0.1:5432/flexdesk
ALLOW_DEMO_AUTH=false
```

## Create and migrate the database

Run the migration runner from the database project:

```powershell
cd "C:\Users\IpshitaDas\Desktop\MTECH Final Year\FlexDesk\Flexdesk-DB"
py migrate.py
```

Seed users, offices, workspaces, preferences, and sample bookings:

```powershell
cd "C:\Users\IpshitaDas\Desktop\MTECH Final Year\FlexDesk\Flexdesk-backend"
py seed.py
```

## Run the backend

```powershell
cd "C:\Users\IpshitaDas\Desktop\MTECH Final Year\FlexDesk\Flexdesk-backend"
py -m uvicorn app.main:app --host 127.0.0.1 --port 8002 --reload
```

Backend URL: `http://127.0.0.1:8002`

Interactive API documentation: `http://127.0.0.1:8002/docs`

Health check: `http://127.0.0.1:8002/health`

## Login

The seeded local account is:

```text
Username: ipshita
Password: 1234
```

The login endpoint is `POST /api/v1/auth/login`. The frontend stores the returned bearer token and sends it with protected requests.

## Main API areas

- Locations, floors, bays, and workspaces
- Workspace availability
- Booking creation and cancellation
- Booking history
- User preferences
- Recommendations and demand prediction
- Workspace assistant queries
- Utilization analytics
