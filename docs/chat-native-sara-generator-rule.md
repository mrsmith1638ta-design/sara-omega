# Chat-Native SARA Generator Rule

From this point, the adaptive tutor may run in chat-native mode with the human operator acting as the live SARA question generator.

This mode is distinct from deployed-runtime acceptance. It does not by itself promote the deployed service to `LIVE ACCEPTANCE PASS`; that still requires live deployed evidence for the full chain:

`SARA generation -> semantic duplicate rejection -> ROAD verification -> answer grading -> mastery update`

## Novelty Gate

Every next question must be generated from the full conversation history, not from a finite local template bank.

The novelty rule is strict:

- No previous question meaning.
- No previous correct-answer principle.
- No previous reasoning path.
- No recycled distractor logic.
- No noun or number swaps disguised as novelty.

A candidate question that repeats any prior meaning, answer principle, reasoning path, distractor structure, or cosmetic substitution must be rejected before presentation.

## Live Runtime Configuration Gate

Current deployed-runtime status remains `LIVE ACCEPTANCE: BLOCKED_CONFIGURATION` until the Railway service has all required live provider configuration present and valid:

- `SARA_GENERATOR_URL`
- `SARA_GENERATOR_TOKEN`
- `ROAD_VERIFIER_URL`
- `ROAD_VERIFIER_TOKEN`
- `SARA_TUTOR_HMAC_SECRET`

The architecture may be deployed while acceptance remains blocked. Binding the live SARA and ROAD services securely to the tutor runtime is the next required step before live acceptance can be attempted.

## Next Legitimate Milestone

The next legitimate milestone is runtime secret and endpoint binding followed by one exact end-to-end acceptance transaction with evidence preserved for every stage.

That evidence must prove each production handoff in order, with no inferred promotion from partial success.

## Production Acceptance Transaction

Once the variables above are configured, acceptance must prove this exact production sequence:

`question request -> SARA candidate generation -> global semantic novelty rejection/acceptance -> ROAD verification -> question delivery -> answer submission -> grading -> mastery persistence`

The promotion standard is fail-closed. Do not claim `LIVE ACCEPTANCE PASS` merely because the route returns `200 OK`; evidence must show the full chain completed successfully, including ROAD verification and a persisted mastery update.

## Status Boundary

Chat-native operation may continue as a separate acceptance-support mode, but it must preserve the stricter novelty gate above.

Until the live production transaction succeeds with evidence, the correct deployed-runtime status remains `LIVE ACCEPTANCE: BLOCKED_CONFIGURATION`.
