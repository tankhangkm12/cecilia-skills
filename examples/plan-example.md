# Plan — SHOP-42 — Hủy đơn hàng (ví dụ)

> State: `IN APPROVAL` · Repo: ./ · Base branch: `develop` · Commits by: agents, locally inside the scope
> Environments in scope for agents: `local` · Production: never agents (A4) · Parallel writers: no

## 5. Batches
| Batch | Goal | IDs | Depends on | Parallel with | Contract version | Scope id |
|---|---|---|---|---|---|---|
| B-01 | Khách hủy đơn khi còn PENDING, hoàn tiền đúng một lần | FR-05, BR-02, AC-11..14 | — | — | `order-api.yaml` v3 | `SHOP-42-B01` |

## 6. Tasks and status
| Task | Role | Covers | Expected files (exact) | Commands | Status |
|---|---|---|---|---|---|
| BE-B01 | dev-be | FR-05, BR-02 | `src/order/**`, `src/app.module.ts`, `migrations/0042_order_version.sql` | `npm test -- order`, `npm run lint` | TODO |
| TEST-B01 | test | AC-11..14 | `test/order/**` | `npm run test:int -- order` | TODO |
| REV-B01-C | review | BE-B01 | — (read-only) | — | TODO |

## 12. Scope blocks

```cecilia-scope
{
  "task": "SHOP-42-B01",
  "write": [
    "src/order/**",
    "src/app.module.ts",
    "migrations/0042_order_version.sql",
    "test/order/**",
    "tensura/reports/SHOP-42/**"
  ],
  "commands": ["npm test -- order", "npm run lint", "npm run test:int -- order"],
  "environments": ["local"],
  "expires_hours": 72
}
```
