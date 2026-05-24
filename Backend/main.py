"""
Wall St. Bots FastAPI Backend
Unified API for lvl13.tech, bitbot13.tech, wallstbots.tech

Author: Claude (AI Senior Engineer)
Date: 2026-05-20 — v2 (admin system + bug fixes)
"""

import os
import jwt
from jwt import PyJWKClient
import json
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Any
from decimal import Decimal

from fastapi import FastAPI, Depends, HTTPException, status, Header, Query
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

SUPABASE_URL             = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY= os.getenv("SUPABASE_SERVICE_ROLE_KEY")
SUPABASE_ANON_KEY        = os.getenv("SUPABASE_ANON_KEY")
JWT_SECRET               = os.getenv("JWT_SECRET")
DATABASE_URL             = os.getenv("DATABASE_URL")

PAYPAL_CLIENT_ID         = os.getenv("PAYPAL_CLIENT_ID")
PAYPAL_CLIENT_SECRET     = os.getenv("PAYPAL_CLIENT_SECRET")
PAYPAL_MODE              = os.getenv("PAYPAL_MODE", "sandbox")
POLYGON_API_KEY          = os.getenv("POLYGON_API_KEY", "")

# Internal key used by GitHub Actions to push tracker data — never exposed publicly
INTERNAL_API_KEY         = os.getenv("INTERNAL_API_KEY", "")

# Admin codes: grant free lifetime SYNDICATE access — case-insensitive
ADMIN_CODES = {'adminm13'}

PAYPAL_API_BASE = (
    "https://api.paypal.com" if PAYPAL_MODE == "live"
    else "https://api.sandbox.paypal.com"
)

# ============================================================================
# DATABASE POOL
# ============================================================================

db_pool = ConnectionPool(
    DATABASE_URL,
    min_size=1,
    max_size=20,
    check=ConnectionPool.check_connection,
    kwargs={
        "connect_timeout": 10,
        "keepalives": 1,
        "keepalives_idle": 30,
        "keepalives_interval": 10,
        "keepalives_count": 5,
        "options": "-c statement_timeout=15000",
    },
)

def get_db_connection():
    return db_pool.getconn(timeout=10.0)

def return_db_connection(conn):
    db_pool.putconn(conn)

# ============================================================================
# FASTAPI APP
# ============================================================================

