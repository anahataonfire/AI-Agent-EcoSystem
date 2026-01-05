"""
QA Runner Utility

Refactored from previous QA Node Agent.
Provides functions to run regression tests from test_suite.yaml.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List
import yaml

# Adjust imports for new location
import sys
# Ensure src is in path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.graph.workflow import run_pipeline


# Paths
DATA_DIR = Path(__file__).parent.parent.parent / "data"
TEST_SUITE_PATH = DATA_DIR / "test_suite.yaml"
REGRESSION_LOG_PATH = DATA_DIR / "regression_log.json"


def load_test_suite() -> List[Dict[str, Any]]:
    """Load all test cases from the YAML file."""
    if not TEST_SUITE_PATH.exists():
        return []
    
    with open(TEST_SUITE_PATH, "r") as f:
        data = yaml.safe_load(f)
    
    return data.get("tests", [])


def load_regression_log() -> List[Dict[str, Any]]:
    """Load existing regression log."""
    if not REGRESSION_LOG_PATH.exists():
        return []
    
    try:
        with open(REGRESSION_LOG_PATH, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return []


def save_regression_log(log: List[Dict[str, Any]]) -> None:
    """Save the regression log."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(REGRESSION_LOG_PATH, "w") as f:
        json.dump(log, f, indent=2, default=str)


def evaluate_test(
    test_case: Dict[str, Any],
    result: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Evaluate a test result against expected values.
    """
    expected = test_case.get("expected", {})
    telemetry = result.get("telemetry", {})
    circuit_breaker = result.get("circuit_breaker", {})
    evidence_map = result.get("evidence_map", {})
    
    # Handle Pydantic objects
    if hasattr(circuit_breaker, "step_count"):
        step_count = circuit_breaker.step_count
    else:
        step_count = circuit_breaker.get("step_count", 0)
    
    checks = []
    failures = []
    
    # Check sanitizer_reject_count_min
    if "sanitizer_reject_count_min" in expected:
        actual = telemetry.get("sanitizer_reject_count", 0)
        check_passed = actual >= expected["sanitizer_reject_count_min"]
        checks.append({
            "name": "sanitizer_reject_count_min",
            "expected": expected["sanitizer_reject_count_min"],
            "actual": actual,
            "passed": check_passed
        })
        if not check_passed:
            failures.append(f"sanitizer_reject_count: {actual} < {expected['sanitizer_reject_count_min']}")
    
    # Check evidence_count_max
    if "evidence_count_max" in expected:
        actual = len(evidence_map)
        check_passed = actual <= expected["evidence_count_max"]
        checks.append({
            "name": "evidence_count_max",
            "expected": expected["evidence_count_max"],
            "actual": actual,
            "passed": check_passed
        })
        if not check_passed:
            failures.append(f"evidence_count: {actual} > {expected['evidence_count_max']}")
    
    # Check evidence_count_min
    if "evidence_count_min" in expected:
        actual = len(evidence_map)
        check_passed = actual >= expected["evidence_count_min"]
        checks.append({
            "name": "evidence_count_min",
            "expected": expected["evidence_count_min"],
            "actual": actual,
            "passed": check_passed
        })
        if not check_passed:
            failures.append(f"evidence_count: {actual} < {expected['evidence_count_min']}")
    
    # Check step_count_min
    if "step_count_min" in expected:
        check_passed = step_count >= expected["step_count_min"]
        checks.append({
            "name": "step_count_min",
            "expected": expected["step_count_min"],
            "actual": step_count,
            "passed": check_passed
        })
        if not check_passed:
            failures.append(f"step_count: {step_count} < {expected['step_count_min']}")
    
    # Check should_complete (always pass if we got here without exception)
    if "should_complete" in expected:
        checks.append({
            "name": "should_complete",
            "expected": expected["should_complete"],
            "actual": True,
            "passed": True
        })
    
    return {
        "passed": len(failures) == 0,
        "checks": checks,
        "failures": failures
    }


def run_test(test_id: str) -> Dict[str, Any]:
    """Run a specific test by ID."""
    tests = load_test_suite()
    test_case = next((t for t in tests if t["test_id"] == test_id), None)
    
    if not test_case:
        return {
            "test_id": test_id,
            "status": "ERROR",
            "error": f"Test case '{test_id}' not found"
        }
    
    query = test_case.get("query", "")
    
    try:
        result = run_pipeline(query)
        evaluation = evaluate_test(test_case, result)
        
        # Build result record
        record = {
            "timestamp": datetime.now().isoformat(),
            "test_id": test_id,
            "query": query,
            "telemetry": result.get("telemetry", {}),
            "evidence_count": len(result.get("evidence_map", {})),
            "step_count": result.get("circuit_breaker", {}).step_count if hasattr(result.get("circuit_breaker", {}), "step_count") else result.get("circuit_breaker", {}).get("step_count", 0),
            "evaluation": evaluation,
            "status": "PASS" if evaluation["passed"] else "FAIL"
        }
        
        # Log result
        log = load_regression_log()
        log.append(record)
        save_regression_log(log)
        
        return record
        
    except Exception as e:
        record = {
            "timestamp": datetime.now().isoformat(),
            "test_id": test_id,
            "query": query,
            "status": "ERROR",
            "error": str(e)
        }
        
        # Log even errors
        log = load_regression_log()
        log.append(record)
        save_regression_log(log)
        
        return record


def run_all_tests() -> Dict[str, Any]:
    """Run all tests in the test suite."""
    tests = load_test_suite()
    results = []
    
    for test_case in tests:
        test_id = test_case.get("test_id", "UNKNOWN")
        result = run_test(test_id)
        results.append(result)
    
    # Summary
    passed = sum(1 for r in results if r.get("status") == "PASS")
    failed = sum(1 for r in results if r.get("status") == "FAIL")
    errors = sum(1 for r in results if r.get("status") == "ERROR")
    
    return {
        "timestamp": datetime.now().isoformat(),
        "total": len(results),
        "passed": passed,
        "failed": failed,
        "errors": errors,
        "results": results
    }


if __name__ == "__main__":
    # CLI entrypoint for testing
    print("Running QA Regression Suite...")
    summary = run_all_tests()
    
    print(f"\n=== REGRESSION SUMMARY ===")
    print(f"Total: {summary['total']}")
    print(f"Passed: {summary['passed']}")
    print(f"Failed: {summary['failed']}")
    print(f"Errors: {summary['errors']}")
    
    for result in summary["results"]:
        status_icon = "✓" if result["status"] == "PASS" else "✗" if result["status"] == "FAIL" else "⚠"
        print(f"\n{status_icon} {result['test_id']}: {result['status']}")
        if result.get("error"):
            print(f"   Error: {result['error']}")
        if result.get("evaluation", {}).get("failures"):
            for f in result["evaluation"]["failures"]:
                print(f"   - {f}")
