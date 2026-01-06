# Nexus Bank - Complete Technical and Business Audit

**Audit Date:** January 6, 2026  
**Auditor:** Senior Technical Auditor  
**Project:** Nexus Bank Digital Banking Platform  
**Scope:** Backend Codebase (Django REST Framework)

---

## Table of Contents
1. [Project Overview](#1-project-overview)
2. [Business Logic Breakdown](#2-business-logic-breakdown)
3. [System Architecture](#3-system-architecture)
4. [Backend Deep Dive](#4-backend-deep-dive)
5. [Frontend Deep Dive](#5-frontend-deep-dive)
6. [Data and Metrics](#6-data-and-metrics)
7. [Risk Management Logic](#7-risk-management-logic)
8. [Authentication and Authorization](#8-authentication-and-authorization)
9. [AI / BI Advisor](#9-ai--bi-advisor)
10. [Known Issues and Technical Debt](#10-known-issues-and-technical-debt)
11. [Improvement Recommendations](#11-improvement-recommendations)
12. [Final Summary](#12-final-summary)

---

## 1. Project Overview

### Project Name
**Nexus Bank** - A digital banking simulation platform

### Core Business Problem It Solves
Nexus Bank provides a complete digital banking experience for educational and demonstration purposes. It simulates:
- Multi-currency account management (JOD, USD, EUR)
- Internal and external fund transfers
- Bill payment processing
- Card management (debit/credit)
- Risk detection and fraud prevention
- Business intelligence and analytics dashboards

### Target Users
1. **End Users (Customers):** Individuals managing bank accounts, transfers, and bill payments
2. **Administrators:** Bank staff monitoring transactions, users, and security incidents
3. **Stakeholders:** Business analysts reviewing performance metrics and AI-generated insights

### Business Value
- **Educational Platform:** Demonstrates real-world banking system architecture
- **Academic Project:** Suitable for graduation projects requiring FinTech implementations
- **Risk Simulation:** Showcases fraud detection, anomaly monitoring, and incident response

### High-Level System Goal
Provide a fully functional digital banking backend with:
- Secure 2FA authentication
- Atomic transaction processing with currency conversion
- Real-time risk monitoring and incident logging
- AI-powered business intelligence advisors
- Administrative controls for user/account management

---

## 2. Business Logic Breakdown

### 2.1 User Lifecycle

#### Signup Flow
```
User Registration (Djoser) → Email + Password → Profile Creation → Account Ready
```

**Implementation Location:** `api/serializers.py` - `UserCreateSerializer`

**Fields Required:**
- Email (unique identifier, replaces username)
- Password
- First name
- Country (optional)

**Why This Design:**
- Email-based authentication is modern and user-friendly
- No username reduces friction and potential for typosquatting
- Country field enables geo-based analytics and risk detection

#### Login Flow (Two-Factor Authentication)
```
Step 1: POST /auth/login/init/
  ↓
  Validate credentials → Generate 6-digit OTP → Send via Email
  ↓
Step 2: POST /auth/login/verify/
  ↓
  Validate OTP → Issue JWT tokens (access + refresh)
```

**Implementation Location:** `api/views.py` - `LoginInitView`, `LoginVerifyView`

**Why 2FA Exists:**
- Protects against credential stuffing attacks
- Adds layer of security for financial transactions
- Required for modern banking compliance standards

#### Status Changes
| Status | Trigger | Effect |
|--------|---------|--------|
| `is_active=True` | Default on signup | User can log in and transact |
| `is_active=False` | Admin blocks user | All access denied, existing tokens still valid until expiry |
| `is_online=True` | Successful login | Indicates current session |
| `is_online=False` | Logout or timeout | Session ended |

**Critical Note:** Blocking a user (`is_active=False`) does NOT invalidate existing JWT tokens. The `AdminTerminateSessionView` must be called separately to blacklist tokens.

---

### 2.2 Transactions Lifecycle

#### Internal Transfer (Same User)
```
POST /api/transfers/internal/
  ↓
  Validate: sender + receiver owned by user
  ↓
  Check: amount <= withdrawal_limit
  ↓
  If amount > 500: Create PENDING_OTP → Send OTP → Wait for confirmation
  If amount <= 500: Execute atomically → SUCCESS
```

#### External Transfer (Different Users)
```
POST /api/transfers/external/
  ↓
  Validate: sender owned by user, receiver exists
  ↓
  Calculate: 1% fee (EXTERNAL_TRANSFER_FEE_PERCENTAGE)
  ↓
  Same OTP logic for high-value transfers
  ↓
  Execute with currency conversion if needed
```

**Implementation Location:** `api/models.py` - `Transaction.execute_transaction()`

#### Transaction Execution (Atomic)
```python
# Simplified flow from Transaction.execute_transaction()
with transaction.atomic():
    1. Lock sender and receiver accounts (SELECT FOR UPDATE)
    2. Validate same-account check
    3. Validate positive amount
    4. Check sufficient balance (including fees)
    5. Perform currency conversion if needed
    6. Update balances atomically (F expressions)
    7. Record balance snapshots
```

**Why Atomic Execution:**
- Prevents race conditions
- Ensures data consistency
- Uses database-level locking to prevent double-spending

#### Transaction Statuses
| Status | Meaning |
|--------|---------|
| `SUCCESS` | Completed and balances updated |
| `FAILED` | Validation failed, no balance change |
| `REVERSED` | Previously successful, now refunded |
| `PENDING_OTP` | Awaiting high-value transfer confirmation |

---

### 2.3 Risk Detection Logic

The system logs security incidents across multiple threat vectors:

#### Authentication Threats
| Event | Severity | Trigger |
|-------|----------|---------|
| Failed login attempt | Low | Invalid credentials |
| Brute-force suspected | High | 5+ failures on same email in 10 minutes |
| Credential stuffing | High | 5+ failures from same IP targeting 3+ accounts |
| Impossible travel | High | Login from different country within 1 hour |
| Login from new country | Medium | First login from a country |
| Login from new device | Medium | User-agent change |
| Login at unusual hour | Low | Login between midnight and 5 AM |

**Implementation Location:** `risk/auth_logging.py`

#### Transaction Threats
| Event | Severity | Trigger |
|-------|----------|---------|
| Large transaction | Medium | Amount >= 10,000 (configurable) |
| Unusual transaction size | Medium | Amount >= 5x user's 30-day average |
| First transfer to beneficiary | Medium | New receiver account |
| Multiple transfers in short window | Medium | 5+ transfers in 5 minutes |
| Suspicious velocity | High | 10+ transactions OR 50,000 amount in 15 minutes |
| Transaction at unusual hour | Low | Before 5 AM |
| Transaction from blacklisted IP | High | IP in `RISK_BLACKLISTED_IPS` |
| Transaction via anonymizer | Medium | Tor/VPN headers detected |
| Transaction from new country | High | Different country within 2 hours of login |

**Implementation Location:** `risk/transaction_logging.py`

---

### 2.4 Actions Logic (Block / Freeze / Terminate)

All admin actions are logged to the `Incident` model for audit compliance.

#### User Block
```
POST /api/admin/users/{id}/block/
  ↓
  Set user.is_active = False
  ↓
  Log: "Admin Action: BLOCK_USER"
```
**Effect:** User cannot log in with new credentials, but existing JWTs remain valid.

#### User Unblock
```
POST /api/admin/users/{id}/unblock/
  ↓
  Set user.is_active = True
  ↓
  Log: "Admin Action: UNBLOCK_USER"
```

#### Account Freeze
```
POST /api/admin/accounts/{account_number}/freeze/
  ↓
  Set account.is_active = False
  ↓
  Log: "Admin Action: FREEZE_ACCOUNT"
```
**Effect:** Account cannot be used for sending or receiving transfers.

#### Account Unfreeze
```
POST /api/admin/accounts/{account_number}/unfreeze/
  ↓
  Set account.is_active = True
  ↓
  Log: "Admin Action: UNFREEZE_ACCOUNT"
```

#### Session Termination
```
POST /api/admin/users/{id}/terminate-session/
  ↓
  Find all OutstandingTokens for user
  ↓
  Add each to BlacklistedToken table
  ↓
  Log: "Admin Action: TERMINATE_SESSION"
```
**Effect:** All existing JWTs are invalidated immediately.

**Implementation Location:** `api/views_admin.py`

---

### 2.5 Admin vs Normal User Permissions

| Endpoint | Normal User | Admin (is_staff=True) |
|----------|-------------|----------------------|
| `/api/accounts` | Own accounts only | Own accounts only |
| `/api/admin/accounts/` | 403 Forbidden | All accounts |
| `/api/admin/users/{id}/block/` | 403 Forbidden | Allowed |
| `/business/daily/` | 403 Forbidden | Allowed |
| `/risk/incidents/` | 403 Forbidden | Allowed |

**Permission Implementation:**
- DRF's `IsAdminUser` permission class checks `user.is_staff`
- JWT authentication required for all protected endpoints
- CSRF exempt for API endpoints (JWT-only auth)

---

## 3. System Architecture

### 3.1 Technology Stack Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         FRONTEND                                 │
│  React.js + React Router + Axios/Fetch                          │
│  - Hosted on Vercel/Netlify                                     │
│  - nexus-banking.com                                            │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼ HTTPS
┌─────────────────────────────────────────────────────────────────┐
│                         BACKEND                                  │
│  Django 4.x + Django REST Framework                             │
│  - api.nexus-banking.com                                        │
│  - SQLite (Development) / PostgreSQL (Production)              │
│  - JWT Authentication (SimpleJWT)                               │
│  - Daphne ASGI Server (WebSocket support)                       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    EXTERNAL SERVICES                             │
│  - Google OAuth (allauth)                                       │
│  - Google Gemini AI (business + risk analysis)                  │
│  - SMTP Email (Gmail)                                           │
│  - IPInfo API (geo-location)                                    │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 Request Flow Mental Model

```
1. User submits transfer request from React frontend
   ↓
2. Request hits Django backend with JWT in Authorization header
   ↓
3. JWTAuthentication middleware validates token
   ↓
4. View processes request:
   a. Serializer validates data
   b. Check ownership and limits
   c. If high-value: create PENDING_OTP, send email OTP
   d. If normal: execute atomic transaction
   ↓
5. Signal fires: log_transaction_event() → creates Incident if anomalous
   ↓
6. Signal fires: record_transaction() → updates DailyBusinessMetrics
   ↓
7. Response returned to frontend
```

### 3.3 Frontend Stack and Responsibility

**Stack:** React.js with JavaScript (not TypeScript)

**Responsibilities:**
- UI rendering and user interaction
- JWT token management (localStorage)
- API calls to backend
- Real-time state updates
- Admin dashboard visualization

**Key Frontend Files:**
- `LoginPage.jsx` - 2FA login flow
- `AdminDashboard.jsx` - Admin analytics and controls
- `HomeBank.jsx` - User dashboard
- `TransferMoneyPage.jsx` - Transfer interfaces

### 3.4 Backend Stack and Responsibility

**Stack:**
- **Framework:** Django 4.x + Django REST Framework
- **Auth:** SimpleJWT + django-allauth + djoser
- **Database:** SQLite (dev), designed for PostgreSQL (prod)
- **ASGI:** Daphne (WebSocket support via Django Channels)

**Responsibilities:**
- Authentication and authorization
- Business logic execution
- Data persistence
- Risk monitoring and logging
- API documentation (OpenAPI/Swagger)
- AI analysis integration

### 3.5 AI / BI Components

| Component | Purpose | Implementation |
|-----------|---------|----------------|
| Business AI Advisor | Analyzes daily/monthly metrics, generates insights | `business/ai.py` |
| Risk AI Analyzer | Analyzes security incidents, suggests actions | `risk/ai.py` |

Both use **Google Gemini 2.5 Flash** model via the `google-genai` Python SDK.

### 3.6 Database Schema

The system uses 15+ Django models organized into three apps:

**API App (Core Banking):**
- `User` - Custom user with email auth
- `UserProfile` - Extended profile data
- `UserAddress` - Physical addresses
- `Account` - Bank accounts with multi-currency support
- `Card` - Debit/credit cards
- `Transaction` - Transfer records
- `Biller` - Bill payment vendors
- `BillPayment` - Bill payment records
- `Notification` - User notifications
- `OTPVerification` - Login OTP codes
- `TransferOTP` - High-value transfer OTP codes

**Risk App (Security):**
- `Incident` - Security events and anomalies
- `LoginEvent` - Authentication attempts

**Business App (Analytics):**
- `DailyBusinessMetrics` - Daily KPIs
- `WeeklySummary` - Weekly aggregates
- `MonthlySummary` - Monthly aggregates
- `CountryUserMetrics` - Geo-based metrics
- `CurrencyMetrics` - Currency-based metrics
- `ActiveUserWindow` - DAU/WAU/MAU tracking
- `DailyActiveUser` - Per-user daily activity
- `DailyAIInsight` - AI-generated daily reports
- `MonthlyAIInsight` - AI-generated monthly reports

### 3.7 External Services

| Service | Purpose | Configuration |
|---------|---------|---------------|
| Google OAuth | Social login | `SOCIALACCOUNT_PROVIDERS` in settings |
| Google Gemini | AI analysis | `GEMINI_API_KEY` environment variable |
| Gmail SMTP | Email delivery (OTP, notifications) | `EMAIL_HOST_*` environment variables |
| IPInfo | Geo-location for risk detection | `IPINFO_TOKEN` environment variable |

---

## 4. Backend Deep Dive

### 4.1 Folder Structure

```
back/
├── api/                    # Core banking API
│   ├── models.py          # User, Account, Transaction, etc.
│   ├── serializers.py     # DRF serializers
│   ├── views.py           # User-facing endpoints
│   ├── views_admin.py     # Admin-only endpoints
│   ├── consumers.py       # WebSocket handlers
│   ├── signals.py         # Post-save hooks
│   ├── urls.py            # API routes
│   ├── convert_currency.py # FX conversion functions
│   └── middleware.py      # Request logging
│
├── business/              # Analytics and BI
│   ├── models.py          # Metrics models
│   ├── services.py        # Incremental metric updates
│   ├── views.py           # Metrics endpoints
│   ├── views_ai.py        # AI advisor endpoints
│   ├── ai.py              # Gemini integration
│   ├── reporting.py       # Report generation
│   └── management/commands/
│       └── reset_and_seed_analytics.py  # Demo data generator
│
├── risk/                  # Security and monitoring
│   ├── models.py          # Incident, LoginEvent
│   ├── auth_logging.py    # Authentication logging
│   ├── transaction_logging.py # Transaction anomaly detection
│   ├── middleware.py      # Authorization logging
│   ├── views.py           # Risk endpoints
│   ├── ai.py              # Risk AI analysis
│   └── throttling.py      # Rate limiting
│
├── nexus/                 # Project configuration
│   ├── settings.py        # Django settings
│   ├── urls.py            # Root URL config
│   ├── asgi.py            # ASGI application
│   └── wsgi.py            # WSGI application
│
└── db.sqlite3             # SQLite database (17+ MB)
```

### 4.2 Purpose of Each Major File/Module

#### `api/models.py` (626 lines)
The heart of the banking system. Contains:

- **`User`**: Custom user model with email-based auth (`USERNAME_FIELD = 'email'`). No username field.
- **`Account`**: Bank accounts with:
  - Primary key: `account_number` (12-digit string, auto-generated)
  - Types: Savings, Salary, Basic, USD, EUR
  - `maximum_withdrawal_amount`: Per-type limits (all 10,000)
  - Database constraint: `balance >= 0`
- **`Transaction`**: Transfer records with:
  - `execute_transaction()`: Atomic balance updates with locking
  - Currency conversion handling
  - OTP-based high-value transfer flow
- **`TransferOTP`**: Secure OTP implementation with:
  - Hashed code storage (`code_hash` using SHA-256)
  - Attempt tracking (max 3)
  - 5-minute expiry

#### `api/serializers.py` (475 lines)
Request/response validation and transformation:

- **`InternalTransferSerializer`**: Validates same-user transfers, enforces withdrawal limits
- **`ExternalTransferSerializer`**: Handles cross-user transfers, calculates 1% fee
- **`AccountSerializer`**: Masks account numbers, shows currency-converted balances
- **`CardSerializer`**: Exposes only last 4 digits (security)

**Important Business Rule Location:**
```python
HIGH_VALUE_TRANSFER_THRESHOLD = Decimal("500.00")  # Line 16
EXTERNAL_TRANSFER_FEE_PERCENTAGE = Decimal("0.01")  # 1% fee, Line 17
```

#### `api/views.py` (633 lines)
User-facing API endpoints:

- `LoginInitView` / `LoginVerifyView`: 2FA flow
- `InternalTransferListCreateView` / `ExternalTransferListCreateView`: Transfers
- `TransferConfirmationView`: High-value OTP verification
- `NotificationListView` / `NotificationMarkReadView`: Notification management

#### `api/views_admin.py` (347 lines)
Admin-only operations:

- `AdminUserBlockView` / `AdminUserUnblockView`
- `AdminAccountFreezeView` / `AdminAccountUnfreezeView`
- `AdminTerminateSessionView`: Token blacklisting
- `AdminAccountsListView`: All accounts in system

All endpoints use `@csrf_exempt` and `JWTAuthentication` only.

#### `risk/transaction_logging.py` (414 lines)
Transaction anomaly detection. Key function:

```python
def log_transaction_event(*, request, user, transaction,
                          large_txn_threshold=Decimal("10000.00"),
                          rapid_transfer_threshold=5,
                          velocity_count_threshold=10,
                          velocity_amount_threshold=Decimal("50000.00")):
```

Checks performed:
1. Large transaction threshold
2. Unusual size vs 30-day average
3. First transfer to beneficiary
4. Multiple transfers in 5-minute window
5. Velocity pattern (15-minute window)
6. Unusual hours
7. Blacklisted IP
8. Tor/VPN detection
9. Country change after login

#### `risk/auth_logging.py` (655 lines)
Authentication monitoring. Key function:

```python
def log_auth_event(*, request, user, successful, source, attempted_email, failure_reason):
```

On successful login:
- Records LoginEvent
- Sets `is_online = True`
- Checks for new country/device
- Detects impossible travel
- Monitors unusual hours
- Tracks multiple accounts from same IP

On failed login:
- Credential stuffing detection (5 failures, 3+ targets, 10 minutes)
- Brute-force detection (5 failures on same email)

#### `business/services.py` (279 lines)
Incremental metrics updates. Called synchronously (no Celery):

- `record_transaction()`: Updates daily metrics on each transaction
- `record_bill_payment()`: Bill payment metrics
- `record_user_signup()`: New user counts
- `record_login_event()`: Active user tracking (DAU/WAU/MAU)

**Important:** All updates use `SELECT FOR UPDATE` to prevent race conditions.

#### `business/ai.py` (264 lines)
Google Gemini integration for business insights:

- `analyze_business()`: General metrics analysis
- `explain_daily_performance()`: Day-over-day comparison
- Strict prompting to enforce read-only advisory role

#### `risk/ai.py` (141 lines)
Risk incident analysis:

- `determine_action()`: Deterministic action recommendation (terminate/freeze/block/monitor)
- `analyze_incident()`: Gemini-powered threat assessment
- Always returns action recommendation even if AI fails

### 4.3 Models and Field Meanings

#### User Model
| Field | Type | Purpose |
|-------|------|---------|
| email | EmailField (unique) | Login identifier |
| is_online | Boolean | Current session status |
| is_active | Boolean | Account enabled/disabled |
| is_staff | Boolean | Admin access |
| country | CharField | Geo-location for analytics |

#### Account Model
| Field | Type | Purpose |
|-------|------|---------|
| account_number | CharField(12) PK | Unique identifier |
| type | Enum | Savings/Salary/Basic/USD/EUR |
| balance | Decimal(12,2) | Current balance |
| is_active | Boolean | Frozen/active status |
| currency | Enum | JOD/USD/EUR |

#### Transaction Model
| Field | Type | Purpose |
|-------|------|---------|
| sender_account | FK to Account | Source account |
| receiver_account | FK to Account | Destination account |
| amount | Decimal(12,2) | Transfer amount |
| fee_amount | Decimal(12,2) | Applied fee (1% external) |
| status | Enum | SUCCESS/FAILED/REVERSED/PENDING_OTP |
| idempotency_key | CharField | Duplicate prevention |
| sender_balance_after | Decimal | Snapshot for audit |
| receiver_balance_after | Decimal | Snapshot for audit |

#### Incident Model
| Field | Type | Purpose |
|-------|------|---------|
| user | FK to User (nullable) | Associated user |
| ip | GenericIPAddress | Source IP |
| country | CharField | Geo-location |
| event | CharField | Event description |
| severity | Enum | low/medium/high/critical |
| details | JSONField | Structured metadata |
| gemini_analysis | TextField | AI-generated response |
| timestamp | DateTime | Event time |

### 4.4 Business Rules Enforced in Backend

1. **Non-negative Balance Constraint**
   - Location: `Account` model, database check constraint
   - `models.CheckConstraint(check=Q(balance__gte=0), name='account_balance_nonnegative')`

2. **Positive Transaction Amount**
   - Location: `Transaction` model, database check constraint
   - `models.CheckConstraint(check=Q(amount__gt=0), name='positive_transaction_amount')`

3. **Withdrawal Limits**
   - Location: `InternalTransferSerializer.validate()`, `ExternalTransferSerializer.validate()`
   - Limit: 10,000 per account type

4. **High-Value Transfer OTP**
   - Location: `InternalTransferListCreateView.create()`, `ExternalTransferListCreateView.create()`
   - Threshold: 500

5. **External Transfer Fee**
   - Location: `ExternalTransferSerializer.create()`
   - Rate: 1%

6. **Same-Account Transfer Prevention**
   - Location: `Transaction.execute_transaction()`
   - Raises ValueError

7. **Inactive Account Filter**
   - Location: Serializer `__init__` methods
   - Only `is_active=True` accounts appear in querysets

### 4.5 Security Decision Points

| Decision | Location | Mechanism |
|----------|----------|-----------|
| Authentication | Views | `permission_classes`, `authentication_classes` |
| Admin-only access | `views_admin.py` | `IsAdminUser` permission |
| OTP validation | `TransferOTP.verify()` | Hashed comparison + attempt limit |
| Rate limiting | `settings.py` | DRF throttle classes |
| CSRF exemption | API views | `@csrf_exempt`, JWT-only auth |
| Token blacklisting | `AdminTerminateSessionView` | SimpleJWT blacklist |
| Brute-force protection | `settings.py` | Django Axes (15 failures, 1 hour lockout) |

### 4.6 Data Validation Points

| Validation | Location | Method |
|------------|----------|--------|
| Email format | `LoginStepOneSerializer` | `serializers.EmailField` |
| OTP length | `LoginStepTwoSerializer` | `min_length=6, max_length=6` |
| Positive amount | Transfer serializers | `min_value=Decimal("0.01")` |
| Account ownership | Serializer `__init__` | Filtered queryset |
| Withdrawal limits | Serializer `validate()` | Comparison to `maximum_withdrawal_amount` |
| Idempotency | Serializer `create()` | Lookup by `idempotency_key` |

---

## 5. Frontend Deep Dive

### 5.1 Pages and Dashboards

Based on the open documents and conversation history:

| Page | Purpose | Backend Endpoint |
|------|---------|-----------------|
| `LoginPage.jsx` | 2FA login flow | `/auth/login/init/`, `/auth/login/verify/` |
| `AdminDashboard.jsx` | Admin analytics | `/business/daily/`, `/business/monthly/`, `/risk/incidents/` |
| `HomeBank.jsx` | User dashboard | `/api/accounts`, `/api/notifications/` |
| `TransferMoneyPage.jsx` | Money transfers | `/api/transfers/internal/`, `/api/transfers/external/` |
| `PayBillsPage.jsx` | Bill payments | `/api/bill/`, `/api/billers/` |

### 5.2 Data Consumption by Page

**AdminDashboard.jsx:**
- Daily metrics: `GET /business/daily/?date=YYYY-MM-DD`
- Monthly metrics: `GET /business/monthly/?month=YYYY-MM`
- Incidents: `GET /risk/incidents/`
- Users: `GET /auth/users/`
- Accounts: `GET /api/admin/accounts/`
- AI analysis: `POST /risk/analyze/`

**HomeBank.jsx:**
- User accounts: `GET /api/accounts`
- Notifications: `GET /api/notifications/`
- Transactions: `GET /api/transfers/internal/`, `GET /api/transfers/external/`

### 5.3 Date Filtering Logic

The frontend uses date picker components that send:
- Daily: `?date=YYYY-MM-DD` format
- Monthly: `?month=YYYY-MM` or `?month=YYYY-MM-DD` format

**Backend handling (MonthlySummaryView):**
```python
if len(month_param_raw) == 7:  # YYYY-MM format
    month_param = datetime.strptime(month_param_raw + "-01", "%Y-%m-%d").date()
```

**Known Issue:** If a date is selected with no data, the backend now returns zeroed metrics instead of an empty array (fixed in recent conversations).

### 5.4 State Storage

- **JWT Tokens:** localStorage (`access`, `refresh`)
- **User Data:** React state, fetched on mount
- **Dashboard Filters:** React state (not persisted)

### 5.5 API Response Handling

**Typical Pattern:**
```javascript
try {
  const response = await fetch(endpoint, {
    headers: { Authorization: `Bearer ${token}` }
  });
  const data = await response.json();
  setState(data);
} catch (error) {
  setError(error.message);
}
```

### 5.6 Potential Frontend Issues

1. **Token Expiry:** JWT tokens expire after 60 minutes. Frontend should handle 401 responses by attempting token refresh.

2. **Stale Data:** Admin dashboard may show outdated data if not refreshed after admin actions.

3. **Admin Detection:** Previously relied on `ADMIN_EMAILS` constant. Should use `user.is_staff` from API response.

4. **Empty States:** Dashboard charts may crash if metrics return empty arrays instead of zeroed objects.

---

## 6. Data and Metrics

### 6.1 Calculated Metrics

**DailyBusinessMetrics fields:**

| Metric | Calculation | Source |
|--------|-------------|--------|
| new_users | Count of users created today | User model |
| total_users | Cumulative user count | User model |
| active_users | Unique logins today (DAU) | DailyActiveUser model |
| active_users_7d | Unique logins in 7 days (WAU) | DailyActiveUser model |
| active_users_30d | Unique logins in 30 days (MAU) | DailyActiveUser model |
| total_transactions_success | SUCCESS status count | Transaction model |
| total_transferred_amount | Sum of amounts | Transaction model |
| avg_transaction_value | total_amount / count | Calculated |
| fee_revenue | Sum of fee_amount | Transaction model |
| fx_volume | Cross-currency transfer amounts | Transaction model |
| fx_spread_revenue | Estimated FX margin | 0.3% of fx_volume |
| net_revenue | fee + bill_commission + fx_spread - refunds - chargebacks | Calculated |
| profit | Equal to net_revenue | Simplified |

### 6.2 Daily / Monthly / Total Calculation

**Daily:** Direct aggregation from that day's data
**Weekly:** Sum of daily metrics for Monday-Sunday
**Monthly:** Sum of daily metrics for calendar month
**Total:** Not stored; calculated on-demand if needed

**Implementation:**
- `build_weekly_summaries()` in `business/services.py`
- `build_monthly_summaries()` in `business/services.py`

### 6.3 Date Filtering Failure Points

1. **No Data for Date:** Backend returns zeroed object (recent fix)
2. **Invalid Date Format:** `_parse_date_param()` returns None, falls back to latest
3. **Future Dates:** Returns zeroed metrics
4. **Timezone Issues:** Uses `timezone.localdate()` which respects Django TIME_ZONE setting

### 6.4 Seed Data Logic

**Command:** `python manage.py reset_and_seed_analytics`

**Date Range:** September 1, 2025 - January 7, 2026

**Generation Logic:**
1. Creates 10-20 transactions per account per day
2. 30% of accounts pay bills daily
3. Random 15-25% cross-currency (FX) transactions
4. Random new users (0-5 per day)
5. Random failed logins (0-5 per day)
6. Random incidents (0-2 per day)

**Country Distribution:**
- Jordan: 60%
- UAE: 25%
- KSA: 15%

**Currency Distribution:**
- JOD: 70%
- USD: 20%
- EUR: 10%

### 6.5 Risks of Missing or Misleading Data

1. **Seed Data is Simulated:** Does not reflect real user behavior patterns
2. **Rolling Windows Approximate:** WAU/MAU use multiplier estimates (0.6x, 0.5x)
3. **No Real FX Rates:** Uses hardcoded conversion rates
4. **Balance Snapshots Mock Values:** `sender_balance_after` in seeded data does not reflect actual balances
5. **AI Insights Depend on API Key:** Missing `GEMINI_API_KEY` results in null insights

---

## 7. Risk Management Logic

### 7.1 Risky Behavior Definition

The system considers the following behaviors risky:

**Critical (Severity: Critical/High):**
- Fraud-related keywords in incident event
- Confirmed malicious activity
- 10+ failed login attempts
- Credential stuffing patterns
- Impossible travel detection
- Transactions from blacklisted IPs
- Transaction from new country immediately after login

**Moderate (Severity: Medium):**
- Large transactions (>= 10,000)
- Unusual transaction size (5x average)
- Multiple transfers in short window
- Failed transfer attempts
- New device/country login
- Rate limit triggers

**Low (Severity: Low):**
- Successful logins (for audit)
- Unusual hour activity
- Balance anomalies

### 7.2 Anomaly Detection

**Transaction Anomalies (in order of check):**

```python
1. amount >= large_txn_threshold (10,000)
2. amount >= 5x user's 30-day average
3. First transfer to this receiver
4. 5+ transfers in 5-minute window (deduplicated)
5. 10+ transactions OR 50,000 amount in 15 minutes
6. Transaction hour < 5 AM
7. IP in RISK_BLACKLISTED_IPS
8. Tor/VPN headers detected
9. Different country from last login (within 2 hours)
```

**Authentication Anomalies:**

```python
1. 5+ failures from IP targeting 3+ accounts (credential stuffing)
2. 5+ failures on same email (brute-force)
3. Login from different country (new country detection)
4. Country change within 1 hour (impossible travel)
5. User-agent change (new device)
6. Login before 5 AM or after 11 PM (unusual hours)
7. 5+ distinct users from same IP in 1 hour (shared IP abuse)
```

### 7.3 Report Generation

**Incident Reports:**
- Stored in `Incident` model with JSON `details` field
- Accessible via `GET /risk/incidents/`
- Filterable by severity, country

**Business Reports:**
- `DailyAIInsight` model stores AI-generated daily analysis
- `MonthlyAIInsight` model stores AI-generated monthly analysis
- Generated by `business/reporting.py`

### 7.4 AI Usage in Risk Detection

**Location:** `risk/ai.py`

**Process:**
1. `determine_action()` runs first (deterministic)
2. Based on severity and keywords:
   - critical severity OR fraud keywords → TERMINATE
   - high severity OR suspicious keywords → FREEZE
   - medium severity OR failed keywords → BLOCK
   - otherwise → MONITOR
3. `analyze_incident()` calls Gemini for human-readable explanation
4. AI output appended with deterministic action recommendation

**Fallback:**
- If `GEMINI_API_KEY` not set → Returns deterministic action only
- If API call fails → Returns error message with deterministic action

### 7.5 Action Suggestions

| Action | Meaning | Trigger |
|--------|---------|---------|
| TERMINATE | Disable account/session, escalate to security | Critical severity, fraud keywords |
| FREEZE | Suspend account pending review | High severity, suspicious patterns |
| BLOCK | Temporary access restriction | Medium severity, failed attempts |
| MONITOR | Continue observation | Low severity, informational |

### 7.6 Logic Gaps and Weaknesses

1. **Tor/VPN Detection is Header-Based:** Easily bypassed, relies on proxies setting headers

2. **IP Geolocation Requires External API:** IPInfo token must be configured; falls back to empty country

3. **No Machine Learning:** All detection is rule-based with hardcoded thresholds

4. **Impossible Travel Only Checks Country:** Does not consider time zones or actual distance

5. **Rate Limits Don't Block Distributed Attacks:** Only per-IP throttling

6. **Blacklist is Static:** `RISK_BLACKLISTED_IPS` must be manually maintained

7. **No Real-Time Alerts:** Incidents are logged but not pushed to admins

8. **Admin Actions Don't Auto-Trigger:** AI suggests actions but doesn't execute them

---

## 8. Authentication and Authorization

### 8.1 Auth Flow

**Email/Password (2FA):**
```
1. POST /auth/login/init/ {email, password}
   → Validates credentials
   → Generates 6-digit OTP (OTPVerification model)
   → Sends OTP via email
   → Returns {"detail": "OTP sent to email"}

2. User receives email with code

3. POST /auth/login/verify/ {email, code}
   → Validates OTP (not expired, not used)
   → Marks OTP as verified
   → Sets user.is_online = True
   → Returns {access: "...", refresh: "..."}
```

**Google OAuth:**
```
1. User clicks "Login with Google"
2. Frontend redirects to /accounts/google/login/
3. Google authenticates and redirects to /accounts/google/login/callback/
4. Django allauth creates/links user
5. Redirect to /auth/social/complete/
6. social_login_complete() generates JWT tokens
7. Redirect to frontend with tokens in URL: 
   /auth/social/success?access=...&refresh=...
```

### 8.2 Role Handling

**User Roles (Boolean flags on User model):**

| Flag | Meaning | Grants |
|------|---------|--------|
| is_active | Account enabled | Login ability |
| is_staff | Admin user | `IsAdminUser` permission |
| is_superuser | Full admin | Django admin + all permissions |

**Permission Checking:**
```python
# In views
permission_classes = [IsAdminUser]  # Checks is_staff=True

# Serializers check ownership via queryset filtering
def __init__(self, *args, **kwargs):
    self.fields["account"].queryset = Account.objects.filter(user=req.user)
```

### 8.3 Admin Access Control

**Endpoints requiring `IsAdminUser`:**
- `/business/*` - All analytics
- `/risk/*` - All security monitoring
- `/api/admin/*` - User/account management

**Admin Creation:**
```bash
python manage.py createsuperuser
# Email, password (no username)
```

### 8.4 Account Lock/Unlock Logic

**Lock (Block):**
```python
user.is_active = False
user.save()
# User cannot log in
# Existing JWTs still valid!
```

**Unlock (Unblock):**
```python
user.is_active = True
user.save()
# User can log in again
```

**Full Session Termination:**
```python
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken, BlacklistedToken

for token in OutstandingToken.objects.filter(user=user):
    BlacklistedToken.objects.get_or_create(token=token)
# All existing JWTs are now invalid
```

### 8.5 Security Risks and Missing Protections

1. **JWT Not Invalidated on Block:**
   - Blocking a user does NOT invalidate their tokens
   - Must call terminate-session separately
   - Risk: Blocked user can continue using existing session

2. **Refresh Token Rotation Disabled:**
   ```python
   # settings.py
   #"ROTATE_REFRESH_TOKENS": True,  # Commented out
   #"BLACKLIST_AFTER_ROTATION": True,
   ```
   - Same refresh token can be reused indefinitely
   - Risk: Token theft has longer impact

3. **OTP Sent via Email Only:**
   - No SMS or authenticator app option
   - Email compromise = full account compromise

4. **OTP Not Rate-Limited Separately:**
   - Uses global rate limits, not OTP-specific
   - Attacker could exhaust limits for legitimate user

5. **Google OAuth Auto-Links Accounts:**
   ```python
   SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT = True
   ```
   - If someone controls an email, they can link to existing account
   - Risk: Social engineering attack vector

6. **No Password Complexity Enforcement:**
   - Uses Django validators (min length, common passwords, numeric)
   - No requirement for special characters

7. **Session Timeout Not Enforced:**
   - Access token: 60 minutes
   - Refresh token: 7 days
   - No absolute session limit

8. **Admin Actions Not Require Re-Authentication:**
   - Admin can block/terminate with just JWT
   - No 2FA for sensitive admin operations

---

## 9. AI / BI Advisor

### 9.1 Purpose

The AI/BI Advisor provides **read-only decision support** for administrators. It:
- Explains performance changes
- Identifies business risks
- Suggests areas for investigation
- Does NOT modify any data or trigger automated actions

### 9.2 Data Analyzed

**Business AI (`business/ai.py`):**
- Daily metrics comparison (today vs yesterday)
- Monthly summaries
- User growth trends
- Transaction volumes
- Revenue components
- Failed login counts
- Incident counts

**Risk AI (`risk/ai.py`):**
- Individual incident details
- Event type and severity
- IP address and country
- User context
- Transaction amounts (if applicable)

### 9.3 Prompt Structure

**Business Advisor Prompt (business/ai.py):**
```
You are an AI Business Advisor for a digital banking analytics platform.

IMPORTANT CONSTRAINTS:
- You are providing READ-ONLY decision support for administrators.
- All financial values represent business indicators in a banking simulation, NOT real money.
- You must NOT suggest automated changes, enforcement actions, or system modifications.
- All recommendations must be DESCRIPTIVE and require HUMAN REVIEW.
- Do NOT speculate beyond the data provided.
- If data is insufficient, state that explicitly.

YOUR ROLE:
1. Explain significant performance changes (profit, revenue, users, transactions)
2. Identify business risks (loss days, high failure rates, efficiency issues)
3. Provide clear, actionable suggestions for administrators to INVESTIGATE

OUTPUT FORMAT:
📊 **Performance Summary**
🔍 **Key Observations**
⚠️ **Risk Signals**
💡 **Recommendations for Review**
```

**Risk Advisor Prompt (risk/ai.py):**
```
You are a Senior SOC Analyst at NexusBank. Analyze this security incident:

- Event: {incident.event}
- Severity: {incident.severity}
- IP: {incident.ip} ({incident.country})
- User: {incident.attempted_email or incident.user}
- Context: {incident.details}

The system has already determined the recommended action: {recommended_action.upper()}

Task:
Provide a VERY SHORT, readable summary (under 60 words).
1. Threat Assessment (1 sentence).
2. Immediate Actions (2-3 concise bullet points).
3. Justification for the {recommended_action.upper()} recommendation.

Do NOT provide generic advice. Be specific and brief.
End with: "TAKE ACTION: {action_text}"
```

### 9.4 Reliable vs Risky Outputs

**Reliable:**
- Deterministic action recommendations (terminate/freeze/block/monitor)
- Metric comparisons (numerical)
- Trend identification from data

**Risky (requires human verification):**
- Root cause analysis ("likely due to...")
- Prediction of future trends
- Severity assessments beyond the rule-based determination
- Recommendations for specific actions

### 9.5 Limitations

1. **No Historical Context:** Each analysis is independent; AI doesn't remember past analyses

2. **Hallucination Risk:** AI may invent explanations not supported by data

3. **No Real-Time Analysis:** Must be triggered manually; no streaming updates

4. **API Dependency:** If Gemini API is down or rate-limited, analysis unavailable

5. **Cost Implications:** Each analysis is an API call; high volume = higher cost

6. **No Feedback Loop:** System doesn't learn from admin decisions

### 9.6 Improvement Points

1. Add confidence scores to AI outputs
2. Implement caching for repeated analyses
3. Add historical context window
4. Create fallback to simpler models if Gemini unavailable
5. Track which AI recommendations were acted upon
6. Implement prompt versioning for reproducibility

---

## 10. Known Issues and Technical Debt

### 10.1 Bugs Inferred from Code

1. **Duplicate Import in api/urls.py (Line 11-12):**
   ```python
   from .views import (
       ...
       CardDetailView,
       ExternalTransferListCreateView,
       CardDetailView,  # Duplicated
       ExternalTransferListCreateView,  # Duplicated
   ```

2. **Duplicate URL Comment in api/urls.py (Lines 70-75):**
   ```python
   # Admin Response Endpoints (Scope 1.5.7)
   # ==========================================================================
   # ==========================================================================
   # Admin Response Endpoints (Scope 1.5.7)
   ```

3. **PENDING_OTP Status Creates Transaction First:**
   - Transaction is saved before OTP verification
   - If user never verifies, transaction stays in PENDING_OTP forever
   - No cleanup mechanism for stale pending transactions

4. **Seed Data Does Not Clean All Tables:**
   - `WeeklySummary` and `MonthlySummary` not cleaned in date range
   - Could accumulate stale summaries

5. **Rolling Average in Seed is Approximated:**
   - Uses multipliers (0.6x, 0.5x) instead of actual unique counts
   - WAU/MAU values are estimates, not accurate

### 10.2 Duplicated Logic

1. **Transfer OTP Logic Duplicated:**
   - `InternalTransferListCreateView.create()` and `ExternalTransferListCreateView.create()`
   - Same OTP generation and email sending code in both
   - Should be extracted to shared utility

2. **Zeroed Metric Object Duplicated:**
   - `DailyMetricsListView.list()` and `MonthlySummaryView.get()`
   - Same zeroed dictionary structure defined in multiple places
   - Should be a constant or factory function

3. **Account Ownership Check Duplicated:**
   - `InternalTransferSerializer.__init__()` and `ExternalTransferSerializer.__init__()`
   - Same queryset filtering pattern

### 10.3 Missing Validations

1. **No Minimum Balance Check:**
   - Only checks balance >= transfer amount
   - No concept of minimum required balance

2. **No Daily Transfer Limit:**
   - Only per-transaction limit (10,000)
   - User could make unlimited 9,999 transfers

3. **No Cross-Currency Transfer Fee:**
   - FX spread is tracked but not charged to user
   - `fx_spread_revenue` is simulated, not actual charge

4. **No Card Transaction Support:**
   - Cards exist in model but no card payment endpoints
   - Card status (active/frozen) not enforced in transfers

5. **No Biller Account Validation:**
   - Bill payment assumes biller.system_account exists
   - No protection if system_account is deleted

### 10.4 Poor Naming or Structure

1. **`views.py` vs `views_admin.py` Split:**
   - Both in same app
   - Could confuse developers about where to add new endpoints

2. **`convert_currency.py` Naming:**
   - Functions are named `jod_to_usd`, etc.
   - Should be a single `convert(amount, from_currency, to_currency)` function

3. **`BaseModel` vs `TimeStampedModel`:**
   - `api/models.py` has `BaseModel` with created_at/updated_at
   - `business/models.py` has `TimeStampedModel` with same fields
   - Should be unified

4. **Inconsistent Error Messages:**
   - Some use `{"detail": "..."}`, others use `{"error": "..."}`
   - Should standardize

### 10.5 Scalability Risks

1. **SQLite Database:**
   - Fine for development
   - Will bottleneck with concurrent writes in production

2. **InMemoryChannelLayer:**
   - WebSocket messages not persisted
   - Won't work with multiple server instances

3. **Synchronous Metrics Updates:**
   - Every transaction triggers multiple DB updates
   - Could slow down transfers under high load

4. **No Database Indexing Optimization:**
   - Many queries filter by date, user, account
   - Missing composite indexes could slow queries

5. **No Query Pagination in Some Views:**
   - `AdminAccountsListView` returns ALL accounts
   - Could be problematic with 10,000+ accounts

6. **No Rate Limiting on AI Analysis:**
   - Each analysis calls Gemini API
   - Could hit rate limits or incur high costs

---

## 11. Improvement Recommendations

### 11.1 Short-Term Fixes (Quick Wins)

1. **Remove Duplicate Imports in api/urls.py**
   - Effort: 5 minutes
   - Impact: Code cleanliness

2. **Extract Transfer OTP Logic to Utility Function**
   ```python
   # api/utils.py
   def handle_high_value_transfer(request, user, tx, amount):
       if amount > HIGH_VALUE_TRANSFER_THRESHOLD:
           otp, code = TransferOTP.generate(user, tx)
           send_otp_email(user.email, code, amount)
           return True
       return False
   ```
   - Effort: 30 minutes
   - Impact: Reduces code duplication

3. **Add Pagination to AdminAccountsListView**
   ```python
   from rest_framework.pagination import PageNumberPagination
   
   class AdminAccountsListView(ListAPIView):
       pagination_class = PageNumberPagination
   ```
   - Effort: 10 minutes
   - Impact: Scalability

4. **Invalidate Tokens on User Block**
   ```python
   # In AdminUserBlockView.post()
   user.is_active = False
   user.save()
   # Add token invalidation
   AdminTerminateSessionView().terminate_user_sessions(user)
   ```
   - Effort: 15 minutes
   - Impact: Security

5. **Create Zeroed Metrics Factory**
   ```python
   def get_zeroed_daily_metrics(date):
       return {"date": str(date), "new_users": 0, ...}
   ```
   - Effort: 15 minutes
   - Impact: DRY principle

### 11.2 Medium-Term Refactors

1. **Unify BaseModel Classes**
   - Create `core/models.py` with shared abstract model
   - Have all apps inherit from it
   - Effort: 2 hours
   - Impact: Consistency

2. **Implement Daily Transfer Limits**
   ```python
   class Account(BaseModel):
       daily_transfer_limit = models.DecimalField(default=Decimal("50000.00"))
   
   # In serializer validate()
   today_total = Transaction.objects.filter(
       sender_account=account,
       created_at__date=timezone.now().date(),
       status=Transaction.Status.SUCCESS
   ).aggregate(total=Sum("amount"))["total"] or Decimal("0")
   
   if today_total + amount > account.daily_transfer_limit:
       raise ValidationError("Daily limit exceeded")
   ```
   - Effort: 4 hours
   - Impact: Security

3. **Add Celery for Async Tasks**
   - Move AI analysis to background tasks
   - Move email sending to background tasks
   - Effort: 1-2 days
   - Impact: Performance

4. **Implement Pending Transaction Cleanup**
   ```python
   # management/commands/cleanup_pending.py
   old_pending = Transaction.objects.filter(
       status=Transaction.Status.PENDING_OTP,
       created_at__lt=timezone.now() - timedelta(hours=24)
   )
   old_pending.update(status=Transaction.Status.FAILED)
   ```
   - Effort: 2 hours
   - Impact: Data hygiene

5. **Add Comprehensive Logging**
   - Use Python logging module consistently
   - Add request IDs for tracing
   - Effort: 4 hours
   - Impact: Debugging

### 11.3 Long-Term Architectural Improvements

1. **Migrate to PostgreSQL**
   - Required for production
   - Enables full-text search, better concurrency
   - Effort: 1 day
   - Impact: Scalability, reliability

2. **Implement Event-Driven Architecture**
   - Use Django signals or message queue
   - Decouple transaction logging from request handling
   - Effort: 1-2 weeks
   - Impact: Performance, maintainability

3. **Add Real-Time Notifications**
   - Use Django Channels for WebSocket
   - Push incident alerts to admins
   - Effort: 1 week
   - Impact: User experience

4. **Implement Microservices Split**
   - Separate risk service
   - Separate analytics service
   - Effort: 1-2 months
   - Impact: Scalability, team independence

5. **Add Machine Learning for Fraud Detection**
   - Train on historical incident data
   - Replace/augment rule-based detection
   - Effort: 2-3 months
   - Impact: Detection accuracy

### 11.4 What Should NOT Be Changed Yet

1. **Database Schema:** Major changes would break existing data
2. **API Endpoints:** Frontend depends on current contract
3. **Auth Flow:** 2FA is working; changing could break login
4. **Threshold Values:** Current values are tested; change requires analysis
5. **AI Prompts:** Iterative improvement only; avoid complete rewrites

---

## 12. Final Summary

### 12.1 One-Page Mental Model

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           NEXUS BANK SYSTEM                             │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  USER FLOW                                                              │
│  ─────────                                                              │
│  1. Register (email + password)                                         │
│  2. Login (2FA: credentials → OTP via email → JWT tokens)              │
│  3. Create accounts (Savings/Basic/USD/EUR)                            │
│  4. Transfer money (internal free, external 1% fee, >500 requires OTP) │
│  5. Pay bills (fixed amount per biller)                                │
│                                                                         │
│  SECURITY LAYER                                                         │
│  ──────────────                                                         │
│  • Every action logged to Incident model                               │
│  • Rule-based anomaly detection (13+ rules)                            │
│  • Admin can block users, freeze accounts, terminate sessions          │
│  • AI analyzes incidents and suggests actions                          │
│                                                                         │
│  ANALYTICS LAYER                                                        │
│  ───────────────                                                        │
│  • Metrics updated synchronously on every transaction                  │
│  • Daily/Weekly/Monthly summaries                                      │
│  • Geo and currency breakdowns                                         │
│  • AI generates business insights                                      │
│                                                                         │
│  KEY CONSTRAINTS                                                        │
│  ───────────────                                                        │
│  • Balance cannot go negative (DB constraint)                          │
│  • Transfer amount must be positive (DB constraint)                    │
│  • Max withdrawal per transaction: 10,000                              │
│  • High-value transfer threshold: 500                                  │
│  • OTP expires in 5 minutes, max 3 attempts                            │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 12.2 What the Owner Must Understand Before Extending

1. **Transaction Atomicity is Critical:**
   - Never modify `execute_transaction()` without understanding database locking
   - Race conditions can cause double-spending

2. **Security Logging is Pervasive:**
   - Adding new endpoints may require adding logging
   - Check `risk/auth_logging.py` and `risk/transaction_logging.py` patterns

3. **AI is Advisory Only:**
   - Never let AI actions execute automatically
   - Always require human confirmation

4. **Frontend Assumes Specific API Contract:**
   - Changing response shapes will break dashboard
   - Version API endpoints if making breaking changes

5. **Seed Data is for Testing Only:**
   - Production should start with empty analytics
   - Running seed command will delete real transaction history

6. **Token Lifecycle Matters:**
   - Blocking a user doesn't invalidate their tokens
   - Call terminate-session for immediate effect

### 12.3 Biggest Technical Risks

1. **SQLite Under Load:**
   - Will fail with concurrent writes
   - Must migrate to PostgreSQL before real usage

2. **No Token Rotation:**
   - Stolen refresh token valid for 7 days
   - Enable rotation in production

3. **Synchronous Everything:**
   - AI calls block request until complete
   - Email sending blocks transaction creation
   - Add async processing for production

4. **No Real Fraud Response:**
   - System detects but doesn't prevent
   - Need automated freezing for critical incidents

5. **Single Point of Failure:**
   - All logic in one Django app
   - Database downtime = complete outage

### 12.4 Biggest Business Risks

1. **Simulated Revenue:**
   - `profit` and `net_revenue` are calculated, not from real payments
   - Do not use for actual business decisions

2. **No Real Currency Conversion:**
   - Hardcoded exchange rates
   - Real FX would require live rate APIs

3. **No Compliance Features:**
   - No KYC/AML checks
   - No regulatory reporting
   - Not suitable for real banking without major additions

4. **Demo Data Remains:**
   - Seed command must not run in production
   - Risk of mixing test and real data

5. **AI Reliability:**
   - Gemini API availability affects admin workflows
   - Should have fallback for AI-assisted decisions

---

**End of Audit**

*This document should be updated as the codebase evolves. Last updated: January 6, 2026*
