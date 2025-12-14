# Nexus Bank

Modern Django/DRF banking stack with rich risk logging and real-time business metrics (no Celery workers required).

## Highlights
- Strong auth: JWT via SimpleJWT + Djoser, django-axes lockouts, admin/audit trails.
- Risk engine: incidents, login events, throttling, API key logging, anomaly detection.
- Banking core: users/accounts/cards, transfers (internal/external), bill payments.
- Analytics: daily/weekly/monthly KPIs, country/currency metrics, active user tracking (inline updates).
- API docs: DRF Spectacular (Swagger/Redoc) at `/api/schema/*`.

## Quickstart (dev)
```bash
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver 0.0.0.0:8000
```

## Environment
Create a `.env` (or export vars) for secrets and settings:
```
DJANGO_SECRET_KEY=change-me
DJANGO_DEBUG=True
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=you@example.com
EMAIL_HOST_PASSWORD=app-password
IPINFO_TOKEN=your_ipinfo_token_optional
RISK_ALLOWED_API_KEYS=key1,key2
RISK_BLACKLISTED_IPS=1.2.3.4,5.6.7.8
FRONTEND_URL=http://localhost:3000
```

## Risk & Security
- Admin/risk audit: incidents, login events, admin actions (`risk` app).
- Throttling with logged rate-limit hits (`risk.throttling`).
- CSRF failure handler: `risk.views.csrf_failure_view`.
- HTTPS-ready settings: HSTS/secure cookies auto-enabled when `DJANGO_DEBUG` is false.
- API key logging middleware for suspicious usage.

## API Surface
- Auth: `auth/jwt/create`, `auth/jwt/refresh`, `auth/logout`, Djoser endpoints under `/auth/`.
- Accounts/cards/transfers/bills: see `api/urls.py`.
- Risk dashboards: `/risk/incidents`, `/risk/logins`, `/risk/kpis`.
- Business metrics (staff-only): `/business/*` (daily, weekly, monthly, country, currency, active, overview).
- Docs: `/api/schema/`, `/api/schema/swagger-ui/`, `/api/schema/redoc/`.

## Testing
```bash
python manage.py test
```

## Models at a Glance
- `api`: User (email + country), Account, Card, Transaction (status/fee/idempotency), Biller, BillPayment.
- `risk`: Incident, LoginEvent (+ logging helpers).
- `business`: Daily metrics, country/currency metrics, active user tracking, derived weekly/monthly summaries on read.

## Deployment Tips
- Set `DJANGO_DEBUG=False` and unique `DJANGO_SECRET_KEY`.
- Serve via gunicorn/uvicorn behind Nginx with TLS.
- Run `collectstatic` to serve static assets.
- Ensure allowed hosts and CORS origins are set for your domains.

## Diagrams
- Data model graph: `models.dot` (render with Graphviz).
- Schema overview: `schema.yml` (for quick reference).
