# RoadRescue

A roadside assistance platform for Lebanon connecting drivers with verified mechanics.
Built as an MIS senior capstone project with Flask, SQLAlchemy, and server-rendered
Jinja2 templates.

## Features

- **Customers** can register, manage multiple vehicles, request roadside assistance by
  dropping a pin on an interactive Lebanon map (or typing an address), cancel a request
  while it's still pending, track their mechanic live once en route (including a moving
  marker on the map), pay either in-app (Stripe test mode) or in cash, and rate/complain
  afterwards -- with a dedicated "My reviews & complaints" history page. Forgot your
  password? A self-service reset flow is one click away from the login page.
- **Mechanics** apply by uploading certification documents (drag-and-drop or file
  picker), get approved by an admin, toggle their availability, and work jobs through a
  defined status pipeline, with search/filter on their job history.
- **Admins** review and open uploaded certification documents, approve/suspend
  mechanics, review complaints, see platform-wide stats, and search/filter every
  mechanic, customer, and request list.

All of it is localized for Lebanon: kilometers (not miles), USD pricing, `+961` phone
numbers, and a seeded list of Lebanese service areas -- no US-specific defaults anywhere.

## Tech stack

| Layer | Choice |
|---|---|
| Backend | Flask (application factory + blueprints: `auth`, `customer`, `mechanic`, `admin`) |
| Database / ORM | SQLAlchemy, SQLite for local dev |
| Auth | Flask-Login + Werkzeug password hashing |
| Forms | Flask-WTF with server-side validation |
| Frontend | Jinja2 templates, plain CSS, small vanilla-JS files |
| Maps | Leaflet + OpenStreetMap tiles (free, no API key) for location picking and live tracking |
| Payments | Stripe **test mode**, a simulated fallback, or cash-to-mechanic -- see below |

## Setup

```bash
cd RoadRescue
python -m venv venv

# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate

pip install -r requirements.txt
```

The database schema is created automatically the first time the app starts
(`db.create_all()` inside the application factory) -- there's no separate migration
step to run for this SQLite-based demo. See "Moving to production" below for how a
real deployment would instead use migrations.

### Seed demo data

```bash
python seed.py
```

This drops and recreates all tables, then creates one admin, two customers (with three
vehicles between them), three mechanics (two approved, one still pending review), and
four sample requests spanning the lifecycle: rated & paid, awaiting payment, currently
"en route" (for the live-tracking demo), and still pending.

### Run the app

```bash
# Windows
set FLASK_APP=wsgi.py
flask run

# macOS/Linux
export FLASK_APP=wsgi.py
flask run
```

Then open http://127.0.0.1:5000.

### Run the tests

```bash
pytest
```

## Demo login credentials

| Role | Email | Password | Notes |
|---|---|---|---|
| Admin | admin@roadrescue.lb | Admin123! | Single seeded admin account |
| Customer | karim.haddad@example.com | Customer123! | Has 1 vehicle, 3 requests in different states |
| Customer | layal.fares@example.com | Customer123! | Has 2 vehicles |
| Mechanic | georges.mechanic@example.com | Mechanic123! | Approved, available, has an active job |
| Mechanic | rami.mechanic@example.com | Mechanic123! | Approved, offline |
| Mechanic | sami.mechanic@example.com | Mechanic123! | Still pending admin approval |

## Enabling real Stripe test-mode card payment

By default (no Stripe keys configured) the "Pay now" flow uses a built-in simulated
confirmation screen -- no external account needed. To collect an actual card via
Stripe **test mode** instead:

1. Create a free Stripe account and grab your test-mode **secret key** (`sk_test_...`)
   and **publishable key** (`pk_test_...`) from the dashboard.
2. Set both as environment variables before running the app:

   ```bash
   export STRIPE_SECRET_KEY=sk_test_...
   export STRIPE_PUBLISHABLE_KEY=pk_test_...
   ```
