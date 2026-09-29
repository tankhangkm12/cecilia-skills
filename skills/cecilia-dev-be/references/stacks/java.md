# Java

Read after `code/principles.md`. Repo build and style config (Maven/Gradle, Checkstyle, Spotless) wins.

## 1. Stack is never assumed
Existing repo → detect from `pom.xml`/`build.gradle*`, confirm in one line. New project and docs silent →
ONE question with 2–3 researched bundles and a recommendation, e.g.:
(A) Java 21 + Spring Boot 3.x + Spring Data JPA + Flyway + MapStruct + Maven, blocking
(B) Java 21 + Quarkus + Hibernate Panache + Flyway + Gradle
(C) your own. Blocking vs reactive decided once. Lombok yes/no (records cover most needs).

## 2. Files & names
PascalCase = class name, role suffix kept: `UserProfileController`, `UserProfileService`, `UserRepository`
(port), `UserJpaAdapter`, `UserJpaRepository` (Spring Data, adapter-internal), `UserEntity`,
`CreateUserRequest`, `UserResponse`, `UserMapper`, `ErrorCode`, `GlobalExceptionHandler`. Packages lowercase:
`com.company.project.modules.user.application`.

## 3. Types
No raw types · no `Map<String,Object>` DTOs → `record` · `Optional<T>` only as return type · never return
null from public methods (Optional, empty collection, or exception) · `record` for DTOs/commands/value objects ·
sealed interfaces + records for sum types · enums instead of string/int constants.

## 4. Layers
Controllers thin (`@Valid @RequestBody`, call service, return DTO; envelope via `ResponseBodyAdvice`, errors
via `@RestControllerAdvice`) · services hold logic and `@Transactional` (readOnly for reads; beware
self-invocation → separate bean; no external calls inside; publish after commit with
`@TransactionalEventListener(AFTER_COMMIT)` or outbox) · constructor injection with `final` fields.

## 5. Repository — JPA hidden
```java
public interface UserRepository {                 // domain port
    Optional<User> findActiveByEmail(Email email);
    User save(User user);
}
@Repository @RequiredArgsConstructor
public class UserJpaAdapter implements UserRepository {
    private final UserJpaRepository jpa;          // exists only here
    private final UserMapper mapper;
    @Override public Optional<User> findActiveByEmail(Email email) {
        return jpa.findByEmailAndStatus(email.value(), UserStatus.ACTIVE).map(mapper::toDomain);
    }
}
```
No `EntityManager`/`Specification`/Criteria outside adapters; complex queries via `@Query`/jOOQ inside adapters.

## 6. Exceptions
`AppException extends RuntimeException` with `errorCode`, `HttpStatus`, context; subclasses per status; codes
from `ErrorCode`; handler maps `AppException`, `MethodArgumentNotValidException` (→ `data.fields`), and unknown
`Exception` (log error, generic 500). No `ResponseStatusException` in services; no empty catch.

## 7. requestId
`OncePerRequestFilter` at highest precedence: read/generate, `MDC.put`, response header, `MDC.clear()` in
finally. Propagate MDC across `@Async`/executors with a `TaskDecorator`.

## 8. Validation
Records with `@NotBlank @Email @Size(max=255)` etc.; every String sized, numbers bounded, collections sized;
business rules in services; mapping via MapStruct (if in repo) or dedicated mappers.

## 9. Structure
Level 1: `modules/<feature>/{UserController, UserService, UserRepository(port), UserJpaAdapter, UserMapper}`,
`dto/`, `entity/`. Level 3: `domain/{model,port,service,event}`, `application/{usecase,command}`,
`infrastructure/{persistence,gateway,messaging}`, `presentation/{controller,dto}`. Module fence:
package-private internals, public facade + DTOs only, ArchUnit test if available.

## 10. Common mistakes
Field `@Autowired` · injecting JpaRepository into services · returning entities · `@Transactional` on
controllers · EAGER fetch by default · N+1 (use `@EntityGraph`/join fetch) · `@Data` on JPA entities ·
`ddl-auto: update` · double money · `new Date()`/`SimpleDateFormat` · `System.out.println` · concatenated native SQL.
