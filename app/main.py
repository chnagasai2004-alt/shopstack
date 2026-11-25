from __future__ import annotations

import math
import os
import secrets
from pathlib import Path
from typing import Annotated
from urllib.parse import urlencode

from fastapi import Depends, FastAPI, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, joinedload
from starlette.middleware.sessions import SessionMiddleware

from .auth import hash_password, verify_password
from .database import Base, SessionLocal, engine, get_db
from .models import (
    Address,
    CartItem,
    Category,
    Order,
    OrderItem,
    Product,
    Review,
    User,
    WishlistItem,
    utcnow,
)

BASE_DIR = Path(__file__).resolve().parent
app = FastAPI(title="Shopstack", version="1.0.0")
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SESSION_SECRET", "dev-only-change-me"),
    same_site="lax",
    https_only=False,
)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")


PRODUCT_SEEDS = [
    {"category": "Audio", "name": "Orbit Wireless Headphones", "slug": "orbit-wireless-headphones", "price": 12900, "compare": 15900, "sku": "AUD-001", "stock": 24, "featured": True, "image": "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?auto=format&fit=crop&w=900&q=85", "description": "Immersive over-ear listening with adaptive noise cancellation, a 40-hour battery, and a lightweight memory-foam fit."},
    {"category": "Workspace", "name": "Lumen Desk Lamp", "slug": "lumen-desk-lamp", "price": 7900, "compare": None, "sku": "HOM-002", "stock": 18, "featured": True, "image": "https://images.unsplash.com/photo-1507473885765-e6ed057f782c?auto=format&fit=crop&w=900&q=85", "description": "A warm, dimmable desk light with a sculptural profile and a focused reading mode for late-night work."},
    {"category": "Bags", "name": "Transit Daypack", "slug": "transit-daypack", "price": 9800, "compare": 11900, "sku": "BAG-003", "stock": 31, "featured": True, "image": "https://images.unsplash.com/photo-1553062407-98eeb64c6a62?auto=format&fit=crop&w=900&q=85", "description": "Weather-resistant everyday carry with a padded laptop sleeve, hidden passport pocket, and flexible 20L capacity."},
    {"category": "Home", "name": "Terra Ceramic Set", "slug": "terra-ceramic-set", "price": 5400, "compare": None, "sku": "HOM-004", "stock": 42, "featured": False, "image": "https://images.unsplash.com/photo-1493106641515-6b5631de4bb9?auto=format&fit=crop&w=900&q=85", "description": "Hand-finished stoneware mugs in a calm, neutral palette. Dishwasher and microwave safe."},
    {"category": "Apparel", "name": "Daily Knit Overshirt", "slug": "daily-knit-overshirt", "price": 8600, "compare": None, "sku": "APP-005", "stock": 15, "featured": True, "image": "https://images.unsplash.com/photo-1598033129183-c4f50c736f10?auto=format&fit=crop&w=900&q=85", "description": "A soft structured layer cut from breathable cotton knit with a relaxed fit and everyday versatility."},
    {"category": "Wellness", "name": "Calm Essential Oil Set", "slug": "calm-essential-oil-set", "price": 3600, "compare": 4200, "sku": "WEL-006", "stock": 27, "featured": False, "image": "https://images.unsplash.com/photo-1608571423902-eed4a5ad8108?auto=format&fit=crop&w=900&q=85", "description": "Three grounding botanical blends for moments of reset, packaged in amber glass with a simple guide."},
    {"category": "Tech", "name": "Arc Mechanical Keyboard", "slug": "arc-mechanical-keyboard", "price": 14900, "compare": None, "sku": "TEC-007", "stock": 12, "featured": True, "image": "https://images.unsplash.com/photo-1587829741301-dc798b83add3?auto=format&fit=crop&w=900&q=85", "description": "A compact mechanical keyboard with hot-swappable switches, tactile feedback, and quiet, considered details."},
    {"category": "Kitchen", "name": "Brew Go Kettle", "slug": "brew-go-kettle", "price": 6900, "compare": 7600, "sku": "KIT-008", "stock": 21, "featured": False, "image": "https://images.unsplash.com/photo-1594213114663-d94db9b171e1?auto=format&fit=crop&w=900&q=85", "description": "Compact pour-over kettle with variable temperature control and a balanced gooseneck spout."},
    {"category": "Outdoor", "name": "Field Bottle 750", "slug": "field-bottle-750", "price": 2900, "compare": None, "sku": "OUT-009", "stock": 55, "featured": False, "image": "https://images.unsplash.com/photo-1602143407151-7111542de6e8?auto=format&fit=crop&w=900&q=85", "description": "Double-wall stainless steel bottle that keeps drinks cold on commutes, trails, and long studio days."},
    {"category": "Accessories", "name": "Sol Leather Card Case", "slug": "sol-leather-card-case", "price": 4500, "compare": None, "sku": "ACC-010", "stock": 35, "featured": False, "image": "https://images.unsplash.com/photo-1627123424574-724758594e93?auto=format&fit=crop&w=900&q=85", "description": "Slim vegetable-tanned leather card case with four quick-access slots and a central cash fold."},
]