3. Restart the app. The "Pay now" screen will now show a real embedded Stripe card
   field (via [Stripe Elements](https://stripe.com/docs/payments/elements)) right on
   the page -- use Stripe's [test card numbers](https://stripe.com/docs/testing), e.g.
   `4242 4242 4242 4242` with any future expiry and any CVC. No real money ever moves,
   and the raw card number never touches this app's server: Stripe's own script
   tokenizes it directly in the browser, and the backend only ever sees a
   PaymentIntent id, which it re-verifies with Stripe before marking the request paid.

## Enabling real password-reset emails

By default (no mail server configured) "Forgot your password?" on the login page still
works end-to-end -- it just shows the reset link directly on screen instead of emailing
it, so the feature works out of the box with no email account required. To actually send
the link by email instead:

1. Set your SMTP server's details as environment variables before running the app:

   ```bash
   export MAIL_SERVER=smtp.gmail.com
   export MAIL_PORT=587
   export MAIL_USERNAME=you@gmail.com
   export MAIL_PASSWORD=your-app-password
   export MAIL_DEFAULT_SENDER=no-reply@roadrescue.lb
   ```
2. Restart the app. Reset links are signed and self-expiring (`itsdangerous`, valid for
   one hour by default -- see `PASSWORD_RESET_MAX_AGE_SECONDS` in
   [app/config.py](app/config.py)), so no database column or cleanup job is needed to
   invalidate them. The "forgot password" page always shows the same confirmation
   message regardless of whether the email matched an account, so it can't be used to
   check which emails are registered.

## What's simulated vs. production-ready

This is a capstone demo, so a few things are intentionally simplified:

| Area | In this demo | For production |
|---|---|---|
| Map | Real interactive map (Leaflet + OpenStreetMap, free, no API key) for dropping a pin and for the live-tracking view | Same library works as-is; could swap to Google Maps if you have a billing-enabled API key, or add server-side push (see below) |
| Mechanic location / GPS | The customer's pin is real; the mechanic's position is *simulated* -- a random starting point exactly the (also simulated) remaining distance away, animated toward the customer as that distance counts down (`ServiceRequest._place_mechanic_start` / `mechanic_position` in [app/models.py](app/models.py)), polled by the browser every few seconds | Real GPS coordinates read from the mechanic's phone, pushed via WebSockets instead of polling |
| Reverse geocoding | Client-side calls to OSM's free Nominatim API to turn a map pin into a readable address | Same approach works in production too, or use a paid geocoder for higher volume/rate limits |
| Payments | A real embedded Stripe Elements card field in **test mode** (PaymentIntents API, re-verified server-side before marking paid) when Stripe keys are set, a simulated "confirm payment" screen if not, or a cash option that just records the choice | Stripe **live mode**, plus webhook-based confirmation as a fallback to the client-side check (covers the case where the browser tab closes right after payment); cash payments would likely need mechanic-side confirmation before marking paid |
| Platform commission | A flat 15% (`PLATFORM_COMMISSION_RATE` in [app/constants.py](app/constants.py)) taken from every completed job; the mechanic gets the rest, and the admin dashboard shows both the gross job value and the platform's cut separately | Same mechanism; a real deployment would likely make the rate configurable per mechanic tier or promotion rather than a single global constant |
| Certification review | Uploaded documents are stored as plain files on local disk (`instance/uploads/certifications/`) | Object storage (S3/GCS) with virus scanning and access-controlled URLs |
| Password-reset email | Works fully out of the box: if no SMTP server is configured, the reset link is shown directly on screen (dev mode) instead of emailed | Same code path, just point it at a real SMTP server or transactional email service (SendGrid, SES, etc.) |
| Database | SQLite file, schema created via `db.create_all()` on startup | PostgreSQL (just change `DATABASE_URL`; the ORM code doesn't change) with Flask-Migrate/Alembic-managed migrations |
| Notifications | None -- customers/mechanics discover updates by revisiting the page (or the JS polling on the tracking view) | Push notifications / SMS (relevant in Lebanon given variable data connectivity) via a provider like Twilio |
| Mechanic matching | A pending request is visible to every approved mechanic; whoever accepts first gets it | Proximity-based matching using real mechanic locations |
| Secrets | `SECRET_KEY` defaults to a dev value in [app/config.py](app/config.py) | Must be set via a real environment variable / secrets manager |

## Project structure

```
RoadRescue/
  app/
    __init__.py        application factory
    config.py           Config / TestingConfig
    extensions.py        db, login_manager, csrf
    models.py            SQLAlchemy models + the request state machine
    constants.py          Lebanese areas, issue pricing, phone regex, etc.
    decorators.py         role_required / approved_mechanic_required
    auth/                 register, login, logout
    customer/              vehicles, requests, tracking, payment, rating, complaints
    mechanic/               certifications, availability, job pipeline, earnings
    admin/                   mechanic approval, complaints, platform stats
    templates/               Jinja2 templates, one folder per blueprint
    static/                   style.css + JS: validation, tracking, location_picker, certification_upload
  instance/
    uploads/certifications/    uploaded mechanic certification documents
  seed.py                 demo data
  wsgi.py                  `flask run` entry point
  tests/                    pytest suite (state machine, access control, requests, payment, admin, auth)
  requirements.txt
```
