# 05. Memory and context

## Three layers

1. **Working state:** current request, intermediate tool results, pending action and short session history. Ends or compacts with the run.
2. **Personal memory:** explicit preferences, facts, commitments and useful episodes that survive sessions.
3. **Procedural memory/harness:** evidence-backed lessons and versioned choices about retrieval/workflow. More stored facts alone are not harness improvement.

Each layer is employee-scoped. No global summary may combine private facts from all employees. Sharing is out of scope.

## Write pipeline

`evidence -> structured candidate -> scope/schema validation -> conflict handling -> commit -> embedding/index update`

### Evidence rules

- Explicit user statements and corrections can create active memories after identity is reliably bound.
- Inferred preferences start provisional; one action is not enough to establish an enduring preference.
- Calendar/email records are observations with external IDs and observation times, not permanent truths.
- Model guesses are not evidence.
- Unknown-speaker audio is not assigned to anyone's personal memory.
- Words inside a received email cannot be treated as instructions to update assistant rules or send a message.
- Do not infer personality, health, demographics, emotional state or workplace competence.

Structured extraction output:

```json
{
  "items": [
    {
      "kind": "preference",
      "key": "scheduling.preferred_period",
      "text": "Prefers afternoon meetings.",
      "value": "afternoon",
      "certainty": "explicit",
      "sourceSpan": "I prefer afternoon meetings.",
      "validUntil": null
    }
  ]
}
```

No employeeId, orgId, permissions, connectionId or approval field is accepted from the extractor. The server injects scope and source IDs. Validate sourceSpan against the actual permitted evidence, and use deterministic item keys to avoid duplicate extraction on retries.

## Conflict and correction semantics

Example: Asha first says 'afternoons are best', then 'this week only, mornings are better'. The second statement is a temporary override with an expiry, not a permanent deletion of the older preference.

- Explicit current correction outranks an older conflicting inference.
- Temporary instructions override only within their time/task scope.
- Ambiguous contradictions trigger clarification rather than automatic rewriting.
- Preserve the source event and supersession relationship for auditability.
- Store a current canonical value and append history consistently, as described in the data model.
- Do not rewrite the original transcript to make the assistant look correct.

For the first implementation, support a small typed preference vocabulary: timeZone, scheduling preferred period, meeting duration, meeting buffer and email brevity. Unknown keys may remain ordinary notes but cannot become application configuration automatically.

## Context assembly order

The context builder is deterministic code. It assembles:

1. Immutable application policy and allowed typed tools.
2. Trusted run metadata: current date/time, employee timezone, mode and connection capability availability. Never inject tokens.
3. Active task-specific user instructions and required authorization facts, always included and not optimizer-controlled.
4. Applicable explicit personal preferences, depending on the bounded retrieval policy. Live safety constraints are never optional.
5. A short employee-scoped session window.
6. Relevant active memory notes with IDs, source and time.
7. Current tool evidence, explicitly labeled untrusted data.
8. Current request and bounded response requirements.

The editable preference policy is for convenience preferences, such as preferred meeting times. It cannot remove authorization, explicit current-task constraints, safety rules or consent.

Initial total context target: 4,000 application-supplied tokens, configurable within the hard ceiling. Record actual usage if the provider returns it. Prefer removing low-ranked historical episodes before explicit constraints. Never truncate the current approval payload or a required safety instruction to fit a budget; fail or reduce lower-priority context instead.

## Retrieval strategy

- Use ordinary scoped MongoDB reads for current typed preferences and current-session notes.
- Use scoped Atlas Vector Search for semantic historical retrieval when available.
- `semanticTopK` starts at 6; keep it configurable within bounded limits.
- Expand at most two related notes total in the MVP, with fresh scope/validity checks on every link.
- Deduplicate by memory ID and semantic key.
- Prefer explicit, valid and recent evidence when notes conflict; do not blindly trust the highest vector score.
- Rehydrate vector hits with fresh ordinary reads to reject stale/deleted/superseded notes.
- Stamp the context with employee memoryEpoch. Rebuild or invalidate pending proposals if relevant memory changed before execution.

If embeddings or the index are unavailable, retrieve current preferences and a bounded set of scoped recent/key-matched notes. Label this as lexical fallback. Do not let a fallback remove employee filters or search the entire collection.

## Data freshness

Do not describe previously captured email/calendar status as current without refresh. Each observation has `observedAt`, `externalId` and connector mode. Refresh calendar availability before finalizing a meeting proposal after a material delay. Ask the user to confirm ambiguous relative dates/timezones; do not guess among multiple plausible recipients.

Atlas indexing and Change Streams do not watch Google services by themselves. External data changes enter through explicit connector refresh or provider notifications, which are optional later work.

## Read-your-writes

An explicit preference update is acknowledged only after the canonical database write succeeds. It must influence the very next relevant request, even if embedding generation is still pending. Use the direct preference path and current-session committed note set, not a sleep-until-indexed workaround.

Background extraction jobs must check memoryEpoch and tombstones before committing. A user deleting a note while extraction is in flight must not have it resurrected by the delayed worker.

## Memory controls in the UI

- 'What do you remember about me?': list only that employee's notes with source/time/status.
- 'Correct': show old/new value and preserve a supersession chain.
- 'Forget': remove the item from retrieval immediately, purge derived copies and create a content-free suppression tombstone where necessary.
- 'Do not remember this': process the current task without creating long-term memory; traces must be minimized consistently.

For demo fixtures these controls can use the fixture identity. Live controls require authenticated owner access.

## Procedural lessons

A procedural lesson is a candidate insight such as 'check whether returned calendar records cover the requested time range'. It is stored with evidence, helpful/harmful counters if used, and a status. A counter is supporting evidence, not proof of general improvement.

Do not append unlimited instructions after every run. At most one relevant improvement proposal per cycle; deduplicate and keep bounded context. Promote executable behavior only through the gated harness process in [07](07-HARNESS-IMPROVEMENT.md).

## Privacy and output

Private context includes model prompts and traces, not just database records. Clear employee-specific buffers, use scoped caches, avoid cross-user optimizer batches, and restrict traces to their owner. Generic voice output such as 'Your draft is ready' is the default in a shared office. Private content belongs on an authorized personal surface, not a loudspeaker.