app = FastAPI(
    title="Wall St. Bots API",
    description="Unified backend for AI/Crypto/Stock trackers",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
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
    platform: str
    description: Optional[str] = None

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
    discount_amount: Optional[float] = None
    discount_percentage: Optional[float] = None
    message: str

class SubscriptionCreateRequest(BaseModel):
    user_id: str
    bot_count: int
    promo_code: Optional[str] = None
    referral_code: Optional[str] = None

class PayPalWebhookEvent(BaseModel):
    event_type: str
    resource: dict

class TrackerPushRequest(BaseModel):
    data_type: str   # 'state' | 'news' | 'signals' | 'reports'
    platform:  str   # 'lvl13' | 'bitbot13' | 'wallstbots'
    data:      Any

class StockPick(BaseModel):
    ticker: str
    name: Optional[str] = None

class SaveStocksRequest(BaseModel):
    stocks: List[StockPick]
    platform: str = "lvl13"

class AdminUserUpdate(BaseModel):
    role: Optional[str] = None          # 'user' | 'admin'
    max_free_bots: Optional[int] = None

class AdminTierUpdate(BaseModel):
    tier: str                            # 'member' | 'insider' | 'syndicate' | 'webmaster'
    expires_at: Optional[str] = None     # ISO date string or None for lifetime

class AdminCodeClaimRequest(BaseModel):
    code: str
    email: EmailStr
    password: str
    full_name: Optional[str] = None

# ============================================================================
# AUTH HELPERS
# ============================================================================

_jwks_client = None

def _get_jwks_client():
    global _jwks_client
    if _jwks_client is None and SUPABASE_URL:
        _jwks_client = PyJWKClient(f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json")
    return _jwks_client


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """Verify JWT token and return basic user claims (no DB hit).
    Supports both HS256 (old Supabase JWT_SECRET) and ES256 (new sb_publishable_ keys via JWKS).
    """
    token = credentials.credentials
    # Try HS256 first (old Supabase JWT secret format)
    if JWT_SECRET:
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
            user_id = payload.get("sub")
            if user_id:
                return {"user_id": user_id, "email": payload.get("email")}
        except jwt.InvalidTokenError:
            pass  # fall through to ES256

    # ES256 via Supabase JWKS (new sb_publishable_/sb_secret_ format)
    try:
        jwks = _get_jwks_client()
        if jwks is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Auth not configured")
        signing_key = jwks.get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["ES256"],
            audience="authenticated",
        )
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
        return {"user_id": user_id, "email": payload.get("email")}
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


def get_current_user_with_role(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """Verify JWT and fetch role + subscription_tier from DB. Use when role matters for the endpoint."""
    user = get_current_user(credentials)
    conn = get_db_connection()
    try:
        cursor = conn.cursor(row_factory=dict_row)
        cursor.execute(
            "SELECT role, max_free_bots, subscription_tier FROM users WHERE id = %s",
            (user["user_id"],)
        )
        row = cursor.fetchone()
        if row:
            user["role"]              = row["role"]
            user["max_free_bots"]     = row["max_free_bots"] or 0
            user["subscription_tier"] = (row["subscription_tier"] or "member").lower()
        else:
            user["role"]              = "user"
            user["max_free_bots"]     = 0
            user["subscription_tier"] = "member"
        return user
    finally:
        cursor.close()
        return_db_connection(conn)


def require_admin(current_user: dict = Depends(get_current_user_with_role)) -> dict:
    """Dependency: raises 403 unless the calling user is an admin."""
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return current_user


def require_webmaster(current_user: dict = Depends(get_current_user_with_role)) -> dict:
    """Dependency: raises 403 unless the calling user has subscription_tier = 'webmaster'.
    Webmaster is the owner/operator tier — grants access to all admin panels,
    financial data, member database, and tier management tools."""
    tier = (current_user.get("subscription_tier") or "member").lower()
    if tier != "webmaster":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Webmaster access required")
    return current_user


def call_supabase_auth(method: str, endpoint: str, data: dict = None) -> dict:
    url = f"{SUPABASE_URL}/auth/v1{endpoint}"
    headers = {"apikey": SUPABASE_ANON_KEY, "Content-Type": "application/json"}
    if method == "POST":
        response = requests.post(url, json=data, headers=headers)
    elif method == "GET":
        response = requests.get(url, headers=headers)
    else:
        raise ValueError(f"Unsupported method: {method}")
    if response.status_code not in [200, 201]:
        raise HTTPException(status_code=response.status_code, detail=response.text)
    return response.json()

# ============================================================================
# AUTH ENDPOINTS
# ============================================================================

@app.post("/auth/signup")
async def signup(request: SignUpRequest):
    """
    Sign up a new user.
    Creates auth user in Supabase Auth and a row in public.users.
    The DB trigger (users_generate_referral_code) auto-generates the referral code.
    After the user row is committed, we backfill the referral_codes table.
    """
    try:
        auth_response = call_supabase_auth("POST", "/signup", {
            "email": request.email,
            "password": request.password,
            "user_metadata": {"full_name": request.full_name or ""}
        })

        # Fix: new Supabase key format returns the user object at the top level
        # when email confirmation is required; fall back to nested {"user": {...}} format
        user_obj = auth_response.get("user") or auth_response
        user_id = user_obj["id"]

        conn = get_db_connection()
        try:
            cursor = conn.cursor(row_factory=dict_row)

            # 1. Insert user — DB trigger sets referral_code automatically.
            #    ON CONFLICT handles duplicate signups (e.g. email already confirmed).
            cursor.execute("""
                INSERT INTO users (id, email, full_name)
                VALUES (%s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    email     = EXCLUDED.email,
                    full_name = EXCLUDED.full_name
                RETURNING id, email, referral_code
            """, (user_id, request.email, request.full_name or ""))

            user = cursor.fetchone()
            conn.commit()

            # 2. Backfill referral_codes so the code is usable for invites.
            #    Non-fatal — user is created even if this step fails.
            if user and user.get("referral_code"):
                try:
                    cursor.execute("""
                        INSERT INTO referral_codes (code, created_by_user_id)
                        VALUES (%s, %s)
                        ON CONFLICT (code) DO NOTHING
                    """, (user["referral_code"], user_id))
                    conn.commit()
                except Exception:
                    pass

            return {
                "success": True,
                "user": {
                    "id":            user["id"],
                    "email":         user["email"],
                    "referral_code": user.get("referral_code"),
                },
                "message": "Signup successful. Check your email to confirm."
            }
        finally:
            cursor.close()
            return_db_connection(conn)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/auth/login")
async def login(request: LoginRequest):
    try:
        auth_response = call_supabase_auth("POST", "/token?grant_type=password", {
            "email": request.email,
            "password": request.password
        })
        return {
            "success":       True,
            "access_token":  auth_response["access_token"],
            "refresh_token": auth_response.get("refresh_token"),
            "expires_in":    auth_response.get("expires_in", 3600)
        }
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid email or password")


@app.post("/auth/refresh")
async def refresh_token(body: dict):
    """Refresh a Supabase JWT using a refresh_token."""
    try:
        refresh_tok = body.get("refresh_token")
        if not refresh_tok:
            raise HTTPException(status_code=400, detail="refresh_token required")
        auth_response = call_supabase_auth("POST", "/token?grant_type=refresh_token", {
            "refresh_token": refresh_tok
        })
        return {
            "success":       True,
            "access_token":  auth_response["access_token"],
            "refresh_token": auth_response.get("refresh_token"),
            "expires_in":    auth_response.get("expires_in", 3600)
        }
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Token refresh failed")


@app.post("/auth/logout")
async def logout(current_user: dict = Depends(get_current_user)):
    return {"success": True, "message": "Logged out"}


@app.on_event("startup")
async def startup_migration():
    """Add subscription tier columns to users table if they don't exist yet."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name='users' AND column_name='subscription_tier'
                ) THEN
                    ALTER TABLE users ADD COLUMN subscription_tier VARCHAR(20) DEFAULT 'free';
                END IF;
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name='users' AND column_name='tier_expires_at'
                ) THEN
                    ALTER TABLE users
                    ADD COLUMN tier_expires_at TIMESTAMP WITH TIME ZONE DEFAULT NULL;
                END IF;
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name='users' AND column_name='admin_code_used'
                ) THEN
                    ALTER TABLE users ADD COLUMN admin_code_used BOOLEAN DEFAULT FALSE;
                END IF;
            END $$;
        """)
        conn.commit()
        print("[startup] subscription_tier migration OK")
    except Exception as e:
        print(f"[startup] migration warning (non-fatal): {e}")
    finally:
        cursor.close()
        return_db_connection(conn)


@app.post("/auth/signup-with-admin-code")
async def signup_with_admin_code(request: AdminCodeClaimRequest):
    """
    Sign up a new user using an admin code.
    Grants free lifetime INSIDER access — no PayPal required.
    Returns an access token so the user is immediately logged in.
    """
    if request.code.lower() not in ADMIN_CODES:
        raise HTTPException(status_code=400, detail="Invalid admin code")

    # Enforce 5-account cap on admin code signups
    ADMIN_CODE_MAX = 5
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users WHERE admin_code_used = TRUE")
        used_count = cursor.fetchone()[0]
    finally:
        cursor.close()
        return_db_connection(conn)
    if used_count >= ADMIN_CODE_MAX:
        raise HTTPException(
            status_code=403,
            detail="This code has reached its maximum number of uses. Contact the admin."
        )

    # Create Supabase auth user
    try:
        auth_response = call_supabase_auth("POST", "/signup", {
            "email": request.email,
            "password": request.password,
            "user_metadata": {"full_name": request.full_name or ""}
        })
    except HTTPException as e:
        raise HTTPException(status_code=400, detail=f"Signup failed: {e.detail}")

    user_obj = auth_response.get("user") or auth_response
    user_id  = user_obj.get("id")
    if not user_id:
        raise HTTPException(status_code=400, detail="Could not create account — email may already be registered")

    # Create user row with SYNDICATE tier (lifetime)
    conn = get_db_connection()
    try:
        cursor = conn.cursor(row_factory=dict_row)
        cursor.execute("""
            INSERT INTO users (id, email, full_name, subscription_tier, tier_expires_at, admin_code_used)
            VALUES (%s, %s, %s, 'syndicate', NULL, TRUE)
            ON CONFLICT (id) DO UPDATE SET
                email             = EXCLUDED.email,
                full_name         = EXCLUDED.full_name,
                subscription_tier = 'syndicate',
                tier_expires_at   = NULL,
                admin_code_used   = TRUE
            RETURNING id, email, referral_code
        """, (user_id, request.email, request.full_name or ""))
        user = cursor.fetchone()
        conn.commit()

        # Backfill referral_codes (non-fatal)
        if user and user.get("referral_code"):
            try:
                cursor.execute("""
                    INSERT INTO referral_codes (code, created_by_user_id)
                    VALUES (%s, %s) ON CONFLICT (code) DO NOTHING
                """, (user["referral_code"], user_id))
                conn.commit()
            except Exception:
                pass
    finally:
        cursor.close()
        return_db_connection(conn)

    # Log the user in to get a JWT
    try:
        login_resp = call_supabase_auth("POST", "/token?grant_type=password", {
            "email":    request.email,
            "password": request.password,
        })
        access_token = login_resp.get("access_token")
    except Exception:
        access_token = None  # account created but email confirmation may be required

    return {
        "success":      True,
        "access_token": access_token,
        "tier":         "insider",
        "message":      "Welcome! You have free lifetime INSIDER access.",
        "needs_confirm": access_token is None,
    }


@app.post("/auth/claim-admin-access")
async def claim_admin_access(
    code: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Activate an admin code on an existing logged-in account.
    Sets subscription_tier = 'syndicate' with no expiry.
    """
    if code.lower() not in ADMIN_CODES:
        raise HTTPException(status_code=400, detail="Invalid admin code")

    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE users
            SET subscription_tier = 'syndicate', tier_expires_at = NULL
            WHERE id = %s
        """, (current_user["user_id"],))
        conn.commit()
        return {"success": True, "tier": "syndicate", "message": "SYNDICATE access activated!"}
    finally:
        cursor.close()
        return_db_connection(conn)

# ============================================================================
# USER ENDPOINTS
# ============================================================================

@app.get("/user/profile", response_model=UserResponse)
async def get_user_profile(current_user: dict = Depends(get_current_user)):
    conn = get_db_connection()
    try:
        cursor = conn.cursor(row_factory=dict_row)
        cursor.execute("""
            SELECT id, email, full_name, role, referral_code, referral_credit_balance, created_at
            FROM users WHERE id = %s
        """, (current_user["user_id"],))
        user = cursor.fetchone()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return {
            "id":                      str(user["id"]),
            "email":                   user["email"],
            "full_name":               user["full_name"],
            "role":                    user["role"],
            "referral_code":           user["referral_code"],
            "referral_credit_balance": float(user["referral_credit_balance"] or 0),
            "created_at":              str(user["created_at"])
        }
    finally:
        cursor.close()
        return_db_connection(conn)


@app.put("/user/profile")
async def update_user_profile(
    full_name: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Update user's profile. Returns current profile even if no changes."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor(row_factory=dict_row)
        if full_name:
            cursor.execute("""
                UPDATE users SET full_name = %s WHERE id = %s
                RETURNING id, email, full_name, role, referral_code, referral_credit_balance
            """, (full_name, current_user["user_id"]))
            updated_user = cursor.fetchone()
            conn.commit()
        else:
            # No changes — just return current profile
            cursor.execute("""
                SELECT id, email, full_name, role, referral_code, referral_credit_balance
                FROM users WHERE id = %s
            """, (current_user["user_id"],))
            updated_user = cursor.fetchone()
        return {"success": True, "user": dict(updated_user) if updated_user else {}}
    finally:
        cursor.close()
        return_db_connection(conn)


@app.get("/account/referral")
async def get_referral_info(current_user: dict = Depends(get_current_user)):
    """
    Return the current user's referral code, credit balance, and referred user count.
    Called by the referral dashboard section in all three app.js files.
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor(row_factory=dict_row)

        # Get user's referral code and balance
        cursor.execute("""
            SELECT u.referral_code, u.referral_credit_balance,
                   rc.used_count, rc.total_referral_credits
            FROM users u
            LEFT JOIN referral_codes rc ON rc.code = u.referral_code
            WHERE u.id = %s
        """, (current_user["user_id"],))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="User not found")

        return {
            "success":          True,
            "referral_code":    row["referral_code"],
            "credit_balance":   float(row["referral_credit_balance"] or 0),
            "referred_count":   row["used_count"] or 0,
            "total_earned":     float(row["total_referral_credits"] or 0),
            # Build shareable link
            "share_link":       f"https://lvl13.tech/#/get-yours?ref={row['referral_code']}",
        }
    finally:
        cursor.close()
        return_db_connection(conn)

# ============================================================================
# BOT ENDPOINTS
# ============================================================================

@app.get("/bots")
async def list_bots(current_user: dict = Depends(get_current_user)):
    conn = get_db_connection()
    try:
        cursor = conn.cursor(row_factory=dict_row)
        cursor.execute("""
            SELECT id, name, platform, status, created_at FROM bots
            WHERE user_id = %s AND status != 'deleted'
            ORDER BY created_at DESC
        """, (current_user["user_id"],))
        bots = cursor.fetchall()
        return {"success": True, "bots": [
            {"id": str(b["id"]), "name": b["name"], "platform": b["platform"],
             "status": b["status"], "created_at": str(b["created_at"])}
            for b in bots
        ]}
    finally:
        cursor.close()
        return_db_connection(conn)


@app.post("/bots")
async def create_bot(bot: BotCreate, current_user: dict = Depends(get_current_user)):
    conn = get_db_connection()
    try:
        cursor = conn.cursor(row_factory=dict_row)

        # Enforce portfolio limit based on user's tier
        cursor.execute("SELECT subscription_tier FROM users WHERE id = %s", (current_user["user_id"],))
        user_row = cursor.fetchone()
        tier = (user_row["subscription_tier"] or "free").lower() if user_row else "free"
        if tier == "webmaster":
            portfolio_limit = 99
        elif tier in ("insider", "elite", "premium", "syndicate"):
            portfolio_limit = 50
        elif tier == "pro":
            portfolio_limit = 10
        else:
            portfolio_limit = 3
        cursor.execute(
            "SELECT COUNT(*) AS cnt FROM bots WHERE user_id = %s AND status != 'deleted'",
            (current_user["user_id"],)
        )
        count_row = cursor.fetchone()
        if count_row["cnt"] >= portfolio_limit:
            raise HTTPException(
                status_code=400,
                detail=f"Portfolio limit reached ({portfolio_limit} max for your plan). Upgrade to add more."
            )

        cursor.execute("""
            INSERT INTO bots (user_id, name, platform, description)
            VALUES (%s, %s, %s, %s)
            RETURNING id, name, platform, status, created_at
        """, (current_user["user_id"], bot.name, bot.platform, bot.description))
        new_bot = cursor.fetchone()
        conn.commit()
        return {"success": True, "bot": {
            "id": str(new_bot["id"]), "name": new_bot["name"],
            "platform": new_bot["platform"], "status": new_bot["status"],
            "created_at": str(new_bot["created_at"])
        }}
    finally:
        cursor.close()
        return_db_connection(conn)


@app.get("/bots/{bot_id}")
async def get_bot(bot_id: str, current_user: dict = Depends(get_current_user)):
    conn = get_db_connection()
    try:
        cursor = conn.cursor(row_factory=dict_row)
        cursor.execute("""
            SELECT id, name, platform, status, created_at FROM bots
            WHERE id = %s AND user_id = %s
        """, (bot_id, current_user["user_id"]))
        bot = cursor.fetchone()
        if not bot:
            raise HTTPException(status_code=404, detail="Bot not found")

        cursor.execute("""
            SELECT total_value, entry_cost, gain_loss, gain_loss_pct, snapshot_date, strategy_name
            FROM bot_latest_performance WHERE bot_id = %s
        """, (bot_id,))
        performance = cursor.fetchone()

        cursor.execute("""
            SELECT id, symbol, asset_type, weight, quantity, entry_price
            FROM bot_holdings WHERE bot_id = %s AND removed_at IS NULL
        """, (bot_id,))
        holdings = cursor.fetchall()

        return {"success": True, "bot": {
            "id": str(bot["id"]), "name": bot["name"],
            "platform": bot["platform"], "status": bot["status"],
            "created_at": str(bot["created_at"]),
            "performance": {
                "total_value":    float(performance["total_value"]) if performance else 0,
                "entry_cost":     float(performance["entry_cost"]) if performance else 0,
                "gain_loss":      float(performance["gain_loss"]) if performance else 0,
                "gain_loss_pct":  float(performance["gain_loss_pct"]) if performance else 0,
                "snapshot_date":  str(performance["snapshot_date"]) if performance else None,
                "strategy_name":  performance["strategy_name"] if performance else None,
            } if performance else None,
            "holdings": [
                {"id": str(h["id"]), "symbol": h["symbol"], "asset_type": h["asset_type"],
                 "weight": float(h["weight"] or 0), "quantity": float(h["quantity"] or 0),
                 "entry_price": float(h["entry_price"] or 0)}
                for h in holdings
            ]
        }}
    finally:
        cursor.close()
        return_db_connection(conn)


@app.delete("/bots/{bot_id}")
async def delete_bot(bot_id: str, current_user: dict = Depends(get_current_user)):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE bots SET status = 'deleted' WHERE id = %s AND user_id = %s
        """, (bot_id, current_user["user_id"]))
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Bot not found")
        conn.commit()
        return {"success": True, "message": "Bot deleted"}
    finally:
        cursor.close()
        return_db_connection(conn)


@app.post("/bots/{bot_id}/holdings")
async def add_holding(bot_id: str, req: BotHoldingCreate, current_user: dict = Depends(get_current_user)):
    """Add a holding (stock/crypto) to a portfolio."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor(row_factory=dict_row)

        # Verify the bot exists and belongs to this user
        cursor.execute("""
            SELECT id FROM bots WHERE id = %s AND user_id = %s AND status = 'active'
        """, (bot_id, current_user["user_id"]))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Bot not found")

        # Cap at 50 holdings
        cursor.execute("""
            SELECT COUNT(*) as cnt FROM bot_holdings
            WHERE bot_id = %s AND removed_at IS NULL
        """, (bot_id,))
        if cursor.fetchone()["cnt"] >= 50:
            raise HTTPException(status_code=400, detail="Maximum 50 holdings per portfolio")

        symbol = req.symbol.upper().strip()

        # Try to fetch the last close price from Polygon as entry_price baseline
        entry_price = req.entry_price
        if entry_price is None and POLYGON_API_KEY:
            try:
                pr = requests.get(
                    f"https://api.polygon.io/v2/aggs/ticker/{symbol}/prev",
                    params={"apiKey": POLYGON_API_KEY}, timeout=5
                )
                if pr.status_code == 200:
                    results = pr.json().get("results", [])
                    if results:
                        entry_price = results[0].get("c")  # previous close
            except Exception:
                pass

        cursor.execute("""
            INSERT INTO bot_holdings (bot_id, symbol, asset_type, weight, quantity, entry_price)
            VALUES (%s, %s, 'stock', %s, %s, %s)
            RETURNING id, symbol, asset_type, weight, quantity, entry_price, added_at
        """, (bot_id, symbol, req.weight or 1000, req.quantity, entry_price))
        h = cursor.fetchone()
        conn.commit()
        return {
            "success": True,
            "holding": {
                "id":          str(h["id"]),
                "symbol":      h["symbol"],
                "asset_type":  h["asset_type"],
                "weight":      float(h["weight"] or 0),
                "quantity":    float(h["quantity"]) if h["quantity"] is not None else None,
                "entry_price": float(h["entry_price"]) if h["entry_price"] is not None else None,
                "added_at":    str(h["added_at"]),
            }
        }
    finally:
        cursor.close()
        return_db_connection(conn)


@app.delete("/bots/{bot_id}/holdings/{holding_id}")
async def remove_holding(bot_id: str, holding_id: str, current_user: dict = Depends(get_current_user)):
    """Soft-delete a holding from a portfolio."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE bot_holdings SET removed_at = NOW()
            WHERE id = %s
              AND bot_id = %s
              AND bot_id IN (
                  SELECT id FROM bots WHERE user_id = %s AND status = 'active'
              )
              AND removed_at IS NULL
        """, (holding_id, bot_id, current_user["user_id"]))
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Holding not found")
        conn.commit()
        return {"success": True}
    finally:
        cursor.close()
        return_db_connection(conn)


# ============================================================================
# PROMO CODE ENDPOINTS
# ============================================================================

@app.post("/promo-codes/validate", response_model=PromoCodeValidateResponse)
async def validate_promo_code(request: PromoCodeValidateRequest):
    conn = get_db_connection()
    try:
        cursor = conn.cursor(row_factory=dict_row)
        cursor.execute("""
            SELECT code, code_type, discount_amount, discount_percentage,
                   max_uses, current_uses, active, grants_unlimited_bots
            FROM promo_codes WHERE code = %s AND active = TRUE
        """, (request.code,))
        promo = cursor.fetchone()
        if not promo:
            return PromoCodeValidateResponse(valid=False, message="Promo code not found or expired")
        if promo["max_uses"] and promo["current_uses"] >= promo["max_uses"]:
            return PromoCodeValidateResponse(valid=False, message="Promo code has reached its usage limit")
        return PromoCodeValidateResponse(
            valid=True,
            discount_amount=float(promo["discount_amount"]) if promo["discount_amount"] else None,
            discount_percentage=float(promo["discount_percentage"]) if promo["discount_percentage"] else None,
            message="Promo code is valid"
        )
    finally:
        cursor.close()
        return_db_connection(conn)


@app.get("/subscriptions/validate-referral")
async def validate_referral_code(code: str = Query(..., description="Referral code to validate")):
    """
    Validate a referral code (REF_XXXXXXXX format generated per-user).
    Called from the Get Yours page on all three sites when a visitor
    arrives via a referral link.
    """
    if not code or len(code) < 4:
        return {"valid": False, "code": code, "message": "Invalid code format"}

    # Admin codes bypass the DB — grant free lifetime INSIDER access
    if code.lower() in ADMIN_CODES:
        return {
            "valid":   True,
            "code":    code,
            "type":    "admin_lifetime",
            "tier":    "insider",
            "message": "Admin code — free lifetime INSIDER access! Enter your details below to claim.",
        }

    conn = get_db_connection()
    try:
        cursor = conn.cursor(row_factory=dict_row)
        # Check in referral_codes table (one row per user)
        cursor.execute("""
            SELECT rc.code, u.email AS owner_email
            FROM referral_codes rc
            LEFT JOIN users u ON u.referral_code = rc.code
            WHERE rc.code = %s
        """, (code.upper(),))
        row = cursor.fetchone()
        if not row:
            return {"valid": False, "code": code, "message": "Referral code not found"}
        return {
            "valid":   True,
            "code":    row["code"],
            "message": "Valid referral code — you'll save $75 on your subscription",
            "discount": 75.00
        }
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
    base_price    = 799.00 if bot_count == 1 else 799.00 + (bot_count - 1) * 349.00
    discount_amount = 0.0
    applied_promo   = None
    applied_referral= None

    conn = get_db_connection()
    try:
        cursor = conn.cursor(row_factory=dict_row)

        if promo_code:
            cursor.execute("""
                SELECT discount_amount, discount_percentage, max_uses, current_uses
                FROM promo_codes WHERE code = %s AND active = TRUE
            """, (promo_code,))
            promo = cursor.fetchone()
            if promo and (not promo["max_uses"] or promo["current_uses"] < promo["max_uses"]):
                if promo["discount_amount"]:
                    discount_amount += float(promo["discount_amount"])
                if promo["discount_percentage"]:
                    discount_amount += base_price * (float(promo["discount_percentage"]) / 100)
                applied_promo = promo_code

        if referral_code:
            cursor.execute("SELECT code FROM referral_codes WHERE code = %s", (referral_code,))
            if cursor.fetchone():
                discount_amount += 75.00
                applied_referral = referral_code

    finally:
        cursor.close()
        return_db_connection(conn)

    final_price = max(0, base_price - discount_amount)
    return {
        "success":         True,
        "base_price":      base_price,
        "discount_amount": discount_amount,
        "final_price":     final_price,
        "applied_promo":   applied_promo,
        "applied_referral": applied_referral,
    }


@app.post("/paypal/webhook")
async def handle_paypal_webhook(event: PayPalWebhookEvent):
    """Handle PayPal webhooks for subscription payments."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO paypal_webhook_log (event_type, payload)
            VALUES (%s, %s)
        """, (event.event_type, json.dumps(event.dict())))
        conn.commit()

        if event.event_type == "CHECKOUT.ORDER.COMPLETED":
            resource  = event.resource
            txn_id    = resource.get("id", "")
            payer     = resource.get("payer", {})
            payer_email = payer.get("email_address", "")
            purchase_unit = resource.get("purchase_units", [{}])[0]
            amount_str  = purchase_unit.get("amount", {}).get("value", "0")
            try:
                amount = float(amount_str)
            except Exception:
                amount = 0.0

            # Identify which Level 13 site originated the sale.
            # The frontend PayPal form sends site name in `custom` (legacy IPN)
            # or `custom_id` (Orders API). Format is "<site>" or "<site>|ref=CODE".
            # Default to lvl13 if missing/unrecognized.
            origin_raw = (
                purchase_unit.get("custom_id")
                or resource.get("custom_id")
                or resource.get("custom")
                or ""
            ).strip().lower()
            # Strip any "|ref=…" suffix before validating
            site_token = origin_raw.split("|", 1)[0].strip()
            valid_platforms = {"lvl13", "bitbot13", "wallstbots"}
            origin_platform = site_token if site_token in valid_platforms else "lvl13"

            # Look up user by payer email
            cursor2 = conn.cursor(row_factory=dict_row)
            cursor2.execute("SELECT id FROM users WHERE email = %s", (payer_email,))
            user_row = cursor2.fetchone()
            if user_row:
                # Activate subscription. user_id is the key — a sale here counts
                # across ALL 3 sites; origin_platform just records where it came
                # from for ops/reporting.
                cursor2.execute("""
                    INSERT INTO subscriptions
                        (user_id, bot_count, final_price, status,
                         paypal_transaction_id, origin_platform)
                    VALUES (%s, 1, %s, 'completed', %s, %s)
                    ON CONFLICT DO NOTHING
                """, (user_row["id"], amount, txn_id, origin_platform))
                conn.commit()
            cursor2.close()

        return {"success": True, "message": "Webhook processed"}
    finally:
        cursor.close()
        return_db_connection(conn)

# ============================================================================
# TRACKER ENDPOINTS
# ============================================================================

VALID_DATA_TYPES = {"state", "news", "signals", "reports"}

def verify_internal_key(x_internal_key: str = Header(...)):
    if not INTERNAL_API_KEY:
        raise HTTPException(status_code=500, detail="INTERNAL_API_KEY not configured on server")
    if x_internal_key != INTERNAL_API_KEY:
        raise HTTPException(status_code=403, detail="Invalid internal key")


@app.post("/internal/tracker/push")
async def tracker_push(
    payload: TrackerPushRequest,
    _: None = Depends(verify_internal_key)
):
    if payload.data_type not in VALID_DATA_TYPES:
        raise HTTPException(status_code=400,
            detail=f"Invalid data_type. Must be one of: {', '.join(VALID_DATA_TYPES)}")
    conn = get_db_connection()
    try:
        cursor = conn.cursor(row_factory=dict_row)
        cursor.execute("""
            INSERT INTO tracker_live_data (data_type, platform, data, pushed_at)
            VALUES (%s, %s, %s::jsonb, NOW())
            ON CONFLICT (data_type, platform) DO UPDATE
                SET data      = EXCLUDED.data,
                    pushed_at = EXCLUDED.pushed_at
            RETURNING id, data_type, platform, pushed_at
        """, (payload.data_type, payload.platform, json.dumps(payload.data)))
        row = cursor.fetchone()
        conn.commit()
        return {
            "success":   True,
            "id":        row["id"],
            "data_type": row["data_type"],
            "platform":  row["platform"],
            "pushed_at": str(row["pushed_at"])
        }
    finally:
        cursor.close()
        return_db_connection(conn)


@app.get("/public/tracker/{data_type}")
async def tracker_read(data_type: str, platform: str = "lvl13"):
    if data_type not in VALID_DATA_TYPES:
        raise HTTPException(status_code=400,
            detail=f"Invalid data_type. Must be one of: {', '.join(VALID_DATA_TYPES)}")
    conn = get_db_connection()
    try:
        cursor = conn.cursor(row_factory=dict_row)
        cursor.execute("""
            SELECT data, pushed_at FROM tracker_live_data
            WHERE data_type = %s AND platform = %s
        """, (data_type, platform))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404,
                detail=f"No {data_type} data found for platform '{platform}'")
        return {
            "success":   True,
            "data_type": data_type,
            "platform":  platform,
            "pushed_at": str(row["pushed_at"]),
            "data":      row["data"]
        }
    finally:
        cursor.close()
        return_db_connection(conn)

# ============================================================================
# STOCK SEARCH
# ============================================================================

@app.get("/stocks/search")
async def search_stocks(q: str = "", limit: int = 15, market: str = "all"):
    """
    Search tickers on Polygon.io.
    market=all    → NYSE + NASDAQ + AMEX + OTC + Pink Sheets  (stocks + otc markets)
    market=crypto → Cryptocurrencies only
    market=stocks → Exchange-listed stocks only (NYSE, NASDAQ, AMEX)
    market=otc    → OTC / Pink Sheets only
    """
    q = q.strip()
    if not q:
        return {"results": []}
    if not POLYGON_API_KEY:
        return {"results": [], "manual_entry": True}

    # Map the caller's market param to Polygon market values
    if market == "crypto":
        markets_to_search = ["crypto"]
    elif market == "stocks":
        markets_to_search = ["stocks"]
    elif market == "otc":
        markets_to_search = ["otc"]
    else:  # "all" — NYSE + NASDAQ + OTC + Pink Sheets
        markets_to_search = ["stocks", "otc"]

    try:
        all_results = []
        seen = set()
        for mkt in markets_to_search:
            r = requests.get("https://api.polygon.io/v3/reference/tickers", params={
                "search": q, "active": "true", "market": mkt,
                "limit": min(limit, 20), "apiKey": POLYGON_API_KEY,
            }, timeout=10)
            if r.status_code == 200:
                for t in r.json().get("results", []):
                    ticker = t.get("ticker", "")
                    if ticker and ticker not in seen:
                        seen.add(ticker)
                        all_results.append({
                            "ticker":   ticker,
                            "name":     t.get("name", ""),
                            "market":   t.get("market", ""),
                            "type":     t.get("type", ""),
                            "exchange": t.get("primary_exchange", ""),
                        })
        return {"results": all_results[:limit]}
    except Exception as e:
        return {"results": [], "error": str(e)}

# ============================================================================
# USER STOCK PICKS & SUBSCRIPTION
# ============================================================================

@app.post("/user/stocks")
async def save_user_stocks(request: SaveStocksRequest, current_user: dict = Depends(get_current_user)):
    if len(request.stocks) > 50:
        raise HTTPException(status_code=400, detail="Maximum 50 stocks allowed")
    platform = request.platform.lower()
    conn = get_db_connection()
    try:
        cursor = conn.cursor(row_factory=dict_row)
        cursor.execute("DELETE FROM user_stock_picks WHERE user_id = %s AND platform = %s",
                       (current_user["user_id"], platform))
        for s in request.stocks:
            cursor.execute("""
                INSERT INTO user_stock_picks (user_id, platform, ticker, company_name)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (user_id, platform, ticker) DO UPDATE
                    SET company_name = EXCLUDED.company_name
            """, (current_user["user_id"], platform,
                  s.ticker.upper().strip(), s.name or s.ticker.upper().strip()))
        cursor.execute("""
            INSERT INTO user_platform_subs (user_id, platform, status, provisioned_at)
            VALUES (%s, %s, 'active', NOW())
            ON CONFLICT (user_id, platform) DO UPDATE
                SET status = 'active', provisioned_at = NOW(), updated_at = NOW()
        """, (current_user["user_id"], platform))
        conn.commit()
        return {"success": True, "saved": len(request.stocks),
                "message": "Stock picks saved. Your private dashboard will be live within 24 hours."}
    finally:
        cursor.close()
        return_db_connection(conn)


@app.get("/user/stocks")
async def get_user_stocks(platform: str = "lvl13", current_user: dict = Depends(get_current_user)):
    conn = get_db_connection()
    try:
        cursor = conn.cursor(row_factory=dict_row)
        cursor.execute("""
            SELECT ticker, company_name, added_at FROM user_stock_picks
            WHERE user_id = %s AND platform = %s ORDER BY added_at
        """, (current_user["user_id"], platform.lower()))
        picks = cursor.fetchall()
        return {"success": True, "stocks": [
            {"ticker": p["ticker"], "name": p["company_name"], "added_at": str(p["added_at"])}
            for p in picks
        ]}
    finally:
        cursor.close()
        return_db_connection(conn)


@app.get("/user/subscription")
async def get_user_subscription(
    platform: str = "lvl13",
    current_user: dict = Depends(get_current_user_with_role)
):
    """
    Return subscription status for a given platform.
    Admin users are always treated as subscribed (free access).
    """
    # Admins always have access
    if current_user.get("role") == "admin":
        return {"success": True, "subscribed": True, "status": "admin", "provisioned_at": None}

    conn = get_db_connection()
    try:
        cursor = conn.cursor(row_factory=dict_row)
        cursor.execute("""
            SELECT status, provisioned_at, created_at FROM user_platform_subs
            WHERE user_id = %s AND platform = %s
        """, (current_user["user_id"], platform.lower()))
        sub = cursor.fetchone()
        return {
            "success":        True,
            "subscribed":     sub is not None,
            "status":         sub["status"] if sub else None,
            "provisioned_at": str(sub["provisioned_at"]) if sub and sub["provisioned_at"] else None,
        }
    finally:
        cursor.close()
        return_db_connection(conn)


@app.get("/subscriptions/current")
async def get_current_subscription(current_user: dict = Depends(get_current_user)):
    """
    Return the current user's subscription tier and status.
    Used by all three dashboards to populate the account drawer membership section.
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor(row_factory=dict_row)
        cursor.execute(
            "SELECT subscription_tier, tier_expires_at FROM users WHERE id = %s",
            (current_user["user_id"],)
        )
        row = cursor.fetchone()
        tier = row["subscription_tier"] if row else "free"
        expires_at = row["tier_expires_at"] if row else None

        # Determine max_portfolios from tier
        tier_lower = (tier or "member").lower()
        if tier_lower == "webmaster":
            max_portfolios = 99
        elif tier_lower == "syndicate":
            max_portfolios = 10
        elif tier_lower == "insider":
            max_portfolios = 3
        else:
            max_portfolios = 1

        # Format expiry timestamp as ISO string or None
        expiry_str = expires_at.isoformat() if expires_at else None

        return {
            "success":        True,
            "tier":           tier,
            "plan":           tier.capitalize(),
            "plan_name":      tier.capitalize() + " Plan",
            "status":         "active",
            "max_portfolios": max_portfolios,
            "tier_expires_at": expiry_str,
            "current_period_end": expiry_str,
        }
    except Exception as e:
        # Return member tier on any error rather than breaking the dashboard
        return {
            "success":        True,
            "tier":           "member",
            "plan":           "Member",
            "plan_name":      "Member Plan",
            "status":         "active",
            "max_portfolios": 1,
            "tier_expires_at": None,
            "current_period_end": None,
        }
    finally:
        cursor.close()
        return_db_connection(conn)


class PasswordResetRequest(BaseModel):
    email: str


@app.post("/auth/password-reset")
async def request_password_reset(body: PasswordResetRequest):
    """
    Trigger a Supabase password reset email for the given address.
    Proxies to Supabase Auth /auth/v1/recover using the anon key.
    Always returns success=True to avoid leaking whether an email exists.
    """
    try:
        resp = requests.post(
            f"{SUPABASE_URL}/auth/v1/recover",
            headers={
                "apikey": SUPABASE_ANON_KEY,
                "Content-Type": "application/json",
            },
            json={"email": body.email},
            timeout=10,
        )
        # Supabase returns 200 even if the email doesn't exist (security best practice)
    except Exception as e:
        pass  # Don't surface errors — always tell client "sent"
    return {"success": True, "message": "If that email is registered, a reset link has been sent."}


# ============================================================================
# ADMIN ENDPOINTS  (/admin/*)
# All require role = 'admin'
# ============================================================================

@app.get("/admin/stats")
async def admin_stats(admin: dict = Depends(require_admin)):
    """High-level platform stats: users, revenue, active subscriptions."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor(row_factory=dict_row)

        cursor.execute("SELECT COUNT(*) AS total FROM users")
        total_users = cursor.fetchone()["total"]

        cursor.execute("SELECT COUNT(*) AS total FROM users WHERE role = 'admin'")
        admin_users = cursor.fetchone()["total"]

        cursor.execute("""
            SELECT COUNT(*) AS total, COALESCE(SUM(final_price),0) AS revenue
            FROM subscriptions WHERE status = 'completed'
        """)
        payment_row = cursor.fetchone()

        cursor.execute("""
            SELECT COUNT(DISTINCT user_id) AS active
            FROM user_platform_subs WHERE status = 'active'
        """)
        active_subs = cursor.fetchone()["active"]

        cursor.execute("""
            SELECT platform, COUNT(*) AS cnt FROM tracker_live_data GROUP BY platform
        """)
        tracker_rows = cursor.fetchall()

        return {
            "success":      True,
            "total_users":  total_users,
            "admin_users":  admin_users,
            "total_revenue": float(payment_row["revenue"] or 0),
            "paid_orders":  payment_row["total"],
            "active_subs":  active_subs,
            "tracker_data": {r["platform"]: r["cnt"] for r in tracker_rows},
        }
    finally:
        cursor.close()
        return_db_connection(conn)


@app.get("/admin/users")
async def admin_list_users(
    limit: int = 50,
    offset: int = 0,
    search: Optional[str] = None,
    admin: dict = Depends(require_admin)
):
    """List all users with subscription status and payment totals."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor(row_factory=dict_row)
        where = "WHERE 1=1"
        params: list = []
        if search:
            where += " AND (u.email ILIKE %s OR u.full_name ILIKE %s)"
            params += [f"%{search}%", f"%{search}%"]

        cursor.execute(f"""
            SELECT
                u.id, u.email, u.full_name, u.role, u.referral_code,
                u.referral_credit_balance, u.max_free_bots, u.created_at,
                COALESCE(sub_counts.active_platforms, 0) AS active_platforms,
                COALESCE(pay_totals.total_paid, 0)       AS total_paid
            FROM users u
            LEFT JOIN (
                SELECT user_id, COUNT(*) AS active_platforms
                FROM user_platform_subs WHERE status = 'active'
                GROUP BY user_id
            ) sub_counts ON sub_counts.user_id = u.id
            LEFT JOIN (
                SELECT user_id, SUM(final_price) AS total_paid
                FROM subscriptions WHERE status = 'completed'
                GROUP BY user_id
            ) pay_totals ON pay_totals.user_id = u.id
            {where}
            ORDER BY u.created_at DESC
            LIMIT %s OFFSET %s
        """, params + [limit, offset])
        users = cursor.fetchall()

        cursor.execute(f"SELECT COUNT(*) AS total FROM users u {where}", params)
        total = cursor.fetchone()["total"]

        return {
            "success": True,
            "total":   total,
            "offset":  offset,
            "limit":   limit,
            "users": [
                {
                    "id":              str(u["id"]),
                    "email":           u["email"],
                    "full_name":       u["full_name"] or "",
                    "role":            u["role"],
                    "referral_code":   u["referral_code"],
                    "credit_balance":  float(u["referral_credit_balance"] or 0),
                    "max_free_bots":   u["max_free_bots"] or 0,
                    "active_platforms":u["active_platforms"],
                    "total_paid":      float(u["total_paid"] or 0),
                    "created_at":      str(u["created_at"]),
                }
                for u in users
            ]
        }
    finally:
        cursor.close()
        return_db_connection(conn)


@app.get("/admin/users/{user_id}")
async def admin_get_user(user_id: str, admin: dict = Depends(require_admin)):
    """Full detail on one user — profile, subs, payments, platform access."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor(row_factory=dict_row)
        cursor.execute("""
            SELECT id, email, full_name, role, referral_code,
                   referral_credit_balance, max_free_bots, created_at
            FROM users WHERE id = %s
        """, (user_id,))
        user = cursor.fetchone()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        cursor.execute("""
            SELECT platform, status, provisioned_at FROM user_platform_subs
            WHERE user_id = %s ORDER BY provisioned_at DESC
        """, (user_id,))
        subs = cursor.fetchall()

        cursor.execute("""
            SELECT id, bot_count, final_price, status, paypal_transaction_id, created_at
            FROM subscriptions WHERE user_id = %s ORDER BY created_at DESC
        """, (user_id,))
        payments = cursor.fetchall()

        return {
            "success": True,
            "user": {
                "id":             str(user["id"]),
                "email":          user["email"],
                "full_name":      user["full_name"] or "",
                "role":           user["role"],
                "referral_code":  user["referral_code"],
                "credit_balance": float(user["referral_credit_balance"] or 0),
                "max_free_bots":  user["max_free_bots"] or 0,
                "created_at":     str(user["created_at"]),
            },
            "subscriptions": [
                {"platform": s["platform"], "status": s["status"],
                 "provisioned_at": str(s["provisioned_at"]) if s["provisioned_at"] else None}
                for s in subs
            ],
            "payments": [
                {"id": str(p["id"]), "bot_count": p["bot_count"],
                 "amount": float(p["final_price"] or 0), "status": p["status"],
                 "txn_id": p["paypal_transaction_id"],
                 "created_at": str(p["created_at"])}
                for p in payments
            ]
        }
    finally:
        cursor.close()
        return_db_connection(conn)


@app.put("/admin/users/{user_id}")
async def admin_update_user(
    user_id: str,
    body: AdminUserUpdate,
    admin: dict = Depends(require_admin)
):
    """Update a user's role or max_free_bots. Used to grant/revoke admin."""
    if body.role and body.role not in ("user", "admin"):
        raise HTTPException(status_code=400, detail="role must be 'user' or 'admin'")

    conn = get_db_connection()
    try:
        cursor = conn.cursor(row_factory=dict_row)
        updates, params = [], []
        if body.role is not None:
            updates.append("role = %s::user_role")
            params.append(body.role)
        if body.max_free_bots is not None:
            updates.append("max_free_bots = %s")
            params.append(body.max_free_bots)
        if not updates:
            raise HTTPException(status_code=400, detail="Nothing to update")
        params.append(user_id)
        cursor.execute(
            f"UPDATE users SET {', '.join(updates)} WHERE id = %s RETURNING id, email, role, max_free_bots",
            params
        )
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="User not found")
        conn.commit()
        return {"success": True, "user": dict(row)}
    finally:
        cursor.close()
        return_db_connection(conn)