def money(cents: int | None) -> str:
    return f"${(cents or 0) / 100:,.2f}"


def slugify(text: str) -> str:
    return "-".join(text.lower().strip().split())


def current_user(request: Request, db: Session) -> User | None:
    user_id = request.session.get("user_id")
    return db.get(User, int(user_id)) if user_id else None


def require_user(request: Request, db: Session) -> User:
    user = current_user(request, db)
    if not user:
        next_path = request.url.path
        if request.url.query:
            next_path += f"?{request.url.query}"
        raise HTTPException(status_code=303, headers={"Location": f"/login?{urlencode({'next': next_path})}"})
    return user


def require_admin(request: Request, db: Session) -> User:
    user = require_user(request, db)
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


def cart_lines(request: Request, db: Session, user: User | None = None) -> list[dict]:
    lines: list[dict] = []
    if user:
        rows = db.query(CartItem).options(joinedload(CartItem.product)).filter(CartItem.user_id == user.id).all()
        for row in rows:
            if row.product and row.product.stock > 0:
                row.quantity = min(row.quantity, row.product.stock)
                lines.append({"id": row.id, "product": row.product, "quantity": row.quantity, "line_total_cents": row.quantity * row.product.price_cents})
        return lines

    guest_cart = request.session.get("cart", {})
    if not isinstance(guest_cart, dict):
        guest_cart = {}
    for raw_id, raw_quantity in guest_cart.items():
        product = db.get(Product, int(raw_id))
        if product and product.stock > 0:
            quantity = min(max(int(raw_quantity), 1), product.stock)
            lines.append({"id": None, "product": product, "quantity": quantity, "line_total_cents": quantity * product.price_cents})
    return lines


def cart_totals(lines: list[dict]) -> dict:
    subtotal = sum(line["line_total_cents"] for line in lines)
    shipping = 0 if subtotal >= 7500 or subtotal == 0 else 799
    tax = round(subtotal * 0.0825)
    return {"subtotal_cents": subtotal, "shipping_cents": shipping, "tax_cents": tax, "total_cents": subtotal + shipping + tax}


def template_context(request: Request, db: Session, **values) -> dict:
    user = current_user(request, db)
    lines = cart_lines(request, db, user)
    totals = cart_totals(lines)
    values.update({
        "request": request,
        "user": user,
        "cart_count": sum(line["quantity"] for line in lines),
        "cart_totals": totals,
        "money": money,
    })
    return values


def seed_data() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if db.query(Category).count() == 0:
            category_map: dict[str, Category] = {}
            for seed in PRODUCT_SEEDS:
                category_map.setdefault(seed["category"], Category(name=seed["category"], slug=slugify(seed["category"]), description=f"Thoughtful {seed['category'].lower()} for everyday rituals."))
            db.add_all(category_map.values())
            db.flush()
            for seed in PRODUCT_SEEDS:
                category = category_map[seed["category"]]
                db.add(Product(category_id=category.id, name=seed["name"], slug=seed["slug"], description=seed["description"], price_cents=seed["price"], compare_at_cents=seed["compare"], sku=seed["sku"], image_url=seed["image"], stock=seed["stock"], rating=5, review_count=0, featured=seed["featured"]))
        if not db.query(User).filter(User.email == "demo@example.com").first():
            db.add(User(email="demo@example.com", password_hash=hash_password("demo123"), full_name="Demo Shopper"))
        if not db.query(User).filter(User.email == "admin@example.com").first():
            db.add(User(email="admin@example.com", password_hash=hash_password("admin123"), full_name="Store Admin", is_admin=True))
        db.commit()
    finally:
        db.close()


@app.on_event("startup")
def on_startup() -> None:
    seed_data()


