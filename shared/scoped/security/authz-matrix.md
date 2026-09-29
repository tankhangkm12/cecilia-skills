# Authorization matrix — the table that catches IDOR

<!-- scoped source: shared/scoped/security/authz-matrix.md — synced by tools/sync_common.py. Do not edit a copy. -->

Most real breaches in business software are not clever. They are a missing ownership check on an
endpoint that everybody assumed was covered. A matrix finds those by reading, before anyone writes a
scanner.

## 1. The matrix

One row per endpoint (`EP-nn`), one column per actor from the SRS. Build it from the API contract, not
from the code — then check the code against it.

| EP | Endpoint | Anonymous | Customer | Seller | Admin | Ownership condition | Deny response |
|---|---|---|---|---|---|---|---|
| EP-14 | `GET /orders/{id}` | ✗ | own only | own shop's | all | `order.buyer_id = actor.id OR order.shop_id IN actor.shops` | 404 (do not reveal existence) |
| EP-22 | `POST /orders/{id}/cancel` | ✗ | own, status PENDING | ✗ | all | same as EP-14 **+ state check BR-02** | 404, or 409 if owned but wrong state |

Three columns do the work:

- **Ownership condition** — the actual predicate, in terms of fields that exist. "Must be the owner"
  is not a condition; `order.buyer_id = actor.id` is. Where the condition needs a join, say which —
  that join is where it gets forgotten.
- **Deny response** — 404 vs 403 is a deliberate choice: 403 confirms the resource exists. Decide it
  per endpoint and be consistent; inconsistency itself is an information leak.
- **Anonymous column** — every ✓ here is a threat to model explicitly.

## 2. What to check once the matrix exists

| # | Check | The failure it catches |
|---|---|---|
| 1 | Every endpoint in the contract has a row | an endpoint nobody thought about — usually an admin or debug route |
| 2 | Every row has an ownership condition, or states why none is needed | the classic IDOR |
| 3 | The condition is enforced **in the query**, not after loading | a check-then-read that still exposes the row in logs or timing |
| 4 | Sort, filter and search fields are whitelisted | ordering by a column of another tenant's data; blind injection |
| 5 | Nested and derived resources re-check ownership | `/orders/{id}/items/{itemId}` where only the order is checked |
| 6 | Bulk and batch endpoints check **every** element | check the first, process all |
| 7 | State transitions check state **and** ownership atomically | cancel-twice races (`BR` rules belong here too) |
| 8 | Write endpoints whitelist fields | mass assignment of `role`, `status`, `price`, `ownerId` |
| 9 | The frontend's guards are a convenience, never the enforcement | a screen hidden but its endpoint open |
| 10 | Jobs, consumers and internal calls have an actor too | background work running as an implicit superuser |

## 3. Checking code against the matrix

Sample deliberately rather than reading everything: every row where the ownership condition needs a
join · every bulk endpoint · every endpoint added since the last review · every admin endpoint. For
each, cite the file and line that enforces it, or report it as unenforced.

Report the result as counts (`common/evidence.md`): endpoints with a stated ownership rule / total, and
endpoints verified in code / sampled. Never "authorization looks fine".

## 4. When there is no contract

Build the matrix from the router and say so — it is then `[inferred]` about intent, since an endpoint
list reveals what exists, not what was meant to exist. Recommend `cecilia-design` produce the
contract; a system whose permission model lives only in code has no way to notice a missing rule.