@app.post("/admin/users/{user_id}/grant-access")
async def admin_grant_platform_access(
    user_id: str,
    platform: str,
    admin: dict = Depends(require_admin)
):
    """Manually grant a user active subscription for a platform (no payment needed)."""
    if platform not in ("lvl13", "bitbot13", "wallstbots"):
        raise HTTPException(status_code=400, detail="Invalid platform")
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO user_platform_subs (user_id, platform, status, provisioned_at)
            VALUES (%s, %s, 'active', NOW())
            ON CONFLICT (user_id, platform) DO UPDATE
                SET status = 'active', provisioned_at = NOW(), updated_at = NOW()
        """, (user_id, platform))
        conn.commit()
        return {"success": True, "message": f"Access granted for {platform}"}
    finally:
        cursor.close()
        return_db_connection(conn)


@app.get("/admin/payments")
async def admin_list_payments(
    limit: int = 50,
    offset: int = 0,
    admin: dict = Depends(require_admin)
):
    """All payment records (subscriptions + PayPal webhook log)."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor(row_factory=dict_row)
        cursor.execute("""
            SELECT s.id, s.bot_count, s.final_price, s.status,
                   s.paypal_transaction_id, s.created_at,
                   u.email, u.full_name
            FROM subscriptions s
            JOIN users u ON u.id = s.user_id
            ORDER BY s.created_at DESC
            LIMIT %s OFFSET %s
        """, (limit, offset))
        payments = cursor.fetchall()

        cursor.execute("SELECT COUNT(*) AS total FROM subscriptions")
        total = cursor.fetchone()["total"]

        return {
            "success": True,
            "total":   total,
            "payments": [
                {
                    "id":       str(p["id"]),
                    "email":    p["email"],
                    "name":     p["full_name"] or "",
                    "bots":     p["bot_count"],
                    "amount":   float(p["final_price"] or 0),
                    "status":   p["status"],
                    "txn_id":   p["paypal_transaction_id"],
                    "date":     str(p["created_at"]),
                }
                for p in payments
            ]
        }
    finally:
        cursor.close()
        return_db_connection(conn)