@app.get("/", response_class=HTMLResponse)
def home(request: Request, db: Session = Depends(get_db)):
    featured = db.query(Product).filter(Product.featured.is_(True), Product.stock > 0).order_by(Product.created_at.desc()).limit(4).all()
    categories = db.query(Category).order_by(Category.name).all()
    latest = db.query(Product).filter(Product.stock > 0).order_by(Product.created_at.desc()).limit(8).all()
    return templates.TemplateResponse("home.html", template_context(request, db, featured=featured, categories=categories, latest=latest))


@app.get("/shop", response_class=HTMLResponse)
def shop(
    request: Request,
    q: str = Query(""),
    category: str = Query(""),
    sort: str = Query("featured"),
    page: int = Query(1, ge=1),
    db: Session = Depends(get_db),
):
    query = db.query(Product).join(Category).filter(Product.stock > 0)
    if q.strip():
        term = f"%{q.strip()}%"
        query = query.filter(or_(Product.name.ilike(term), Product.description.ilike(term), Product.sku.ilike(term)))
    if category:
        query = query.filter(Category.slug == category)
    if sort == "price_asc":
        query = query.order_by(Product.price_cents.asc())
    elif sort == "price_desc":
        query = query.order_by(Product.price_cents.desc())
    elif sort == "newest":
        query = query.order_by(Product.created_at.desc())
    else:
        query = query.order_by(Product.featured.desc(), Product.created_at.desc())
    page_size = 8
    total = query.count()
    products = query.offset((page - 1) * page_size).limit(page_size).all()
    categories = db.query(Category).order_by(Category.name).all()
    return templates.TemplateResponse("shop.html", template_context(request, db, products=products, categories=categories, q=q, selected_category=category, sort=sort, page=page, total=total, page_count=max(1, math.ceil(total / page_size))))


@app.get("/products/{slug}", response_class=HTMLResponse)
def product_detail(slug: str, request: Request, db: Session = Depends(get_db)):
    product = db.query(Product).options(joinedload(Product.category), joinedload(Product.reviews).joinedload(Review.user)).filter(Product.slug == slug).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    related = db.query(Product).filter(Product.category_id == product.category_id, Product.id != product.id, Product.stock > 0).limit(4).all()
    wished = False
    user = current_user(request, db)
    if user:
        wished = db.query(WishlistItem).filter_by(user_id=user.id, product_id=product.id).first() is not None
    return templates.TemplateResponse("product.html", template_context(request, db, product=product, related=related, wished=wished))


@app.get("/cart", response_class=HTMLResponse)
def cart_page(request: Request, db: Session = Depends(get_db)):
    user = current_user(request, db)
    return templates.TemplateResponse("cart.html", template_context(request, db, lines=cart_lines(request, db, user)))


@app.post("/api/cart")
def api_add_cart(request: Request, product_id: Annotated[int, Form()] = None, quantity: Annotated[int, Form()] = 1, db: Session = Depends(get_db)):
    product = db.get(Product, product_id)
    if not product:
        return JSONResponse({"ok": False, "error": "Product not found"}, status_code=404)
    user = current_user(request, db)
    quantity = max(1, min(quantity, product.stock))
    if user:
        row = db.query(CartItem).filter_by(user_id=user.id, product_id=product.id).first()
        if row:
            row.quantity = min(row.quantity + quantity, product.stock)
        else:
            db.add(CartItem(user_id=user.id, product_id=product.id, quantity=quantity))
        db.commit()
    else:
        guest_cart = request.session.get("cart", {})
        guest_cart[str(product.id)] = min(int(guest_cart.get(str(product.id), 0)) + quantity, product.stock)
        request.session["cart"] = guest_cart
    lines = cart_lines(request, db, user)
    return {"ok": True, "cart_count": sum(line["quantity"] for line in lines), "message": f"{product.name} added to your bag."}


@app.post("/api/cart/{product_id}/update")
def api_update_cart(product_id: int, request: Request, quantity: Annotated[int, Form()] = 1, db: Session = Depends(get_db)):
    product = db.get(Product, product_id)
    if not product:
        return JSONResponse({"ok": False, "error": "Product not found"}, status_code=404)
    user = current_user(request, db)
    quantity = max(0, min(quantity, product.stock))
    if user:
        row = db.query(CartItem).filter_by(user_id=user.id, product_id=product_id).first()
        if row:
            if quantity == 0:
                db.delete(row)
            else:
                row.quantity = quantity
        db.commit()
    else:
        guest_cart = request.session.get("cart", {})
        if quantity == 0:
            guest_cart.pop(str(product_id), None)
        else:
            guest_cart[str(product_id)] = quantity
        request.session["cart"] = guest_cart
    lines = cart_lines(request, db, user)
    return {"ok": True, "cart_count": sum(line["quantity"] for line in lines), "totals": cart_totals(lines)}


