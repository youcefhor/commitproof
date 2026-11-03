"""Evaluate an agent's completion claim against an isolated SQLite store."""
import argparse
from dataclasses import dataclass
import importlib
import json
from pathlib import Path
import sqlite3


@dataclass(frozen=True)
class Case:
    name: str
    fault: str = ""
    allowed: bool = True
    repeat: bool = False
    expected: tuple = ("A-100",)


CASES = (
    Case("normal"),
    Case("network failure before commit", "before"),
    Case("response lost after commit", "after"),
    Case("HTTP 200 with rejected operation", "rejected", expected=()),
    Case("outside return window", allowed=False, expected=()),
    Case("duplicate user request", repeat=True),
    Case("wrong order acknowledged", "wrong"),
    Case("database transaction rolled back", "rollback"),
)


class Store:
    def __init__(self, connection, case):
        self.connection = connection
        self.case = case
        self.pending_fault = case.fault
        self.trace = []
        connection.execute("CREATE TABLE returns (request TEXT UNIQUE, order_id TEXT)")
        connection.commit()

    def request_return(self, order, request):
        fault, self.pending_fault = self.pending_fault, ""
        self.trace.append({"call": "request_return", "order": order,
                           "request": request, "fault": fault or None})
        if not self.case.allowed or fault == "rejected":
            return {"ok": False, "reason": "return denied"}
        if fault == "before":
            raise TimeoutError("request never reached storage")
        with self.connection:
            self.connection.execute(
                "INSERT OR IGNORE INTO returns VALUES (?, ?)",
                (request, "B-999" if fault == "wrong" else order),
            )
            if fault == "rollback":
                raise TimeoutError("transaction rolled back")
        if fault == "after":
            raise TimeoutError("response lost after commit")
        return {"ok": True}

    def read_return(self, request):
        self.trace.append({"call": "read_return", "request": request})
        result = self.connection.execute(
            "SELECT order_id FROM returns WHERE request = ?", (request,)
        ).fetchone()
        return result[0] if result else None

    def repair_wrong_order(self, request, expected_order):
        """Compensate only the misrouted write attached to this request."""
        self.trace.append({"call": "repair_wrong_order", "request": request})
        with self.connection:
            self.connection.execute(
                "DELETE FROM returns WHERE request = ? AND order_id != ?",
                (request, expected_order),
            )


def optimistic(store, order, request):
    try:
        store.request_return(order, request)
    except TimeoutError:
        pass
    return "completed"


def verified(store, order, request):
    for _ in range(2):
        existing = store.read_return(request)
        if existing == order:
            return "completed"
        if existing is not None:
            store.repair_wrong_order(request, order)
        try:
            response = store.request_return(order, request)
        except TimeoutError:
            continue
        if not response["ok"]:
            return "denied"
    return "completed" if store.read_return(request) == order else "failed"


def evaluate(agent):
    results = []
    for case in CASES:
        connection = sqlite3.connect(":memory:")
        try:
            store = Store(connection, case)
            claims = []
            for _ in range(2 if case.repeat else 1):
                claims.append(agent(store, "A-100", "request-001"))
            observed = tuple(order for (order,) in connection.execute(
                "SELECT order_id FROM returns ORDER BY order_id"
            ))
            expected_claim = "completed" if case.expected else "denied"
            results.append({
                "case": case.name,
                "passed": observed == case.expected and all(
                    claim == expected_claim for claim in claims
                ),
                "claims": claims,
                "expected_orders": list(case.expected),
                "observed_orders": list(observed),
                "trace": store.trace,
            })
        finally:
            connection.close()
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agent", default="verified",
                        help="verified, optimistic, or trusted Python module:function")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    agents = {"verified": verified, "optimistic": optimistic}
    agent = agents.get(args.agent)
    if agent is None:
        module, separator, name = args.agent.partition(":")
        if not separator:
            parser.error("Use module:function for custom agents")
        agent = getattr(importlib.import_module(module), name)
    results = evaluate(agent)
    report = {"agent": args.agent, "passed": sum(r["passed"] for r in results),
              "total": len(results), "cases": results}
    if args.report:
        args.report.write_text(json.dumps(report, indent=2) + "\n")
    for result in results:
        label = "PASS" if result["passed"] else "FAIL"
        print(f"{label}  {result['case']}: {result['claims']} -> {result['observed_orders']}")
    print(f"{report['passed']}/{report['total']} passed")
    return 0 if report["passed"] == report["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