@app.get("/admin/promo-codes")
async def admin_list_promo_codes(admin: dict = Depends(require_admin)):
    """List all promo codes and usage."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor(row_factory=dict_row)
        cursor.execute("""
            SELECT code, code_type, description, discount_amount, discount_percentage,
                   max_uses, current_uses, active, grants_unlimited_bots,
                   created_at, expires_at
            FROM promo_codes ORDER BY created_at DESC
        """)
        codes = cursor.fetchall()
        return {"success": True, "promo_codes": [dict(c) for c in codes]}
    finally:
        cursor.close()
        return_db_connection(conn)


# ============================================================================
# WEBMASTER ENDPOINTS  (/webmaster/*)
# Require subscription_tier = 'webmaster' (owner/operator only)
# ============================================================================

@app.get("/webmaster/members")
async def webmaster_list_members(
    limit: int = 100,
    offset: int = 0,
    search: Optional[str] = None,
    tier: Optional[str] = None,
    _wm: dict = Depends(require_webmaster)
):
    """Full member database: email, tier, join date, portfolio count, last activity."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor(row_factory=dict_row)
        conditions = ["1=1"]
        params: list = []
        if search:
            conditions.append("(u.email ILIKE %s OR u.full_name ILIKE %s)")
            params += [f"%{search}%", f"%{search}%"]
        if tier:
            conditions.append("u.subscription_tier = %s")
            params.append(tier)
        where = " AND ".join(conditions)

        cursor.execute(f"""
            SELECT
                u.id, u.email, u.full_name,
                COALESCE(u.subscription_tier, 'member') AS subscription_tier,
                u.tier_expires_at, u.created_at, u.role,
                COUNT(DISTINCT p.id) AS portfolio_count
            FROM users u
            LEFT JOIN user_portfolios p ON p.user_id = u.id
            WHERE {where}
            GROUP BY u.id, u.email, u.full_name, u.subscription_tier,
                     u.tier_expires_at, u.created_at, u.role
            ORDER BY u.created_at DESC
            LIMIT %s OFFSET %s
        """, params + [limit, offset])
        members = cursor.fetchall()

        cursor.execute(f"SELECT COUNT(*) AS total FROM users u WHERE {where}", params)
        total = cursor.fetchone()["total"]

        # Tier counts summary
        cursor.execute("""
            SELECT COALESCE(subscription_tier, 'member') AS tier, COUNT(*) AS cnt
            FROM users GROUP BY subscription_tier
        """)
        tier_counts = {r["tier"]: r["cnt"] for r in cursor.fetchall()}

        return {
            "success":     True,
            "total":       total,
            "offset":      offset,
            "limit":       limit,
            "tier_counts": tier_counts,
            "members": [
                {
                    "id":                str(m["id"]),
                    "email":             m["email"],
                    "full_name":         m["full_name"] or "",
                    "tier":              m["subscription_tier"] or "member",
                    "tier_expires_at":   str(m["tier_expires_at"]) if m["tier_expires_at"] else None,
                    "joined":            str(m["created_at"]),
                    "portfolio_count":   m["portfolio_count"],
                    "role":              m["role"],
                }
                for m in members
            ]
        }
    finally:
        cursor.close()
        return_db_connection(conn)


