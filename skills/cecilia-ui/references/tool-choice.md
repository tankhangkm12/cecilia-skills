# Choosing the design tool — ask once, record, stick to it

## 1. The question (U1, only when `DECISIONS.md` has no UI-tool row)

```
**[cecilia-ui · U1 · <TASK> · <app>] Q1 — Thiết kế giao diện ở đâu?**

| # | Công cụ | Được | Mất |
|---|---|---|---|
| A | Penpot (qua MCP) | vẽ trực tiếp, bạn mở file xem/sửa được, mã nguồn mở | cần MCP Penpot đang kết nối; mỗi lần ghi hỏi bạn nếu `design_writes = ask` |
| B | Figma (qua MCP) | quen thuộc, dev-fe đọc được design context | nhiều MCP Figma chỉ **đọc** — khi đó bạn vẽ, tôi viết spec và kiểm tra |
| C | Markdown | chạy mọi nơi, không cần tài khoản, diff được trong git | wireframe ASCII + spec, không có hình hi-fi |

**Tôi nghiêng về <X>** vì <lý do theo dự án: MCP nào đang kết nối, bạn đã có file thiết kế chưa>.
```

Before recommending, check which design connectors this session actually has (tool names containing
`penpot` or `figma`). Never recommend a tool that is not connected without saying it must be connected
first (connecting is Cecilia's action).

Record: `D-nn · UI tool: Penpot, project "<name>" / Figma, file <url> / Markdown · decided by: Cecilia <date>`.
Changing tools later is a new `D-nn` with what happens to the existing designs.

## 2. Penpot

- Start by reading the server's own guidance tool (the Penpot MCP exposes an overview / API-info tool) —
  it says how its code-execution tool addresses pages, boards and shapes in the version installed.
- Build in this order: a page per flow, a board per `SCR` × state × breakpoint, named
  `SCR-04 · order list · empty · mobile`. Components in a library page, named with their `CMP` id.
- Tokens: create colour/typography styles from `design-tokens.json`, same names.
- Every write (create, update, run code) goes through the guard: A3 per call while `ui.design_writes` is
  `ask`. Batch related changes into one clearly described call rather than dozens of tiny ones, and say
  what the call will change before asking.
- Export each board as PNG (or SVG) into `ui-exports/` with the board's name — the export tool is a read.

## 3. Figma

- Many Figma MCP servers are read-focused: design context, variables, screenshots, metadata. Check the
  tools the connected server offers.
- **Read-only server:** Cecilia (or her designer) draws; cecilia-ui writes the spec first (flows,
  wireframes, states, tokens), then reads her frames back to check every SCR × state exists, extracts
  variables into `design-tokens.json`, exports screenshots into `ui-exports/`, and reports gaps.
- **Server with write tools:** as Penpot §2 — same naming, same guard behaviour.
- Variables in Figma ↔ tokens in `design-tokens.json`: same names, one source (say which).

## 4. Markdown

- Everything lives in `<app>-ui.md`: flows and wireframes as ASCII in code blocks, one wireframe per SCR ×
  meaningful state (states that only swap text may share a wireframe with a table of texts).
- Tokens in `design-tokens.json`; component specs as tables.
- `ui-exports/` may stay empty; the exit gate row for exports reads "Markdown tool — n/a".
- Good for back-office tools, early product shaping, and teams without a design tool.

## 5. Whatever the tool

The UI design doc is the source dev-fe reads. The design file (Penpot/Figma) is linked from it with a
version or date; if the two disagree, the doc says which wins (default: the design file for visuals, the
doc for behaviour and states).
