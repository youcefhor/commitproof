# CommitProof

**Check an agent's completion claim against what actually committed.**

[العربية](README.ar.md) · [Walkthrough video](https://github.com/youcefhor/youcefhor/blob/main/assets/commitproof-demo.mp4) · [Guard implementation](guard.py) · [Example report](verified.json)

![CommitProof reference results](https://raw.githubusercontent.com/youcefhor/youcefhor/main/assets/commitproof-cover.png)

## The failure this reproduces

A tool can write the right record and still time out before its caller sees the response. A blind retry may send the operation twice. A successful HTTP response can also hide a rejected operation or a write to the wrong record.

CommitProof runs those cases against isolated SQLite databases. It checks the final record IDs as well as the agent's completion status. The separate dispatch guard records intent before calling a write tool and stops redispatch when the outcome is uncertain.

## See it run

![Replay of actual command output](https://raw.githubusercontent.com/youcefhor/youcefhor/main/assets/commitproof-demo.gif)

[Watch or download the MP4 walkthrough](https://github.com/youcefhor/youcefhor/blob/main/assets/commitproof-demo.mp4)

The visual replays output from a local run of this repository on 5 November 2026. The included optimistic baseline passed **3/8** scenarios. The verified baseline passed **8/8**. Six unit tests passed. These results cover the supplied deterministic store and reference agents.

## Try it

Requires Python 3.10 or newer and the standard library.

```sh
git clone https://github.com/youcefhor/commitproof.git
cd commitproof
python commitproof.py --agent optimistic --report optimistic.json
python commitproof.py --agent verified --report verified.json
python -m unittest -v
```

The optimistic baseline intentionally exits with code 1 when a false completion is detected.

## Repository map

| File | Role |
| --- | --- |
| [commitproof.py](commitproof.py) | Store, failure scenarios, evaluator and CLI |
| [guard.py](guard.py) | Durable dispatch journal and uncertain-outcome guard |
| [test_commitproof.py](test_commitproof.py) | Completion-claim regression tests |
| [test_guard.py](test_guard.py) | Crash recovery, concurrency and replay tests |
| [optimistic.json](optimistic.json) / [verified.json](verified.json) | Reproducible reference reports |

## Implementation and integration notes

<details>
<summary>Adapters, dispatch guard and operating assumptions</summary>

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


</details>

