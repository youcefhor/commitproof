# CommitProof

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
`examples/` for the expected orders, observed orders, claims, and tool trace.

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