@app.put("/webmaster/members/{user_id}/tier")
async def webmaster_update_member_tier(
    user_id: str,
    body: AdminTierUpdate,
    _wm: dict = Depends(require_webmaster)
):
    """Update a member's subscription tier. Webmaster only."""
    valid_tiers = ("member", "insider", "syndicate", "webmaster")
    if body.tier.lower() not in valid_tiers:
        raise HTTPException(status_code=400, detail=f"tier must be one of {valid_tiers}")

    conn = get_db_connection()
    try:
        cursor = conn.cursor(row_factory=dict_row)
        expires = None
        if body.expires_at:
            try:
                expires = datetime.fromisoformat(body.expires_at)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid expires_at format — use ISO 8601")

        cursor.execute(
            """UPDATE users
               SET subscription_tier = %s, tier_expires_at = %s
               WHERE id = %s::uuid
               RETURNING id, email, subscription_tier, tier_expires_at""",
            (body.tier.lower(), expires, user_id)
        )
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="User not found")
        conn.commit()
        return {
            "success": True,
            "user": {
                "id":              str(row["id"]),
                "email":           row["email"],
                "tier":            row["subscription_tier"],
                "tier_expires_at": str(row["tier_expires_at"]) if row["tier_expires_at"] else None,
            }
        }
    finally:
        cursor.close()
        return_db_connection(conn)


