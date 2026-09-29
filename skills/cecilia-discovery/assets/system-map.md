# System map — <project>

> **As-built survey** — repo <name> @ <commit sha> · read on <date>
> Depth: survey (wide, shallow). Nothing here is traced end to end unless a row says so.
> Runtime evidence: <what was read live, or "none — source only, so every runtime claim is [inferred]">

## 1. Diagram

```
<ASCII: deployables, sync arrows, async arrows, datastores, external partners.
 Mark anything uncertain with ?? and keep it in the diagram — absence is information.>
```

## 2. Components
| Component | Kind | Deployable? | Code lives in | Last touched | Tests? | Confidence |
|---|---|---|---|---|---|---|

## 3. Connections
| From | To | Channel | Evidence (file:line) | Confidence |
|---|---|---|---|---|

## 4. Data stores
| Store | Owned by | Tables/collections (count) | Migrations in repo? | Live schema read? |
|---|---|---|---|---|

## 5. Scheduled & async work
| Trigger | What runs | Touches | Evidence | Confidence |
|---|---|---|---|---|

## 6. External dependencies
| Partner / service | Called from | Timeout? | Retry? | Contract documented? |
|---|---|---|---|---|

## 7. Not found — expected but missing
| Thing | Expected because | Could not find | Meaning (labelled) |
|---|---|---|---|

## 8. Proposed depth for the next pass
| Area | Why it deserves depth | Proposed depth |
|---|---|---|

Out of scope for this pass: <stated plainly, so nobody assumes coverage>
