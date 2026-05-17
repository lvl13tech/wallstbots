"""
Wall St. Bots FastAPI Backend
Unified API for lvl13.tech, bitbot13.tech, wallstbots.tech

Author: Claude (AI Senior Engineer)
Date: 2026-05-16
"""

import os
import jwt
import json
from datetime import datetime, timedelta, timezone
from typing import Optional, List
from decimal import Decimal

from fastapi import FastAPI, Depends, HTTPException, status, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
import psycopg
from psycopg_pool import ConnectionPool
from psycopg.rows import dict_row
import requests
from dotenv import load_dotenv

load_dotenv()

# ============================================================================
# CONFIGURATION
# ============================================================================

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")
JWT_SECRET = os.getenv("JWT_SECRET")
DATABASE_URL = os.getenv("DATABASE_URL")

PAYPAL_CLIENT_ID = os.getenv("PAYPAL_CLIENT_ID")
PAYPAL_CLIENT_SECRET = os.getenv("PAYPAL_CLIENT_SECRET")
PAYPAL_MODE = os.getenv("PAYPAL_MODE", "sandbox")

PAYPAL_API_BASE = (
    "https://api.paypal.com" if PAYPAL_MODE == "live"
    else "https://api.sandbox.paypal.com"
)

# ============================================================================
# DATABASE POOL
# ============================================================================

db_pool = ConnectionPool(DATABASE_URL, min_size=1, max_size=20)

def get_db_connection():
    """Get a connection from the pool."""
    return db_pool.getconn()

def return_db_connection(conn):
    """Return a connection to the pool."""
    db_pool.putconn(conn)

# ============================================================================
# FASTAPI APP
# ============================================================================

app = FastAPI(
    title="Wall St. Bots API",
    description="Unified backend for AI/Crypto/Stock trackers",
    version="1.0.0"
)

# CORS for all three domains
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # local dev
        "https://lvl13.tech",
        "https://bitbot13.tech",
        "https://wallstbots.tech",
        "https://www.lvl13.tech",
        "https://www.bitbot13.tech",
        "https://www.wallstbots.tech",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBearer()

# ============================================================================
# MODELS
# ============================================================================

class SignUpRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: Optional[str] = None

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: str
    email: str
    full_name: Optional[str]
    role: str
    referral_code: str
    referral_credit_balance: float
    created_at: str

class BotCreate(BaseModel):
    name: str
    platform: str  # 'lvl13', 'bitbot13', 'wallstbots'
    description: Optional[str] = None

class BotResponse(BaseModel):
    id: str
    name: str
    platform: str
    status: str
    created_at: str

class BotHoldingCreate(BaseModel):
    symbol: str
    weight: float
    quantity: Optional[float] = None
    entry_price: Optional[float] = None

class PromoCodeValidateRequest(BaseModel):
    code: str
    bot_count: int = 1

class PromoCodeValidateResponse(BaseModel):
    valid: bool
    discount_amount: Optional[float]
    discount_percentage: Optional[float]
    message: str

class SubscriptionCreateRequest(BaseModel):
    user_id: str
    bot_count: int
    promo_code: Optional[str] = None
    referral_code: Optional[str] = None

class PayPalWebhookEvent(BaseModel):
    event_type: str
    resource: dict

# ============================================================================
# AUTH HELPERS
# ============================================================================

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """
    Verify JWT token and return user claims.
    Token comes from Supabase Auth.
    """
    try:
        token = credentials.credentials

        # Decode JWT (Supabase uses HS256 with JWT_SECRET)
        payload = jwt.decode(
            token,
            JWT_SECRET,
            algorithms=["HS256"]
        )

        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )

        return {"user_id": user_id, "email": payload.get("email")}

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired"
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )

def call_supabase_auth(method: str, endpoint: str, data: dict = None) -> dict:
    """Call Supabase Auth API."""
    url = f"{SUPABASE_URL}/auth/v1{endpoint}"

    headers = {
        "apikey": SUPABASE_ANON_KEY,
        "Content-Type": "application/json"
    }

    if method == "POST":
        response = requests.post(url, json=data, headers=headers)
    elif method == "GET":
        response = requests.get(url, headers=headers)
    else:
        raise ValueError(f"Unsupported method: {method}")

    if response.status_code not in [200, 201]:
        raise HTTPException(
            status_code=response.status_code,
            detail=response.text
        )

    return response.json()

