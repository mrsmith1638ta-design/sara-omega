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

## Status Boundary

Current deployed-runtime status remains `LIVE ACCEPTANCE BLOCKED_CONFIGURATION` until the Railway service has the required live provider configuration and the full deployed flow passes.

Chat-native operation may continue as a separate acceptance-support mode, but it must preserve the stricter novelty gate above.