@app.get("/webmaster/financials/weekly")
async def webmaster_weekly_financials(
    year: int = 0,
    _wm: dict = Depends(require_webmaster)
):
    """Weekly and monthly revenue breakdown with YTD running totals.
    Returns completed-subscription revenue grouped by ISO week and month."""
    if year == 0:
        year = datetime.now(timezone.utc).year
    conn = get_db_connection()
    try:
        cursor = conn.cursor(row_factory=dict_row)

        # Weekly breakdown — all completed subscriptions in the year
        cursor.execute("""
            SELECT
                EXTRACT(WEEK  FROM created_at)  AS week_num,
                EXTRACT(MONTH FROM created_at)  AS month_num,
                MIN(created_at::date)            AS week_start,
                MAX(created_at::date)            AS week_end,
                COUNT(*)                         AS new_subs,
                COALESCE(SUM(final_price), 0)   AS revenue
            FROM subscriptions
            WHERE status = 'completed'
              AND EXTRACT(YEAR FROM created_at) = %s
            GROUP BY week_num, month_num
            ORDER BY week_num
        """, (year,))
        week_rows = cursor.fetchall()

        # Monthly breakdown
        cursor.execute("""
            SELECT
                EXTRACT(MONTH FROM created_at)  AS month_num,
                TO_CHAR(created_at, 'Mon')       AS month_name,
                COUNT(*)                         AS new_subs,
                COALESCE(SUM(final_price), 0)   AS revenue
            FROM subscriptions
            WHERE status = 'completed'
              AND EXTRACT(YEAR FROM created_at) = %s
            GROUP BY month_num, month_name
            ORDER BY month_num
        """, (year,))
        month_rows = cursor.fetchall()

        # YTD totals
        cursor.execute("""
            SELECT
                COUNT(*)                        AS total_subs,
                COALESCE(SUM(final_price), 0)  AS ytd_revenue
            FROM subscriptions
            WHERE status = 'completed'
              AND EXTRACT(YEAR FROM created_at) = %s
        """, (year,))
        ytd = cursor.fetchone()

        # Build weekly list with YTD running total
        weeks = []
        running = 0.0
        for r in week_rows:
            rev = float(r["revenue"] or 0)
            running += rev
            weeks.append({
                "week":         int(r["week_num"]),
                "month":        int(r["month_num"]),
                "week_start":   str(r["week_start"]),
                "week_end":     str(r["week_end"]),
                "new_subs":     int(r["new_subs"]),
                "revenue":      rev,
                "ytd_running":  round(running, 2),
            })

        months = [
            {
                "month":     int(r["month_num"]),
                "name":      r["month_name"],
                "new_subs":  int(r["new_subs"]),
                "revenue":   float(r["revenue"] or 0),
            }
            for r in month_rows
        ]

        return {
            "success":      True,
            "year":         year,
            "ytd_revenue":  float(ytd["ytd_revenue"] or 0),
            "ytd_subs":     int(ytd["total_subs"]),
            "weeks":        weeks,
            "months":       months,
        }
    finally:
        cursor.close()
        return_db_connection(conn)


