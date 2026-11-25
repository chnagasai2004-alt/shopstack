# Shopstack

A feature-rich, single-repository ecommerce starter built with Python, FastAPI, SQLAlchemy, SQLite, Jinja2, and vanilla JavaScript.

## Included

- Product catalog with categories, search, sorting, pagination, stock, featured products, and product detail pages
- Guest cart stored in the signed session and authenticated cart persisted in SQLite
- Registration, login, logout, session-based authentication, and role-aware admin access
- Wishlist, product reviews, ratings, address capture, coupon-ready checkout structure, and order history
- Checkout totals with free-shipping threshold and tax calculation, idempotent order submit, inventory decrement, order confirmation, and status tracking
- Admin dashboard with catalog creation/editing, stock updates, fulfillment status transitions, cancellation with stock restoration, and revenue/customer summaries
- Responsive storefront UI with no frontend build step
- Seed data for local exploration

## Run locally

```bash
cd ecommerce_app
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000.

Demo accounts:

- Shopper: `demo@example.com` / `demo123`
- Admin: `admin@example.com` / `admin123`

The app uses `shopstack.db` in the project root by default. Override with `DATABASE_URL` if needed. Payments are intentionally mocked as a local demo; production use should add a PCI-compliant provider, real email, shipping, tax, observability, CSRF protection, and deployment hardening.

## Test

```bash
pytest -q
```
