# Price List Management Service

Manages pricing, promotions, and price queries.

## Run
1. Copy `.env.example` to `.env` (optional).
2. Install deps:

   pip install -r requirements.txt

3. Start:

   uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload

## Endpoints
- GET /health
- POST /api/v1/prices
- GET /api/v1/prices/{product_id}?apply_promotions=true
- POST /api/v1/prices/query
- POST /api/v1/promotions