@app.get("/webmaster/revenue")
async def webmaster_revenue_summary(_wm: dict = Depends(require_webmaster)):
    """MRR, ARR, conversion rate, tier breakdown, and churn snapshot."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor(row_factory=dict_row)

        # All-time total revenue
        cursor.execute("""
            SELECT COALESCE(SUM(final_price), 0) AS total_revenue,
                   COUNT(*) AS total_orders
            FROM subscriptions WHERE status = 'completed'
        """)
        totals = cursor.fetchone()

        # This month
        cursor.execute("""
            SELECT COALESCE(SUM(final_price), 0) AS mrr,
                   COUNT(*) AS new_subs
            FROM subscriptions
            WHERE status = 'completed'
              AND DATE_TRUNC('month', created_at) = DATE_TRUNC('month', NOW())
        """)
        this_month = cursor.fetchone()

        # Last month
        cursor.execute("""
            SELECT COALESCE(SUM(final_price), 0) AS revenue
            FROM subscriptions
            WHERE status = 'completed'
              AND DATE_TRUNC('month', created_at) = DATE_TRUNC('month', NOW() - INTERVAL '1 month')
        """)
        last_month = cursor.fetchone()

        # Member counts by tier
        cursor.execute("""
            SELECT COALESCE(subscription_tier, 'member') AS tier, COUNT(*) AS cnt
            FROM users GROUP BY subscription_tier
        """)
        tier_counts = {r["tier"]: int(r["cnt"]) for r in cursor.fetchall()}

        total_members = sum(tier_counts.values())
        paid_members = (tier_counts.get("insider", 0)
                        + tier_counts.get("syndicate", 0)
                        + tier_counts.get("webmaster", 0))
        conversion = round(paid_members / total_members * 100, 1) if total_members else 0

        mrr = float(this_month["mrr"] or 0)
        arr = round(mrr * 12, 2)

        return {
            "success":        True,
            "mrr":            mrr,
            "arr":            arr,
            "total_revenue":  float(totals["total_revenue"] or 0),
            "total_orders":   int(totals["total_orders"]),
            "this_month_subs": int(this_month["new_subs"]),
            "last_month_rev": float(last_month["revenue"] or 0),
            "total_members":  total_members,
            "paid_members":   paid_members,
            "conversion_pct": conversion,
            "tier_counts":    tier_counts,
        }
    finally:
        cursor.close()
        return_db_connection(conn)


@app.get("/webmaster/member/{user_id}")
async def webmaster_member_detail(user_id: str, _wm: dict = Depends(require_webmaster)):
    """Full member profile for customer support: account info, portfolios, payments."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor(row_factory=dict_row)

        # Core user info
        cursor.execute("""
            SELECT id, email, full_name, role,
                   COALESCE(subscription_tier, 'member') AS subscription_tier,
                   tier_expires_at, created_at, referral_code,
                   referral_credit_balance, max_free_bots
            FROM users WHERE id = %s::uuid
        """, (user_id,))
        user = cursor.fetchone()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Portfolios
        cursor.execute("""
            SELECT id, name, platform, created_at
            FROM user_portfolios WHERE user_id = %s::uuid
            ORDER BY created_at DESC
        """, (user_id,))
        portfolios = cursor.fetchall()

        # Payment history
        cursor.execute("""
            SELECT id, bot_count, final_price, status,
                   paypal_transaction_id, created_at
            FROM subscriptions WHERE user_id = %s::uuid
            ORDER BY created_at DESC
        """, (user_id,))
        payments = cursor.fetchall()

        return {
            "success": True,
            "user": {
                "id":              str(user["id"]),
                "email":           user["email"],
                "full_name":       user["full_name"] or "",
                "role":            user["role"],
                "tier":            user["subscription_tier"],
                "tier_expires_at": str(user["tier_expires_at"]) if user["tier_expires_at"] else None,
                "joined":          str(user["created_at"]),
                "referral_code":   user["referral_code"],
                "credit_balance":  float(user["referral_credit_balance"] or 0),
            },
            "portfolios": [
                {"id": str(p["id"]), "name": p["name"],
                 "platform": p["platform"], "created_at": str(p["created_at"])}
                for p in portfolios
            ],
            "payments": [
                {"id": str(p["id"]), "bots": p["bot_count"],
                 "amount": float(p["final_price"] or 0), "status": p["status"],
                 "txn_id": p["paypal_transaction_id"], "date": str(p["created_at"])}
                for p in payments
            ],
        }
    finally:
        cursor.close()
        return_db_connection(conn)


