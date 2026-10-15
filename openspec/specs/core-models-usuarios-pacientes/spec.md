# core-models-usuarios-pacientes

## Purpose

Provides the foundational persistence layer every later change builds on: staff/patient identities with uniqueness and consent guarantees, soft-delete auditing, repository-level agenda isolation, and versioned migrations with dev seeds.

## Requirements

### Requirement: Staff user identity with closed roles

The system SHALL persist each staff user with a unique email, a password hash field (minimum 60 characters, never plaintext), a role restricted to `odontologo | recepcionista | admin`, an optional link to an odontologo profile, and an active flag.

#### Scenario: Duplicate staff email is rejected

- **WHEN** a second user is persisted with an email already in use (case-insensitive match)
- **THEN** the system rejects it with a uniqueness violation and no second row is created

#### Scenario: Invalid role is rejected

- **WHEN** a user is persisted with a role outside `odontologo | recepcionista | admin`
- **THEN** the system rejects it with a constraint violation

#### Scenario: Password hash field cannot hold plaintext shortcuts

- **WHEN** a user is persisted with a `password_hash` shorter than 60 characters
- **THEN** the system rejects it with a check violation

### Requirement: Odontologo profile with per-professional amounts

The system SHALL persist one odontologo profile per linked user with a unique `user_id`, `monto_turno` and `monto_senia` as non-negative monetary values with distinct seed values per professional, and an active flag.

#### Scenario: Negative amount is rejected

- **WHEN** an odontologo is persisted with `monto_turno` or `monto_senia` below zero
- **THEN** the system rejects it with a check violation

#### Scenario: One user links to at most one odontologo profile

- **WHEN** a second odontologo profile is persisted with the same `user_id`
- **THEN** the system rejects it with a uniqueness violation

### Requirement: Patient identity with blocking consent

The system SHALL persist each patient with a unique DNI, contact fields, and a `consentimiento_datos` flag plus consent timestamp; a patient record SHALL NOT exist without recorded consent (flag true AND timestamp set).

#### Scenario: Duplicate DNI is rejected

- **WHEN** a second patient is persisted with an already-registered DNI
- **THEN** the system rejects it with a uniqueness violation (enables A2 recognition by DNI)

#### Scenario: Patient without consent is rejected

- **WHEN** a patient is persisted with `consentimiento_datos = false` or with a true flag but no consent timestamp
- **THEN** the system rejects it with a constraint violation (RN-CONSENTIMIENTO)

### Requirement: Soft-delete audit trail on core entities

The system SHALL record `is_active`, `created_at`, `updated_at` and `deleted_at` on Usuario, Odontologo and Paciente; deletion SHALL be a soft-delete (set `is_active = false` plus `deleted_at`) and SHALL never physically remove the row.

#### Scenario: Delete deactivates instead of removing

- **WHEN** a core entity is deleted
- **THEN** the row remains queryable by id with `is_active = false` and a non-null `deleted_at`

#### Scenario: Default queries hide deactivated rows

- **WHEN** core entities are listed through the standard read path
- **THEN** rows with `is_active = false` are excluded unless explicitly requested

### Requirement: Repository-level agenda isolation and atomic units of work

The system SHALL force every odontologo-scoped query through an `odontologo_id` filter that cannot be omitted by callers, and SHALL commit multi-entity writes (e.g. seed, future turno+pago+evento) atomically with rollback on any failure.

#### Scenario: Odontologo-scoped read is always filtered

- **WHEN** an odontologo-scoped entity is queried with an `odontologo_id` context
- **THEN** no row belonging to a different `odontologo_id` is ever returned, even if the caller passes no filter (RN-AISLAMIENTO, P8)

#### Scenario: Partial multi-entity write rolls back

- **WHEN** a unit of work containing two writes fails on the second write
- **THEN** the first write is rolled back and neither row is visible afterwards

### Requirement: Append-only protection prepared at database-role level

The system SHALL provide a least-privilege application database role that is denied `UPDATE` and `DELETE` on append-only audit tables (`turno_historial`, `evento_pago` when created in C-05/C-07), so audit rows are insert-only even against application bugs.

#### Scenario: Application role cannot rewrite audit history

- **WHEN** the application role attempts `UPDATE` or `DELETE` on an append-only audit table
- **THEN** the database denies the statement (RN-AUDIT, P9)

### Requirement: v2 tables modeled but with zero v1 writes

The system SHALL create `lista_espera` and `notificacion_whatsapp` tables via migration with no v1 write path: with `WHATSAPP_ENABLED=false` the application SHALL perform zero inserts into either table.

#### Scenario: v1 runtime never writes v2 tables

- **WHEN** any v1 flow (seeds, tests, request paths) executes with `WHATSAPP_ENABLED=false`
- **THEN** `lista_espera` and `notificacion_whatsapp` remain empty (P13)

### Requirement: Versioned migration with zero runtime table creation

The system SHALL create all tables exclusively through a versioned Alembic migration `001`; the runtime SHALL contain zero `create_all` calls.

#### Scenario: Fresh database builds from migrations only

- **WHEN** migrations are applied to an empty database
- **THEN** all core plus v2-off tables exist and `alembic current` reports exactly one applied head

#### Scenario: No runtime table creation exists

- **WHEN** the backend codebase is searched for `create_all`
- **THEN** zero matches exist outside tests that assert its absence (P3)

### Requirement: Dev seed with fictitious data only

The system SHALL seed the development database with 2 odontologos (distinct amounts, L–V 9–17 availability data reserved for C-04), 1 recepcionista, 1 admin, 5 patients with fictitious DNIs, 1 holiday and 1 block example; the seed SHALL contain zero real patient data and SHALL be idempotent.

#### Scenario: Seed is idempotent and fictitious

- **WHEN** the seed runs twice
- **THEN** the second run creates no duplicates and every patient DNI matches the fictitious-dev pattern (P11)
