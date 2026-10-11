# 03. MongoDB data model

## Database boundaries

Use the event-provided Atlas cluster. Separate databases by execution mode:

- `march_demo`: fictional employees, consenting voice-profile metadata, fixture tool records and demo runs.
- `march_eval`: deterministic evaluation fixtures and candidate executions; no live tokens or live messages.
- `march_live`: optional, disabled until separately authorized and configured.

Prefer separate limited database credentials for runtime and evaluation. Runtime credentials must not administer Atlas or create users. If the supplied sandbox prevents creating narrow credentials, document that limitation and do not ingest private live data.

All employee-owned documents contain `_id`, `schemaVersion`, `mode`, `orgId`, `employeeId`, and `createdAt`. Use UUID strings for IDs and BSON UTC dates for timestamps. Store IANA timezone names, not fixed UTC offsets. API JSON uses ISO 8601 strings; persistence converts them to dates.

The three fixture IDs are `emp_asha`, `emp_ben` and `emp_casey`. IDs are opaque routing keys, not permissions.

## Collections

### `employees`

Fields: displayName, timeZone, enabled, consent `{voiceEnrollment, audioCloudTransfer, grantedAt, policyVersion}`, activeVoiceProfileId, activeHarnessVersionId, memoryEpoch, connectionIds, createdAt, updatedAt.

Only trusted enrollment/account-binding routes change identity or connection mappings. Increment `memoryEpoch` after changes that invalidate context or pending proposals. Do not store passwords or OAuth tokens here.

### `voice_profiles`

Fields: employee scope, profileVersion, modelId, modelRevision, embeddingDimension, sampleRateHz, encryptedProfile, encryptionKeyRef, calibrationId, enrollmentClipCount, revokedAt.

`encryptedProfile` holds an application-encrypted serialized embedding set. Keys remain outside MongoDB, preferably in the OS keychain or an approved secret store. Use an established authenticated-encryption library, never custom cryptography. Do not put voice embeddings in text Vector Search or expose them through the API. Local memory may cache decrypted profiles until revocation/restart.

Raw clips are not stored by default. Transient recordings are deleted after inference; accidental logs/temp files are included in cleanup.

### `connections`

Fields: provider `fixture | google | aside`, externalAccountId, displayEmail, allowedCapabilities, grantedScopes, secretRef, status, lastVerifiedAt, providerMetadata.

The server binds each connection to exactly one employee. Store secret references rather than refresh tokens in ordinary documents. `provider=aside` remains disabled without capability and isolation proof. `status` includes disabled, ready, expired, revoked and unverified.

### `sessions`

Fields: channel, state, lastActiveAt, lastRunId, shortHistory, pendingActionIds, expiresAt.

Keep shortHistory bounded. A session belongs to one employee permanently. Do not relabel an existing session when a new speaker arrives. Persist longer evidence selectively in runs/memories rather than allowing unbounded arrays.

### `memories`

Fields:

```json
{
  "_id": "example-memory-id",
  "schemaVersion": 1,
  "mode": "demo",
  "orgId": "demo_office",
  "employeeId": "emp_asha",
  "kind": "preference",
  "key": "scheduling.preferred_period",
  "text": "Prefers afternoon meetings.",
  "value": "afternoon",
  "status": "active",
  "certainty": "explicit",
  "source": {"type": "user_statement", "runId": "example-run-id", "eventId": "example-event-id"},
  "validFrom": "2026-10-11T12:00:00Z",
  "validUntil": null,
  "supersedesId": null,
  "relatedIds": [],
  "embedding": [],
  "embeddingModel": "configured-at-runtime",
  "embeddingVersion": 1,
  "embeddingStatus": "pending",
  "createdAt": "2026-10-11T12:00:00Z",
  "updatedAt": "2026-10-11T12:00:00Z"
}
```

The example is illustrative JSON, not a seed result. Empty embedding means pending and must not enter vector queries. Actual vector dimension is validated against the configured model/index.

Kinds: fact, preference, commitment, episode, procedural_lesson. Status: active, provisional, superseded, deleted. `certainty` is a categorical evidence label, not a made-up probability. Add expiresAt for temporary notes. Retain source identity and version so corrections and deletion can propagate.

Never store tool permissions, login credentials or inferred employee traits as memories.

### `harness_versions`

Fields: parentVersionId, config, configHash, patch, rationale, evidenceRunIds, evaluationId, lifecycleStatus, createdBy.