@app.post("/cart/add")
def add_cart_form(request: Request, product_id: Annotated[int, Form()], quantity: Annotated[int, Form()] = 1, db: Session = Depends(get_db)):
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    user = current_user(request, db)
    quantity = max(1, min(quantity, product.stock))
    if user:
        row = db.query(CartItem).filter_by(user_id=user.id, product_id=product.id).first()
        if row:
            row.quantity = min(row.quantity + quantity, product.stock)
        else:
            db.add(CartItem(user_id=user.id, product_id=product.id, quantity=quantity))
        db.commit()
    else:
        guest_cart = request.session.get("cart", {})
        guest_cart[str(product.id)] = min(int(guest_cart.get(str(product.id), 0)) + quantity, product.stock)
        request.session["cart"] = guest_cart
    return RedirectResponse(request.headers.get("referer", "/shop"), status_code=303)


@app.post("/cart/{product_id}/remove")
def remove_cart(product_id: int, request: Request, db: Session = Depends(get_db)):
    user = current_user(request, db)
    if user:
        row = db.query(CartItem).filter_by(user_id=user.id, product_id=product_id).first()
        if row:
            db.delete(row)
            db.commit()
    else:
        guest_cart = request.session.get("cart", {})
        guest_cart.pop(str(product_id), None)
        request.session["cart"] = guest_cart
    return RedirectResponse("/cart", status_code=303)


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request, next: str = "/", db: Session = Depends(get_db)):
    if current_user(request, db):
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse("auth.html", template_context(request, db, mode="login", next=next, error=None))


@app.post("/login")
def login(request: Request, email: Annotated[str, Form()], password: Annotated[str, Form()], next: Annotated[str, Form()] = "/", db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == email.strip().lower()).first()
    if not user or not verify_password(password, user.password_hash):
        return templates.TemplateResponse("auth.html", template_context(request, db, mode="login", next=next, error="Email or password is incorrect."), status_code=400)
    request.session["user_id"] = user.id
    guest_cart = request.session.get("cart", {})
    for raw_id, quantity in guest_cart.items() if isinstance(guest_cart, dict) else []:
        product = db.get(Product, int(raw_id))
        if product:
            row = db.query(CartItem).filter_by(user_id=user.id, product_id=product.id).first()
            if row:
                row.quantity = min(row.quantity + int(quantity), product.stock)
            else:
                db.add(CartItem(user_id=user.id, product_id=product.id, quantity=min(int(quantity), product.stock)))
    request.session.pop("cart", None)
    db.commit()
    return RedirectResponse(next if next.startswith("/") else "/", status_code=303)


@app.get("/register", response_class=HTMLResponse)
def register_page(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse("auth.html", template_context(request, db, mode="register", next="/", error=None))


@app.post("/register")
def register(request: Request, full_name: Annotated[str, Form()], email: Annotated[str, Form()], password: Annotated[str, Form()], db: Session = Depends(get_db)):
    email = email.strip().lower()
    if len(password) < 6 or not full_name.strip():
        return templates.TemplateResponse("auth.html", template_context(request, db, mode="register", next="/", error="Use your name and a password with at least 6 characters."), status_code=400)
    if db.query(User).filter(User.email == email).first():
        return templates.TemplateResponse("auth.html", template_context(request, db, mode="register", next="/", error="An account with that email already exists."), status_code=400)
    user = User(full_name=full_name.strip(), email=email, password_hash=hash_password(password))
    db.add(user)
    db.commit()
    request.session["user_id"] = user.id
    return RedirectResponse("/", status_code=303)


@app.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=303)


@app.post("/wishlist/{product_id}")
def toggle_wishlist(product_id: int, request: Request, db: Session = Depends(get_db)):
    user = require_user(request, db)
    item = db.query(WishlistItem).filter_by(user_id=user.id, product_id=product_id).first()
    if item:
        db.delete(item)
    else:
        if not db.get(Product, product_id):
            raise HTTPException(status_code=404, detail="Product not found")
        db.add(WishlistItem(user_id=user.id, product_id=product_id))
    db.commit()
    return RedirectResponse(request.headers.get("referer", "/shop"), status_code=303)


