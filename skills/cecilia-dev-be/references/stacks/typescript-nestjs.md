# TypeScript / NestJS (Node backend)

Read after `code/principles.md`. Repo `tsconfig`, ESLint, Prettier win. ORM (TypeORM/Prisma/MikroORM),
validation library and broker come from tensura/docs/repo; silent → ask (one question, researched bundles).

## 1. TypeScript
`strict`, `noImplicitAny`, `strictNullChecks`, `noUnusedLocals/Parameters`, `noFallthroughCasesInSwitch` ·
no `any` (`unknown` + narrow) · no `@ts-ignore` (`@ts-expect-error` + reason if unavoidable) · explicit return
types on exported functions · `readonly` fields · async/await only, no floating promises · `===`, `??`/`?.`.

## 2. Files & names
kebab-case + role suffix: `user-profile.controller.ts`, `user-profile.service.ts`, `user.repository.port.ts`,
`user.typeorm.repository.ts`, `user.mapper.ts`, `create-user.dto.ts`, `user-response.dto.ts`,
`user.entity.ts`, `jwt-auth.guard.ts`, `response.interceptor.ts`, `all-exceptions.filter.ts`,
`kafka-event.publisher.ts`, `user-created.event.ts`. No `helpers.ts`/`utils.ts` buckets.

## 3. Bootstrap (main.ts) must have
Global prefix + URI versioning · `ValidationPipe({ whitelist: true, forbidNonWhitelisted: true, transform: true })` ·
global `ResponseInterceptor` (envelope) · global `AllExceptionsFilter` (single handler) · request-context
middleware (AsyncLocalStorage requestId + `X-Request-Id`) · wrapped logger · `enableShutdownHooks()`.

## 4. Layers
| Layer | Does | Must not |
|---|---|---|
| Controller | DTO in, call service, return plain data | logic, try/catch formatting, building envelope |
| Service | logic, transactions via a transaction-manager wrapper | inject ORM repositories/DataSource/EntityManager, use `HttpException` |
| Repository adapter | ORM queries, mapping to domain | business logic, opening transactions |

Ports as `abstract class` (Nest DI needs a runtime token): `export abstract class UserRepositoryPort { abstract findActiveByEmail(email: string): Promise<User | null>; }`
bound with `{ provide: UserRepositoryPort, useClass: UserTypeOrmRepository }`.

## 5. DTOs
`readonly` + `!` for required; every string `@MaxLength`, numbers `@Min/@Max`, arrays `@ArrayMaxSize`; response
DTO classes separate (no `@Exclude()` on entities as protection); mappers, not controllers, convert.

## 6. Exceptions
`AppException(errorCode, httpStatus, message, context)` + subclasses; codes from `common/errors/error-code.ts`;
filter logs 5xx with requestId and returns envelope.

## 7. Modules
Level 1 structure: `src/modules/<feature>/{*.module,*.controller,*.service,*.repository.port,*.typeorm.repository,*.mapper}.ts`,
`dto/`, `entities/`; `src/common/{decorators,filters,interceptors,guards,pipes,exceptions,errors,dto,context}`;
`src/infrastructure/{config,logging,database,cache,http,storage}`. Level 3: `domain/` (plain TS entities, no ORM
decorators), `application/use-cases`, `infrastructure/persistence` (ORM entities + mapper), `presentation/`.
Export only facades from a module (`exports: []` minimal); cross-module via facade port or `EventEmitter2` domain
events; `forwardRef()` means boundaries are wrong → report. Global modules only for config, logger, database.
Migrations always; `synchronize: false` everywhere.

## 8. Common mistakes
`@InjectRepository` in services · try/catch in controllers · returning entities · `synchronize: true` ·
`HttpException` in services · `forwardRef` cycles · logic in `XxxHelper` providers · `@Exclude` for hiding ·
`console.log` · `process.env` outside config.