Config and patch are immutable after insertion. Status metadata may change, but never mutate a promoted version's payload. Candidate and active versions are separate documents. The employee's active pointer determines what new runs use.

### `runs`

Fields: sessionId, inputSource, transcriptRedacted, state, harnessVersionId, modelId, memoryEpoch, selectedMemoryIds, toolTrace, responseRedacted, failureCodes, startedAt, completedAt, metrics, correlationId.

Metrics include token counts when available, latencyMs, toolCallCount, connectorMode and outcome checks. Do not call unknown token counts zero. Tool traces hold minimal structured arguments/results; redact private bodies and secrets. For live mode, optimize from a minimized tenant-scoped evidence bundle, not a global raw transcript store.

### `pending_actions`

Fields: runId, connectionId, actionType, normalizedPayload, payloadHash, memoryEpoch, state, expiresAt, approval, executionAttemptId, providerResult, idempotencyKey.

`approval` includes principalId, approvedAt and approvedPayloadHash. `normalizedPayload` includes the exact sender/account, recipients, subject/body or event fields presented to the owner. No model-provided approval flag is trusted.

Retain terminal action records long enough to prevent duplicate dispatch; do not TTL-delete a pending action merely to implement expiry. Compare expiry in code and mark expired, then purge under the retention policy.

### `feedback`

Fields: runId, type `correction | explicit_accept | explicit_reject | verified_failure`, structuredCorrection, sourcePrincipalId, createdAt.

Authenticity of the feedback source matters. A message inside an email is not employee feedback. Store private correction text only as necessary; sanitized structural failure descriptions are sufficient for many optimizer inputs.

### `evaluations`

Fields: candidateVersionId, baselineVersionId, suiteVersion, fixtureSnapshotHash, split, seed, repetitions, modelId, results, aggregate, cost, gateDecision, failureCodes, startedAt, completedAt.

Per-case results contain expected/actual structural outcomes, not just an LLM's self-assigned score. Store split-specific counts and denominators. Aggregate summaries across fixture employees may omit private content.

### `fixture_items`

Employee-scoped fictional email, calendar, contact and simulated-send records. Fields: kind, externalId, payload, fixtureVersion. All provider code must still require scope, so fixtures exercise the same ownership boundaries as live connectors.

### `memory_tombstones`

Fields: sourceEventId or deletedMemoryId, deletionReasonCode, deletionEpoch, createdAt, expiresAt. No deleted private content. Prevent delayed extraction jobs from recreating a forgotten memory. Retain only the minimal suppression identifiers for the configured retention period.

## Indexes

Use schema validation for required scope, enums, BSON dates and bounded arrays. Application validation is still necessary. Examples below are mongosh syntax; run via an idempotent setup script against the configured mode database, never blindly against production.

```javascript
db.employees.createIndex({ mode: 1, orgId: 1, employeeId: 1 }, { unique: true });
db.voice_profiles.createIndex({ mode: 1, orgId: 1, employeeId: 1, profileVersion: 1 }, { unique: true });
db.connections.createIndex({ mode: 1, orgId: 1, employeeId: 1, provider: 1 });
db.sessions.createIndex({ mode: 1, orgId: 1, employeeId: 1, lastActiveAt: -1 });
db.memories.createIndex({ mode: 1, orgId: 1, employeeId: 1, status: 1, kind: 1, updatedAt: -1 });
db.memories.createIndex(
  { mode: 1, orgId: 1, employeeId: 1, key: 1 },
  { unique: true, partialFilterExpression: { kind: 'preference', status: 'active', key: { $type: 'string' } } }
);
db.memories.createIndex({ mode: 1, orgId: 1, employeeId: 1, 'source.eventId': 1, key: 1 }, { unique: true, partialFilterExpression: { 'source.eventId': { $type: 'string' }, key: { $type: 'string' } } });
db.harness_versions.createIndex({ mode: 1, orgId: 1, employeeId: 1, createdAt: -1 });
db.runs.createIndex({ mode: 1, orgId: 1, employeeId: 1, createdAt: -1 });
db.pending_actions.createIndex({ mode: 1, orgId: 1, employeeId: 1, idempotencyKey: 1 }, { unique: true });
db.pending_actions.createIndex({ state: 1, expiresAt: 1 });
db.evaluations.createIndex({ candidateVersionId: 1, suiteVersion: 1, split: 1 });
db.fixture_items.createIndex({ mode: 1, orgId: 1, employeeId: 1, kind: 1, externalId: 1 }, { unique: true });
db.memory_tombstones.createIndex({ mode: 1, orgId: 1, employeeId: 1, sourceEventId: 1 });
```