@app.get("/wishlist", response_class=HTMLResponse)
def wishlist_page(request: Request, db: Session = Depends(get_db)):
    user = require_user(request, db)
    items = db.query(WishlistItem).options(joinedload(WishlistItem.product)).filter_by(user_id=user.id).all()
    return templates.TemplateResponse("wishlist.html", template_context(request, db, items=items))


@app.post("/products/{product_id}/review")
def create_review(product_id: int, request: Request, rating: Annotated[int, Form()], title: Annotated[str, Form()], body: Annotated[str, Form()], db: Session = Depends(get_db)):
    user = require_user(request, db)
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    existing = db.query(Review).filter_by(user_id=user.id, product_id=product_id).first()
    if existing:
        existing.rating, existing.title, existing.body = max(1, min(rating, 5)), title.strip(), body.strip()
    else:
        db.add(Review(user_id=user.id, product_id=product_id, rating=max(1, min(rating, 5)), title=title.strip() or "A thoughtful find", body=body.strip()))
    db.flush()
    reviews = db.query(Review).filter_by(product_id=product_id).all()
    product.review_count = len(reviews)
    product.rating = round(sum(review.rating for review in reviews) / len(reviews)) if reviews else 0
    db.commit()
    return RedirectResponse(f"/products/{product.slug}#reviews", status_code=303)


@app.get("/checkout", response_class=HTMLResponse)
def checkout_page(request: Request, db: Session = Depends(get_db)):
    user = require_user(request, db)
    lines = cart_lines(request, db, user)
    if not lines:
        return RedirectResponse("/cart", status_code=303)
    request.session["checkout_key"] = secrets.token_urlsafe(20)
    address = db.query(Address).filter_by(user_id=user.id, is_default=True).first()
    return templates.TemplateResponse("checkout.html", template_context(request, db, lines=lines, address=address, checkout_key=request.session["checkout_key"]))


@app.post("/checkout")
def checkout(
    request: Request,
    full_name: Annotated[str, Form()],
    street: Annotated[str, Form()],
    city: Annotated[str, Form()],
    state: Annotated[str, Form()],
    postal_code: Annotated[str, Form()],
    country: Annotated[str, Form()] = "United States",
    payment_method: Annotated[str, Form()] = "demo_card",
    checkout_key: Annotated[str, Form()] = "",
    db: Session = Depends(get_db),
):
    user = require_user(request, db)
    expected_key = request.session.get("checkout_key")
    if not expected_key or not secrets.compare_digest(checkout_key, expected_key):
        last_order_id = request.session.get("last_order_id")
        if last_order_id:
            return RedirectResponse(f"/account/orders/{last_order_id}", status_code=303)
        return RedirectResponse("/checkout", status_code=303)
    lines = cart_lines(request, db, user)
    if not lines:
        return RedirectResponse("/cart", status_code=303)
    fields = [full_name, street, city, state, postal_code, country]
    if any(not field.strip() for field in fields):
        return templates.TemplateResponse("checkout.html", template_context(request, db, lines=lines, address=None, checkout_key=expected_key, error="Please complete every shipping field."), status_code=400)
    for line in lines:
        if line["quantity"] > line["product"].stock:
            return templates.TemplateResponse("checkout.html", template_context(request, db, lines=lines, address=None, checkout_key=expected_key, error=f"{line['product'].name} no longer has enough stock."), status_code=409)
    totals = cart_totals(lines)
    address = db.query(Address).filter_by(user_id=user.id, is_default=True).first()
    if address:
        address.is_default = False
    db.add(Address(user_id=user.id, label="Default", street=street.strip(), city=city.strip(), state=state.strip(), postal_code=postal_code.strip(), country=country.strip(), is_default=True))
    order = Order(user_id=user.id, status="processing", payment_status="paid", **totals, shipping_name=full_name.strip(), shipping_street=street.strip(), shipping_city=city.strip(), shipping_state=state.strip(), shipping_postal_code=postal_code.strip(), shipping_country=country.strip())
    db.add(order)
    db.flush()
    for line in lines:
        product = line["product"]
        product.stock -= line["quantity"]
        db.add(OrderItem(order_id=order.id, product_id=product.id, product_name=product.name, unit_price_cents=product.price_cents, quantity=line["quantity"]))
    db.query(CartItem).filter(CartItem.user_id == user.id).delete(synchronize_session=False)
    db.commit()
    request.session.pop("checkout_key", None)
    request.session["last_order_id"] = order.id
    return RedirectResponse(f"/account/orders/{order.id}?placed=1", status_code=303)


