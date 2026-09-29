# Growth forecast — from business assumptions to "when does it break"

Answer, per table/collection, **how big, how fast, and when a limit is crossed** — before choosing a schema,
partition scheme, engine or instance size. Numbers are `[projected]` until measured (`numbers.md`).

## 1. Assumptions Cecilia approves (one table, before any calculation)

| Input | Low / expected / high | Source |
|---|---|---|
| active users (or tenants, devices) now | | analytics, sales plan |
| monthly growth (compound, e.g. 0.03 = +3 %/month) | | business plan; the high case is what capacity must survive |
| rows (documents) per user per month, per table | | the feature: orders/user/month × items/order… |
| peak factor (peak writes ÷ average) and when | | sale days, month end, school terms |
| retention (months kept online) | | law, contract, product |
| hardware facts: RAM, disk, write rate one primary sustains, restore throughput | | the instance or a measurement |
| RTO / RPO | | the business (backup-dr.md) |

Unknown input → ask with options; never invent. Say which input the answer is most sensitive to.

## 2. Size of one row / document

- SQL: `capacity.py rowsize --engine postgres|mysql --columns "…"` (±20 %).
- MongoDB: `capacity.py docsize --fields "…"`; field names are stored in every document.
- Best: seed 100k representative rows locally and measure (`engines/*.md` → size queries).

## 3. Forecast and thresholds

```
capacity.py forecast --users L,E,H --monthly-growth L,E,H --rows-per-user-month L,E,H \
  --row-bytes N --index-bytes-per-row N --months 36 --peak-factor L,E,H --retention-months R \
  --ram-gb G --storage-gb S --write-limit W --restore-mbps L,E,H --rto-minutes T
```
Prints the table at 6/12/24/36 months and **the first month each threshold is crossed**:
hot set > 70 % RAM · disk > 80 % · peak writes > one primary · full restore > RTO · a table > 100M rows.

## 4. Read the result

- The **high** scenario sets headroom; the **expected** one sets the plan; the low one tells what is wasted
  if growth disappoints.
- A threshold inside 12 months → a scaling decision now (`scaling-ladder.md`); 12–24 months → a dated review;
  beyond the horizon → note it.
- Growth rarely spreads evenly: find the 1–3 tables that make 80 % of the bytes and the writes; plan those.
- Re-run monthly with real numbers (growth, bytes/row) and record drift in the database doc §14.

## 5. Report (template `assets/growth-report.md`)

Assumptions table · forecast table · threshold table with dates · sensitivity · the tables that matter ·
recommended next step per threshold (a ladder rung, a date to revisit) · how to verify.
