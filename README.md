# FLEXDESK Backend

FastAPI REST backend for the FLEXDESK smart workspace booking POC. It uses PostgreSQL, SQLAlchemy, Pydantic, and Uvicorn.

## Requirements

- Python 3.11+
- PostgreSQL running locally
- Database password configured in `.env`

## Install

From this directory:

```powershell
py -3.11 -m venv .venv311
.\.venv311\Scripts\python.exe -m pip install -r requirements.txt
```

## Environment

The backend `.env` contains the PostgreSQL connection. The password is requested as hidden input by `start-flexdesk.ps1` and is not stored in the file.

```env
DATABASE_URL=postgresql+psycopg://postgres@127.0.0.1:5432/flexdesk
ALLOW_DEMO_AUTH=false
MICROSOFT_TENANT_ID=
MICROSOFT_CLIENT_ID=
MICROSOFT_CLIENT_SECRET=
MICROSOFT_REDIRECT_URI=http://127.0.0.1:8002/api/v1/auth/sso/callback
FRONTEND_URL=http://localhost:5174
AUTH_TOKEN_SECRET=
SSO_SESSION_SECRET=
SSO_COOKIE_SECURE=false
```

Register a single-tenant Microsoft Entra ID app with a Web redirect URI matching `MICROSOFT_REDIRECT_URI`. Set the tenant ID, client ID, client secret, and two independently generated random secrets in `.env`. Set `ALLOW_DEMO_AUTH=false` when using SSO. Set `SSO_COOKIE_SECURE=true` when deployed over HTTPS. Never commit `.env` or share the client secret.

For local demo use without SSO, `ALLOW_DEMO_AUTH=true` accepts any submitted email and password. This bypasses credential verification and should remain disabled when SSO is enabled or outside a local demo.

## Start FLEXDESK

```powershell
..\start-flexdesk.ps1
```

Backend URL: `http://127.0.0.1:8002`

Interactive API documentation: `http://127.0.0.1:8002/docs`

Health check: `http://127.0.0.1:8002/health`

## Seed screenshot locations

From this directory, enter the PostgreSQL password at the hidden prompt to synchronize the 24-location master catalog. Entries outside the catalog are removed, along with bookings tied to their workspaces; demo user accounts and preferences are preserved:

```powershell
$securePassword = Read-Host 'PostgreSQL password for user postgres (hidden input)' -AsSecureString
$passwordPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($securePassword)
try {
    $env:PGPASSWORD = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($passwordPointer)
    & '.\.venv311\Scripts\python.exe' seed.py --locations-only
} finally {
    Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($passwordPointer)
}
```

## Remove all location data

To permanently delete every location, floor, bay, workspace, and booking attached to those workspaces while keeping user accounts and preferences, run this from the backend directory:

```powershell
.\.venv311\Scripts\python.exe clear_locations.py --confirm
```

The command prompts for the PostgreSQL password using hidden input.

## Login

When demo auth is disabled, use the email and password stored for a seeded account. The login endpoint is `POST /api/v1/auth/login`.

The frontend stores the returned bearer token and sends it with protected requests.

## Main API areas

- Locations, floors, bays, and workspaces
- Workspace availability
- Booking creation and cancellation
- Booking history
- User preferences
- Recommendations and demand prediction
- Workspace assistant queries
- Utilization analytics
