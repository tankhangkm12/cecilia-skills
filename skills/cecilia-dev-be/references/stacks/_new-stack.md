# Stack without a dedicated file (Go, Kotlin, C#, Rust, Dart, PHP, …)

1. Apply all of `code/*` (principles, architecture, infrastructure, boundaries, API, data, security).
2. Follow repo conventions and linter/formatter config.
3. None → the language's official/most adopted style guide (Effective Go + gofmt, Kotlin coding conventions,
   .NET naming guidelines, rustfmt + Rust API Guidelines, PSR-12…), researched; state which one in the brief (D3).
4. Propose in the report: "create `references/stacks/<lang>.md`" so Cecilia can settle the style.

## Template for a new stack file
```markdown
# <Language / framework>
Read after `code/principles.md`. Repo config (<files>) wins.
## 1. Stack is never assumed   (detection files; bundle question examples)
## 2. Tooling                  (lint/format/type-check)
## 3. Types                    (strictness, null/optional, money, time, enums)
## 4. Files & names            (table with examples, role suffixes)
## 5. DTOs & validation
## 6. Repository & transactions (port/adapter example)
## 7. Exceptions, envelope, requestId
## 8. Async / concurrency model
## 9. Structure                (level 1 and level 3 trees)
## 10. Common mistakes
```
Reuse the "cancel order" example across stack files so they are comparable.
