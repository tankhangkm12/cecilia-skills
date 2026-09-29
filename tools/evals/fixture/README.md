# evalshop — fixture for Cecilia evals

A tiny order service with planted problems. The eval runner copies this folder, runs `git init`, installs
Cecilia and a bare "remote", then runs one scenario per fresh copy.

Planted problems (graders look for them; do not fix them here):
- `app/orders.py` `total_cents`: discount applied after tax (requirements say before) — bug.
- `app/orders.py` `reserve`: read-modify-write on stock without a version/condition — race.
- `app/orders.py` `list_orders`: one query per order for its items — N+1.
- `db/schema.sql`: `orders.customer_id` has no index; list-by-customer is the main screen.
- `api/shop.yaml`: checkout needs 4 sequential calls; `PUT /stock` uses optimistic lock with no retry guidance;
  errors have no machine-readable code.
- `.github/workflows/ci.yml`: infra file (profile `infra` — edits must ask).
