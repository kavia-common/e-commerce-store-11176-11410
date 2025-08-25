import os
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# PUBLIC_INTERFACE
def get_settings() -> Dict[str, Any]:
    """Load service settings from environment variables."""
    return {
        "SERVICE_NAME": os.getenv("PRICE_SERVICE_NAME", "Price List Management Service"),
        "ENV": os.getenv("ENV", "development"),
        "ALLOWED_ORIGINS": os.getenv("ALLOWED_ORIGINS", "*"),
        # Database connectivity (if enabled by deployment)
        "POSTGRES_URL": os.getenv("PRICE_DB_URL"),
        "POSTGRES_USER": os.getenv("PRICE_DB_USER"),
        "POSTGRES_PASSWORD": os.getenv("PRICE_DB_PASSWORD"),
        "POSTGRES_DB": os.getenv("PRICE_DB_NAME"),
    }

settings = get_settings()

app = FastAPI(
    title="Price List Management Service",
    description="Manages product prices, promotions, discount codes, and price queries.",
    version="1.0.0",
    openapi_tags=[
        {"name": "health", "description": "Health checks"},
        {"name": "prices", "description": "Price management and queries"},
        {"name": "promotions", "description": "Promotion operations"},
    ],
)

allow_origins = [o.strip() for o in settings["ALLOWED_ORIGINS"].split(",")] if settings["ALLOWED_ORIGINS"] else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory store for demo purposes. Replace with DB repository in production.
PRICES: Dict[str, Dict[str, Any]] = {}  # key: product_id, value: dict with base price and currency
PROMOTIONS: Dict[str, float] = {}  # key: product_id, value: percent discount (0-100)


class PriceCreate(BaseModel):
    product_id: str = Field(..., description="Product id")
    currency: str = Field(..., description="ISO currency code")
    base_price: float = Field(..., description="Base price before discounts")


class PriceResponse(BaseModel):
    product_id: str = Field(..., description="Product id")
    currency: str = Field(..., description="ISO currency code")
    final_price: float = Field(..., description="Final price with promotions applied")
    base_price: float = Field(..., description="Base price")
    promotion_applied: Optional[float] = Field(None, description="Percent discount applied if any")


class PromotionUpsert(BaseModel):
    product_id: str = Field(..., description="Product id")
    percent_off: float = Field(..., ge=0, le=100, description="Percent discount 0-100")


class PriceQuery(BaseModel):
    product_id: str = Field(..., description="Product id")
    currency: str = Field(..., description="ISO currency code")
    include_promotions: bool = Field(True, description="Apply promotions if available")


@app.get("/health", tags=["health"], summary="Liveness probe", description="Return liveness info.")
async def health():
    return {"status": "ok", "service": settings["SERVICE_NAME"], "env": settings["ENV"]}


# PUBLIC_INTERFACE
@app.post("/api/v1/prices", tags=["prices"], summary="Create or update base price", response_model=PriceResponse)
async def upsert_price(payload: PriceCreate):
    PRICES[payload.product_id] = {"currency": payload.currency, "base_price": payload.base_price}
    # Compute final price using current promotions if any
    percent = PROMOTIONS.get(payload.product_id)
    final_price = payload.base_price
    if percent:
        final_price = round(payload.base_price * (1 - percent / 100), 2)
    return PriceResponse(
        product_id=payload.product_id,
        currency=payload.currency,
        base_price=payload.base_price,
        final_price=final_price,
        promotion_applied=percent,
    )


# PUBLIC_INTERFACE
@app.get("/api/v1/prices/{product_id}", tags=["prices"], summary="Get price for product", response_model=PriceResponse)
async def get_price(product_id: str, apply_promotions: bool = Query(True, description="Whether to apply active promotions")):
    if product_id not in PRICES:
        raise HTTPException(404, detail="Price not found")
    p = PRICES[product_id]
    base = p["base_price"]
    percent = PROMOTIONS.get(product_id) if apply_promotions else None
    final_price = base if not percent else round(base * (1 - percent / 100), 2)
    return PriceResponse(
        product_id=product_id,
        currency=p["currency"],
        base_price=base,
        final_price=final_price,
        promotion_applied=percent,
    )


# PUBLIC_INTERFACE
@app.post("/api/v1/prices/query", tags=["prices"], summary="Query price", response_model=PriceResponse)
async def query_price(payload: PriceQuery):
    if payload.product_id not in PRICES:
        raise HTTPException(404, detail="Price not found")
    p = PRICES[payload.product_id]
    if p["currency"] != payload.currency:
        # For simplification: return same base price if currency mismatch (no FX calc)
        pass
    base = p["base_price"]
    percent = PROMOTIONS.get(payload.product_id) if payload.include_promotions else None
    final_price = base if not percent else round(base * (1 - percent / 100), 2)
    return PriceResponse(
        product_id=payload.product_id,
        currency=p["currency"],
        base_price=base,
        final_price=final_price,
        promotion_applied=percent,
    )


# PUBLIC_INTERFACE
@app.post("/api/v1/promotions", tags=["promotions"], summary="Create or update promotion")
async def upsert_promotion(payload: PromotionUpsert):
    PROMOTIONS[payload.product_id] = payload.percent_off
    return {"status": "ok", "promotion": {"product_id": payload.product_id, "percent_off": payload.percent_off}}
