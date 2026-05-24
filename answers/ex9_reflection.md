# Ex9 — Reflection

## Q1 — Planner handoff decision

### Your answer

In my Ex7 run (session sess_2d110a6b1bd9), the planner's second
subgoal was assigned to the structured half. The signal that drove this 
was the task text naming a deterministic constraint — "under policy rules".
Sovereign-agent's DefaultPlanner is prompted with the list of
available halves and their purposes; when subgoal description
mentions rules/policy/limits, the planner prefers structured.

This decision is advisory, not physical. The orchestrator respects
it only because both halves are wired up. The broader lesson: the 
planner makes an architectural decision based on prose interpretation. 
Put the rules somewhere the LLM cannot mis-assign — in the structured 
half's Python — and prose ambiguity no longer matters.

### Citation

- Session sess_2d110a6b1bd9 (Ex7 run)

---

## Q2 — Dataflow integrity catch

### Your answer

During Ex5 development (session sess_0834ce64ddee), my integrity check 
validated that every fact in the flyer came from an actual tool call. 
The verify_dataflow function compared the HTML against _TOOL_CALL_LOG 
and caught when facts were fabricated or didn't match tool outputs.

The fabrication test confirmed this: when I changed "£540" to "£9999", 
verify_dataflow correctly returned FAIL with the unverified fact. This 
proves the integrity check is strict — it won't pass invented numbers 
that aren't in the tool outputs.

The lesson: if the validator would pass a human skim, plant a 
deliberately-weird value like £9999 and confirm it's caught.

### Citation

- Session sess_0834ce64ddee (Ex5 run with integrity check)

---

## Q3 — Removing one framework primitive

### Your answer

Session directories (Decision 1) are the irreplaceable foundation. 
Losing them means: cross-tenant data leaks, reconstructing per-run 
state from logs becomes archaeology, and debugging "how did this session 
end up this way" requires manual trace parsing instead of looking at 
files.

Session directories are like git commits — you can rebuild merge, diff, 
blame from commits but not commits from the rest. The other primitives 
(forward-only state, tickets, atomic IPC) can be rebuilt, but sessions 
are the foundation.

### Citation

- Session sess_0834ce64ddee, sess_2d110a6b1bd9, sess_425aeda2fa15, sess_109eaa9f9276
