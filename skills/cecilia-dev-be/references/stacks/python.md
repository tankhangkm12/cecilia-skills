# Python

Read after `code/principles.md`. Repo config (`pyproject.toml`, ruff/mypy/pyright config) wins.

## 1. Stack is never assumed
Existing repo → detect from `pyproject.toml`/`requirements*.txt`/lock files and confirm in one line.
New project and docs silent → ONE question offering 2–3 complete bundles, researched (current versions),
with a recommendation, e.g.:
(A) FastAPI + Pydantic v2 + SQLAlchemy 2 async + Alembic + uv + ruff + mypy, Python 3.12
(B) Django + DRF + Django ORM/migrations + poetry + ruff
(C) your own. Decide async vs sync once for the whole codebase.

## 2. Tooling defaults (propose if repo has none; adding tools = dependency → ask)
ruff (lint + format), mypy or pyright strict. Any explicit `Any` needs a comment explaining the boundary.

## 3. Types
Every parameter and return typed · modern syntax `list[str]`, `str | None` · Pydantic models/dataclasses for
structured data, never `dict[str, Any]` payloads · `Protocol` for ports (or `ABC` to force implementation) ·
`Final`, `Literal`, `NewType` where they clarify intent.

## 4. Files & names
`snake_case` + role suffix: `user_profile_service.py`, `user_profile_router.py`, `user_repository_port.py`,
`user_sqlalchemy_repository.py`, `create_user_dto.py`, `user_mapper.py`, `app_exception.py`, `error_code.py`.
Classes PascalCase, functions/vars snake_case, constants UPPER_SNAKE, private `_leading_underscore`.

## 5. DTOs (Pydantic v2)
```python
class CreateUserDto(BaseModel):
    """Input for user registration. Per API user §4.1 (FR-01)."""
    model_config = ConfigDict(extra="forbid", frozen=True)
    email: EmailStr = Field(max_length=255)
    password: str = Field(min_length=8, max_length=128)
    role: UserRole
```
Request and response DTOs are different classes; ORM rows never returned.

## 6. Repository & transactions
```python
class UserRepositoryPort(Protocol):
    async def find_active_by_email(self, email: str) -> User | None: ...
    async def save(self, user: User) -> User: ...

class UserSqlAlchemyRepository:          # infrastructure; select() lives only here
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
```
Services never receive `AsyncSession`/`select()`. Transactions via a unit of work in the service:
`async with self._uow: ...` (commit/rollback inside).

## 7. Exceptions & envelope (FastAPI example; Django equivalent via middleware/exception handler)
`AppException(error_code, http_status, message, context)` subclasses (`NotFoundException` 404,
`BusinessRuleException` 422 …); codes from `common/errors/error_code.py`; no `HTTPException` in services;
no bare `except:`; catch specific exceptions. requestId in a `ContextVar` set by middleware; one
`@app.exception_handler(AppException)` builds the envelope; logger reads the ContextVar.

## 8. Async
No blocking calls inside `async def` (`requests`, `time.sleep`, sync drivers); CPU work via
`asyncio.to_thread`/process pool; parallel with `asyncio.gather`/`TaskGroup`; timeouts via
`asyncio.timeout` or client settings; one reused `httpx.AsyncClient`.

## 9. Structure
Monolith level 1: `app/modules/<feature>/{router,service,repository_port,sqlalchemy_repository,mapper}.py`,
`dto/`, `entities/`; `app/common/` (exceptions, errors, context, envelope); `app/infrastructure/`
(config `BaseSettings`, logging, database + UoW + Alembic, cache, http, storage). DI via FastAPI `Depends`
or a container already used by the repo. Routers thin. Background jobs through a wrapped queue/scheduler port.

## 10. Common mistakes
Mutable default args · `except: pass` · import cycles (split interfaces, `TYPE_CHECKING`) · logic in
`__init__.py` · `from x import *` · naive `datetime.now()` · `os.environ` scattered · `print` · float money ·
f-string SQL.