Make the source-event/key idempotency contract explicit for extracted notes. If a note has no semantic key, assign a deterministic extraction item key before insertion. Do not suppress distinct legitimate notes with an overly broad unique index.

## Atlas Vector Search

Use one shared memory collection, not a collection per employee. This follows MongoDB's multi-tenant Vector Search guidance but does not create database-level row authorization. The backend remains responsible for mandatory scope.

Create a separate search index named `memory_vector_v1` with a vector field `embedding` using the actual configured dimension and cosine similarity. Index `mode`, `orgId`, `employeeId`, `status`, `embeddingModel` and `embeddingVersion` as filter fields. `EMBEDDING_DIM` in examples is a configuration placeholder, not literal JSON.

```text
fields:
  vector: embedding, dimensions = EMBEDDING_DIM, similarity = cosine
  filter: mode
  filter: orgId
  filter: employeeId
  filter: status
  filter: embeddingModel
  filter: embeddingVersion
```

A typed repository constructs the following pipeline. The model never supplies the pipeline or scope:

```javascript
[
  { $vectorSearch: {
      index: 'memory_vector_v1',
      path: 'embedding',
      queryVector: queryEmbedding,
      numCandidates: 100,
      limit: 6,
      filter: {
        mode: scope.mode,
        orgId: scope.orgId,
        employeeId: scope.employeeId,
        status: 'active',
        embeddingModel: configuredModel,
        embeddingVersion: configuredVersion
      }
  } },
  { $project: { _id: 1, score: { $meta: 'vectorSearchScore' } } }
]
```

These are starting retrieval settings, not accuracy guarantees. Validate limits and capabilities against the actual sandbox. Use `semanticTopK` for limit, with a bounded configured `numCandidates` appropriate to the deployed index. Rehydrate returned IDs through a fresh scoped `find` that rechecks status, validity and source deletion. Search indexes are eventually updated; stale search hits must not resurrect forgotten or superseded content.

Load explicit current preferences through ordinary indexed reads for read-after-write behavior. Merge freshly committed notes in the current session while their embeddings/index updates are pending. Do not wait on semantic indexing before acknowledging a successfully committed explicit preference.

## Atomicity and consistency

- Correct a preference and insert its superseding version in one short transaction when supported, then increment memoryEpoch and invalidate dependent cached context.
- If transactions are unavailable, keep the canonical active preference in a single atomically updated scoped document and append history separately; document this fallback rather than pretending a two-write sequence is atomic.
- Dispatch using an atomic compare-and-set from pending to executing with owner, payload hash, expiry and approval checks. Claim execution once.
- Promote a harness by compare-and-set on `employees.activeHarnessVersionId`, verifying the expected parent is still active. A competing promotion must re-evaluate; it cannot overwrite blindly.
- Every active run keeps its original harness version. New runs see the new pointer.

## Retention and deletion

Suggested demo defaults: no raw-audio retention; ephemeral temp audio cleanup immediately; transcripts/redacted runs seven days; accepted synthetic preferences until reset; pending actions expire after five minutes but retain terminal deduplication records seven days. These are configurable product choices, not legal compliance claims.

TTL removal is asynchronous and is not an authorization or immediate-deletion mechanism. Check expiry on every read. Explicit forgetting/revocation immediately excludes data, increments memoryEpoch, cancels delayed extraction and invalidates pending actions/context; purge embeddings, linked notes, derived summaries, caches and private trace copies as applicable. Keep only redacted audit tombstones. Do not use an immutable audit log as an excuse to retain deleted private content.

Change Streams are optional for asynchronous updates and UI notifications. They observe MongoDB writes, not external Gmail/Calendar changes; those require their own connector refresh/webhooks. For the MVP, explicit service calls after committed writes are simpler and provide clearer read-your-writes behavior.

Sources: [multi-tenant Vector Search](https://www.mongodb.com/docs/vector-search/deployment/multi-tenant-architecture/), [Vector Search overview](https://www.mongodb.com/docs/atlas/atlas-search/vector-search/), [PyMongo Async](https://www.mongodb.com/docs/languages/python/pymongo-driver/current/reference/migration/).