# ============================================================================
# AUTH ENDPOINTS
# ============================================================================

@app.post("/auth/signup")
async def signup(request: SignUpRequest):
    """
    Sign up a new user.
    Creates auth user in Supabase Auth and row in public.users.
    """
    try:
        # Create auth user via Supabase
        auth_response = call_supabase_auth("POST", "/signup", {
            "email": request.email,
            "password": request.password,
            "user_metadata": {
                "full_name": request.full_name or ""
            }
        })

        user_id = auth_response["user"]["id"]

        # Create row in public.users (RLS will allow since they're authenticated)
        conn = get_db_connection()
        try:
            cursor = conn.cursor(row_factory=dict_row)

            cursor.execute("""
                INSERT INTO users (id, email, full_name)
                VALUES (%s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    email = EXCLUDED.email,
                    full_name = EXCLUDED.full_name
                RETURNING *
            """, (user_id, request.email, request.full_name))

            user = cursor.fetchone()
            conn.commit()

            return {
                "success": True,
                "user": {
                    "id": user["id"],
                    "email": user["email"],
                    "referral_code": user["referral_code"]
                },
                "message": "Signup successful. Check your email to confirm."
            }
        finally:
            cursor.close()
            return_db_connection(conn)

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/auth/login")
async def login(request: LoginRequest):
    """
    Log in with email and password.
    Returns JWT token from Supabase Auth.
    """
    try:
        auth_response = call_supabase_auth("POST", "/token?grant_type=password", {
            "email": request.email,
            "password": request.password
        })

        return {
            "success": True,
            "access_token": auth_response["access_token"],
            "refresh_token": auth_response.get("refresh_token"),
            "expires_in": auth_response.get("expires_in", 3600)
        }

    except Exception as e:
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password"
        )

@app.post("/auth/logout")
async def logout(current_user: dict = Depends(get_current_user)):
    """
    Log out the current user.
    (Frontend should discard JWT token)
    """
    return {"success": True, "message": "Logged out"}

# ============================================================================
# USER ENDPOINTS
# ============================================================================

@app.get("/user/profile", response_model=UserResponse)
async def get_user_profile(current_user: dict = Depends(get_current_user)):
    """Get current user's profile."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor(row_factory=dict_row)

        cursor.execute("""
            SELECT id, email, full_name, role, referral_code, referral_credit_balance, created_at
            FROM users
            WHERE id = %s
        """, (current_user["user_id"],))

        user = cursor.fetchone()

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        return {
            "id": str(user["id"]),
            "email": user["email"],
            "full_name": user["full_name"],
            "role": user["role"],
            "referral_code": user["referral_code"],
            "referral_credit_balance": float(user["referral_credit_balance"]),
            "created_at": str(user["created_at"])
        }
    finally:
        cursor.close()
        return_db_connection(conn)

@app.put("/user/profile")
async def update_user_profile(
    full_name: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Update user's profile."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor(row_factory=dict_row)

        if full_name:
            cursor.execute("""
                UPDATE users
                SET full_name = %s
                WHERE id = %s
                RETURNING *
            """, (full_name, current_user["user_id"]))

        updated_user = cursor.fetchone()
        conn.commit()

        return {"success": True, "user": updated_user}
    finally:
        cursor.close()
        return_db_connection(conn)

# ============================================================================
# BOT ENDPOINTS
# ============================================================================

@app.get("/bots")
async def list_bots(current_user: dict = Depends(get_current_user)):
    """List all bots for the current user."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor(row_factory=dict_row)

        cursor.execute("""
            SELECT id, name, platform, status, created_at
            FROM bots
            WHERE user_id = %s AND status != 'deleted'
            ORDER BY created_at DESC
        """, (current_user["user_id"],))

        bots = cursor.fetchall()

        return {
            "success": True,
            "bots": [
                {
                    "id": str(bot["id"]),
                    "name": bot["name"],
                    "platform": bot["platform"],
                    "status": bot["status"],
                    "created_at": str(bot["created_at"])
                }
                for bot in bots
            ]
        }
    finally:
        cursor.close()
        return_db_connection(conn)