@app.get("/account/orders", response_class=HTMLResponse)
def orders_page(request: Request, db: Session = Depends(get_db)):
    user = require_user(request, db)
    orders = db.query(Order).filter_by(user_id=user.id).order_by(Order.created_at.desc()).all()
    return templates.TemplateResponse("orders.html", template_context(request, db, orders=orders))


@app.get("/account/orders/{order_id}", response_class=HTMLResponse)
def order_detail(order_id: int, request: Request, db: Session = Depends(get_db)):
    user = require_user(request, db)
    order = db.query(Order).options(joinedload(Order.items)).filter(Order.id == order_id, Order.user_id == user.id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return templates.TemplateResponse("order_detail.html", template_context(request, db, order=order, placed=request.query_params.get("placed") == "1"))


@app.get("/admin", response_class=HTMLResponse)
def admin_page(request: Request, db: Session = Depends(get_db)):
    require_admin(request, db)
    products = db.query(Product).order_by(Product.created_at.desc()).all()
    orders = db.query(Order).options(joinedload(Order.user)).order_by(Order.created_at.desc()).limit(12).all()
    stats = {"products": db.query(Product).count(), "orders": db.query(Order).count(), "customers": db.query(User).filter(User.is_admin.is_(False)).count(), "revenue": db.query(Order).with_entities(Order.total_cents).all()}
    stats["revenue_cents"] = sum(row[0] for row in stats.pop("revenue"))
    return templates.TemplateResponse("admin.html", template_context(request, db, products=products, orders=orders, stats=stats))


@app.post("/admin/products")
def admin_create_product(request: Request, name: Annotated[str, Form()], category_id: Annotated[int, Form()], price: Annotated[str, Form()], stock: Annotated[int, Form()], image_url: Annotated[str, Form()], description: Annotated[str, Form()], db: Session = Depends(get_db)):
    require_admin(request, db)
    category = db.get(Category, category_id)
    if not category:
        raise HTTPException(status_code=400, detail="Category not found")
    slug = slugify(name)
    if db.query(Product).filter(Product.slug == slug).first():
        slug = f"{slug}-{int(utcnow().timestamp())}"
    product = Product(category_id=category_id, name=name.strip(), slug=slug, description=description.strip(), price_cents=round(float(price) * 100), compare_at_cents=None, sku=f"NEW-{int(utcnow().timestamp())}", image_url=image_url.strip() or PRODUCT_SEEDS[0]["image"], stock=max(0, stock), rating=0, review_count=0, featured=False)
    db.add(product)
    db.commit()
    return RedirectResponse("/admin", status_code=303)


@app.post("/admin/products/{product_id}/edit")
def admin_edit_product(product_id: int, request: Request, name: Annotated[str, Form()], price: Annotated[str, Form()], stock: Annotated[int, Form()], description: Annotated[str, Form()], db: Session = Depends(get_db)):
    require_admin(request, db)
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    product.name, product.price_cents, product.stock, product.description = name.strip(), round(float(price) * 100), max(0, stock), description.strip()
    db.commit()
    return RedirectResponse("/admin", status_code=303)


@app.post("/admin/orders/{order_id}/status")
def admin_update_order(order_id: int, request: Request, status: Annotated[str, Form()], db: Session = Depends(get_db)):
    require_admin(request, db)
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    allowed = {"processing", "packed", "shipped", "delivered", "cancelled"}
    if status not in allowed:
        return RedirectResponse("/admin", status_code=303)
    transitions = {
        "processing": {"processing", "packed", "cancelled"},
        "packed": {"packed", "shipped", "cancelled"},
        "shipped": {"shipped", "delivered"},
        "delivered": {"delivered"},
        "cancelled": {"cancelled"},
    }
    if status not in transitions.get(order.status, set()):
        return RedirectResponse("/admin", status_code=303)
    if status == "cancelled" and order.status != "cancelled":
        for item in order.items:
            if item.product:
                item.product.stock += item.quantity
        order.payment_status = "refunded-demo"
    order.status = status
    db.commit()
    return RedirectResponse("/admin", status_code=303)


@app.get("/health")
def health():
    return {"status": "ok", "service": "shopstack"}