@app.get("/webmaster/system")
async def webmaster_system_status(_wm: dict = Depends(require_webmaster)):
    """Platform health: DB connectivity, total users, last data refreshes."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor(row_factory=dict_row)
        cursor.execute("SELECT COUNT(*) AS total FROM users")
        total_users = cursor.fetchone()["total"]

        cursor.execute("""
            SELECT platform, MAX(updated_at) AS last_refresh, COUNT(*) AS record_count
            FROM tracker_live_data GROUP BY platform
        """)
        tracker_rows = cursor.fetchall()

        db_status = "healthy"
        db_latency_ms = None
        t0 = datetime.now(timezone.utc)
        cursor.execute("SELECT 1")
        cursor.fetchone()
        db_latency_ms = int((datetime.now(timezone.utc) - t0).total_seconds() * 1000)

        return {
            "success":       True,
            "db_status":     db_status,
            "db_latency_ms": db_latency_ms,
            "total_users":   int(total_users),
            "timestamp":     datetime.now(timezone.utc).isoformat(),
            "data_freshness": [
                {"platform": r["platform"],
                 "last_refresh": str(r["last_refresh"]) if r["last_refresh"] else None,
                 "records": int(r["record_count"])}
                for r in tracker_rows
            ],
        }
    finally:
        cursor.close()
        return_db_connection(conn)


@app.post("/webmaster/set-owner")
async def webmaster_set_owner(
    email: str,
    internal_key: str = Header(None, alias="X-Internal-Key")
):
    """One-time bootstrap: promote an account to webmaster tier.
    Requires the INTERNAL_API_KEY header — used during initial setup only."""
    if not INTERNAL_API_KEY or internal_key != INTERNAL_API_KEY:
        raise HTTPException(status_code=403, detail="Invalid internal key")
    conn = get_db_connection()
    try:
        cursor = conn.cursor(row_factory=dict_row)
        cursor.execute(
            """UPDATE users
               SET subscription_tier = 'webmaster', role = 'admin'
               WHERE email = %s
               RETURNING id, email, subscription_tier, role""",
            (email,)
        )
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"No user found with email: {email}")
        conn.commit()
        return {
            "success": True,
            "message": f"Account {email} promoted to webmaster + admin.",
            "user": {
                "id":    str(row["id"]),
                "email": row["email"],
                "tier":  row["subscription_tier"],
                "role":  row["role"],
            }
        }
    finally:
        cursor.close()
        return_db_connection(conn)


# ============================================================================
# EMAIL PREFERENCES
# ============================================================================

class EmailPrefsUpdate(BaseModel):
    email_enabled:      Optional[bool] = None
    email_daily:        Optional[bool] = None
    email_bot13_alerts: Optional[bool] = None
    email_weekly:       Optional[bool] = None
    email_monthly:      Optional[bool] = None
    email_source:       Optional[str]  = None   # 'site' | 'portfolio' | 'both'


@app.get("/user/email-prefs")
async def get_email_prefs(current_user: dict = Depends(get_current_user)):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT email_enabled, email_daily, email_bot13_alerts,
                   email_weekly, email_monthly, email_source
            FROM users WHERE id = %s
        """, (current_user["user_id"],))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="User not found")
        return {
            "email_enabled":      row["email_enabled"],
            "email_daily":        row["email_daily"],
            "email_bot13_alerts": row["email_bot13_alerts"],
            "email_weekly":       row["email_weekly"],
            "email_monthly":      row["email_monthly"],
            "email_source":       row["email_source"],
        }
    finally:
        cursor.close()
        return_db_connection(conn)


@app.put("/user/email-prefs")
async def update_email_prefs(
    body: EmailPrefsUpdate,
    current_user: dict = Depends(get_current_user)
):
    fields, values = [], []
    if body.email_enabled      is not None: fields.append("email_enabled = %s");      values.append(body.email_enabled)
    if body.email_daily        is not None: fields.append("email_daily = %s");        values.append(body.email_daily)
    if body.email_bot13_alerts is not None: fields.append("email_bot13_alerts = %s"); values.append(body.email_bot13_alerts)
    if body.email_weekly       is not None: fields.append("email_weekly = %s");       values.append(body.email_weekly)
    if body.email_monthly      is not None: fields.append("email_monthly = %s");      values.append(body.email_monthly)
    if body.email_source       is not None:
        if body.email_source not in ("site", "portfolio", "both"):
            raise HTTPException(status_code=400, detail="email_source must be 'site', 'portfolio', or 'both'")
        fields.append("email_source = %s"); values.append(body.email_source)

    if not fields:
        raise HTTPException(status_code=400, detail="No fields to update")

    values.append(current_user["user_id"])
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            f"UPDATE users SET {', '.join(fields)}, updated_at = NOW() WHERE id = %s",
            values
        )
        conn.commit()
        return {"success": True}
    finally:
        cursor.close()
        return_db_connection(conn)


# ── Admin: get all email subscribers for a platform ────────────────────────────
@app.get("/admin/email-subscribers")
async def get_email_subscribers(
    platform: str = Query(..., description="wallstbots | bitbot13 | lvl13"),
    x_internal_key: Optional[str] = Header(None, alias="X-Internal-Key"),
):
    """
    Called by GitHub Actions send_emails.py script.
    Returns all opted-in users + their portfolio holdings for the given platform.
    Requires X-Internal-Key header matching INTERNAL_API_KEY env var.
    """
    expected_key = os.environ.get("INTERNAL_API_KEY", "")
    if not expected_key or x_internal_key != expected_key:
        raise HTTPException(status_code=403, detail="Forbidden")

    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        # Get all email-enabled users
        cursor.execute("""
            SELECT u.id, u.email, u.full_name, u.role,
                   u.email_enabled, u.email_daily, u.email_bot13_alerts,
                   u.email_weekly, u.email_monthly, u.email_source
            FROM users u
            WHERE u.email_enabled = TRUE
            ORDER BY u.created_at
        """)
        users = cursor.fetchall()

        subscribers = []
        for u in users:
            # Determine tier
            tier = "free"
            if u["role"] in ("admin", "webmaster"):
                tier = "paid"
            else:
                cursor.execute("""
                    SELECT subscription_tier FROM bots
                    WHERE user_id = %s AND platform = %s
                    LIMIT 1
                """, (u["id"], platform))
                bot_row = cursor.fetchone()
                if bot_row:
                    tier = "paid"

            # Get holdings for this user on this platform
            cursor.execute("""
                SELECT bh.symbol
                FROM bot_holdings bh
                JOIN bots b ON b.id = bh.bot_id
                WHERE b.user_id = %s AND b.platform = %s
            """, (u["id"], platform))
            holdings = [r["symbol"] for r in cursor.fetchall()]

            # Parse first name from full_name
            full = u.get("full_name") or ""
            first_name = full.split()[0] if full.strip() else ""

            subscribers.append({
                "email":             u["email"],
                "first_name":        first_name,
                "tier":              tier,
                "email_daily":       u["email_daily"],
                "email_bot13_alerts": u["email_bot13_alerts"],
                "email_weekly":      u["email_weekly"],
                "email_monthly":     u["email_monthly"],
                "email_source":      u["email_source"],
                "portfolio_holdings": list(set(holdings)),
            })

        return {"subscribers": subscribers, "count": len(subscribers)}
    finally:
        cursor.close()
        return_db_connection(conn)


# ============================================================================
# HEALTH CHECK
# ============================================================================

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "Wall St. Bots API", "version": "2.0.0"}


@app.get("/health/db")
async def health_check_db():
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()
        return {
            "status":    "healthy",
            "database":  "connected",
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
    if db_pool:
        db_pool.close()

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