@app.post("/bots")
async def create_bot(
    bot: BotCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create a new bot for the current user."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor(row_factory=dict_row)

        cursor.execute("""
            INSERT INTO bots (user_id, name, platform, description)
            VALUES (%s, %s, %s, %s)
            RETURNING id, name, platform, status, created_at
        """, (
            current_user["user_id"],
            bot.name,
            bot.platform,
            bot.description
        ))

        new_bot = cursor.fetchone()
        conn.commit()

        return {
            "success": True,
            "bot": {
                "id": str(new_bot["id"]),
                "name": new_bot["name"],
                "platform": new_bot["platform"],
                "status": new_bot["status"],
                "created_at": str(new_bot["created_at"])
            }
        }
    finally:
        cursor.close()
        return_db_connection(conn)

@app.get("/bots/{bot_id}")
async def get_bot(
    bot_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get a specific bot (with performance data)."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor(row_factory=dict_row)

        # Get bot
        cursor.execute("""
            SELECT id, name, platform, status, created_at
            FROM bots
            WHERE id = %s AND user_id = %s
        """, (bot_id, current_user["user_id"]))

        bot = cursor.fetchone()

        if not bot:
            raise HTTPException(status_code=404, detail="Bot not found")

        # Get latest performance
        cursor.execute("""
            SELECT total_value, entry_cost, gain_loss, gain_loss_pct, snapshot_date, strategy_name
            FROM bot_latest_performance
            WHERE bot_id = %s
        """, (bot_id,))

        performance = cursor.fetchone()

        # Get holdings
        cursor.execute("""
            SELECT id, symbol, asset_type, weight, quantity, entry_price
            FROM bot_holdings
            WHERE bot_id = %s AND removed_at IS NULL
        """, (bot_id,))

        holdings = cursor.fetchall()

        return {
            "success": True,
            "bot": {
                "id": str(bot["id"]),
                "name": bot["name"],
                "platform": bot["platform"],
                "status": bot["status"],
                "created_at": str(bot["created_at"]),
                "performance": {
                    "total_value": float(performance["total_value"]) if performance else 0,
                    "entry_cost": float(performance["entry_cost"]) if performance else 0,
                    "gain_loss": float(performance["gain_loss"]) if performance else 0,
                    "gain_loss_pct": float(performance["gain_loss_pct"]) if performance else 0,
                    "snapshot_date": str(performance["snapshot_date"]) if performance else None,
                    "strategy_name": performance["strategy_name"] if performance else None
                } if performance else None,
                "holdings": [
                    {
                        "id": str(h["id"]),
                        "symbol": h["symbol"],
                        "asset_type": h["asset_type"],
                        "weight": float(h["weight"]) if h["weight"] else 0,
                        "quantity": float(h["quantity"]) if h["quantity"] else 0,
                        "entry_price": float(h["entry_price"]) if h["entry_price"] else 0
                    }
                    for h in holdings
                ]
            }
        }
    finally:
        cursor.close()
        return_db_connection(conn)

@app.delete("/bots/{bot_id}")
async def delete_bot(
    bot_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Delete (soft delete) a bot."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE bots
            SET status = 'deleted'
            WHERE id = %s AND user_id = %s
        """, (bot_id, current_user["user_id"]))

        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Bot not found")

        conn.commit()

        return {"success": True, "message": "Bot deleted"}
    finally:
        cursor.close()
        return_db_connection(conn)

# ============================================================================
# PROMO CODE ENDPOINTS
# ============================================================================

@app.post("/promo-codes/validate", response_model=PromoCodeValidateResponse)
async def validate_promo_code(request: PromoCodeValidateRequest):
    """Validate a promo code and return discount."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor(row_factory=dict_row)

        cursor.execute("""
            SELECT code, code_type, discount_amount, discount_percentage,
                   max_uses, current_uses, active, grants_unlimited_bots
            FROM promo_codes
            WHERE code = %s AND active = TRUE
        """, (request.code,))

        promo = cursor.fetchone()

        if not promo:
            return PromoCodeValidateResponse(
                valid=False,
                message="Promo code not found or expired"
            )

        # Check usage limit
        if promo["max_uses"] and promo["current_uses"] >= promo["max_uses"]:
            return PromoCodeValidateResponse(
                valid=False,
                message="Promo code has reached its usage limit"
            )

        return PromoCodeValidateResponse(
            valid=True,
            discount_amount=float(promo["discount_amount"]) if promo["discount_amount"] else None,
            discount_percentage=float(promo["discount_percentage"]) if promo["discount_percentage"] else None,
            message="Promo code is valid"
        )
    finally:
        cursor.close()
        return_db_connection(conn)

# ============================================================================
# PAYMENT & SUBSCRIPTION ENDPOINTS
# ============================================================================

@app.post("/subscriptions/calculate-price")
async def calculate_subscription_price(
    bot_count: int,
    promo_code: Optional[str] = None,
    referral_code: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Calculate final subscription price with discounts."""

    # Base pricing
    if bot_count == 1:
        base_price = 799.00
    else:
        base_price = 799.00 + (bot_count - 1) * 349.00

    discount_amount = 0.0
    applied_promo = None
    applied_referral = None

    # Check promo code
    if promo_code:
        conn = get_db_connection()
        try:
            cursor = conn.cursor(row_factory=dict_row)

            cursor.execute("""
                SELECT discount_amount, discount_percentage, max_uses, current_uses
                FROM promo_codes
                WHERE code = %s AND active = TRUE
            """, (promo_code,))

            promo = cursor.fetchone()

            if promo and (not promo["max_uses"] or promo["current_uses"] < promo["max_uses"]):
                if promo["discount_amount"]:
                    discount_amount += float(promo["discount_amount"])
                if promo["discount_percentage"]:
                    discount_amount += base_price * (float(promo["discount_percentage"]) / 100)
                applied_promo = promo_code
        finally:
            cursor.close()
            return_db_connection(conn)

    # Check referral code
    if referral_code:
        conn = get_db_connection()
        try:
            cursor = conn.cursor(row_factory=dict_row)

            cursor.execute("""
                SELECT * FROM referral_codes WHERE code = %s
            """, (referral_code,))

            referral = cursor.fetchone()

            if referral:
                discount_amount += 75.00  # $75 referral credit
                applied_referral = referral_code
        finally:
            cursor.close()
            return_db_connection(conn)

    final_price = max(0, base_price - discount_amount)

    return {
        "success": True,
        "base_price": base_price,
        "discount_amount": discount_amount,
        "final_price": final_price,
        "applied_promo": applied_promo,
        "applied_referral": applied_referral
    }

@app.post("/paypal/webhook")
async def handle_paypal_webhook(event: PayPalWebhookEvent):
    """
    Handle PayPal webhooks for subscription payments.
    Verifies signature and processes payment events.
    """

    # TODO: Verify PayPal signature
    # See: https://developer.paypal.com/docs/checkout/integration-features/webhooks/

    conn = get_db_connection()
    try:
        cursor = conn.cursor()

        # Log webhook for debugging
        cursor.execute("""
            INSERT INTO paypal_webhook_log (event_type, payload)
            VALUES (%s, %s)
        """, (event.event_type, json.dumps(event.dict())))

        conn.commit()

        # Handle specific event types
        if event.event_type == "CHECKOUT.ORDER.COMPLETED":
            # Extract transaction details and activate subscription
            pass

        return {"success": True, "message": "Webhook processed"}

    finally:
        cursor.close()
        return_db_connection(conn)

# ============================================================================
# HEALTH CHECK
# ============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint - simple API status, no DB dependency."""
    return {
        "status": "ok",
        "service": "Wall St. Bots API",
        "version": "1.0.0"
    }

@app.get("/health/db")
async def health_check_db():
    """Database health check - tests actual DB connection."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()

        return {
            "status": "healthy",
            "database": "connected",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    finally:
        cursor.close()
        return_db_connection(conn)

# ============================================================================
# SHUTDOWN
# ============================================================================

@app.on_event("shutdown")
async def shutdown_event():
    """Close all database connections."""
    db_pool.close()

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
