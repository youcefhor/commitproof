# CommitProof Guard

Protect agent tools from redispatch after an ambiguous failure. If a refund
commits and the worker crashes before seeing the reply, the guard blocks a
second dispatch under the same key. Run `python -m unittest -v` to reproduce.

**Did your agent finish the job, or just say it did?**

CommitProof checks a return-processing agent against the contents of a real,
isolated SQLite database. It injects deterministic failures before and after a
write, including a timeout after commit, rejection with an OK transport
response, rollback, duplicate requests, and misrouted writes.

## Reproduce locally

Requires Python 3.10 or newer. No packages, accounts, network, or API keys.

```sh
python commitproof.py --agent optimistic --report optimistic.json
python commitproof.py --agent verified --report verified.json
python -m unittest -v
```

The optimistic baseline exits with code 1 intentionally. Use the verified
baseline for a passing CI example. See the generated JSON reports in
the repository root for the expected orders, observed orders, claims, and tool trace.

## Connect your own agent

Create a trusted Python module with a function accepting
`(store, order_id, request_id)`. It can call `store.request_return` and
`store.read_return` to perform and verify actions. The optional
`store.repair_wrong_order` models a compensating action. Return one of
`completed`, `denied`, or `failed`. Run
`python commitproof.py --agent your_module:your_function`.

Each scenario gets an independent database. The evaluator scores both the
agent's claims and the final order IDs queried directly from storage. The
duplicate scenario sends the same request twice with one idempotency key.
This is a deterministic reference suite with a synthetic store and two
rule-based reference agents. It measures behavior on this suite only. The
adapter executes in-process, so run only trusted adapters. No commercial
agent or external model has been benchmarked in the included reports.

## Publishing

Create a repository named `commitproof`. Upload the contents of this folder
with the README at the root. Include the hidden `.github/workflows` folder
to run the benchmark on pushes and pull requests. Open the resulting
Actions run to see the tests. The included license is MIT.

## Durable dispatch guard

`guard.Journal` is a separate runtime component for tools that mutate external
state. It writes an intent to SQLite before dispatching a tool, records the
result, and replays that result when the caller retries with the same operation
key and arguments. If the process dies between dispatch and recording the
result, the key remains uncertain and retries raise `Uncertain`. Use an
independent provider lookup or a human operator to resolve that state.

```python
from guard import Journal

journal = Journal("operations.sqlite")
result = journal.execute(
    "refund-request-42", "refund", {"amount": 12},
    lambda key, args: {"receipt": key, "amount": args["amount"]},
)
```

Run `python -m unittest -v`. The crash test starts an independent process,
commits a simulated refund to a separate provider database, and terminates
before the result reaches the journal. The restarted worker checks the original
operation key. A separate test overlaps two requests to check that only one
can dispatch.

Use a stable key from the application before calling an agent. This guard is
for trusted workers sharing a durable SQLite file on one host. The application
must supply reconciliation, authentication and storage protection. Requests
that fail before reaching the provider also remain uncertain. The guard cannot
prevent a caller using a different key, a provider executing one request twice,
or changes outside the journal. The benchmark uses simulated providers and
rule-based agents. No external model scores or production claims are included.

See [Stripe's idempotency design](https://stripe.com/blog/idempotency) for
provider-side guarantees and [τ-bench scoring](https://github.com/sierra-research/tau2-bench/blob/main/docs/evaluation.md)
for database-state evaluation of agents.
