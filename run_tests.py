#!/usr/bin/env python3
import os
import sys
import time
import json
import argparse
import subprocess
from pathlib import Path
from datetime import datetime

def run_tests(args):
    """Run test suite with specified options"""
    start_time = time.time()
    
    # Prepare test command
    cmd = ["pytest"]
    
    if args.unit:
        cmd.extend(["tests/unit"])
    if args.integration:
        cmd.extend(["tests/integration"])
    if args.load:
        cmd.extend(["tests/load"])
    if args.hardware:
        cmd.extend(["tests/hardware"])
    if args.performance:
        cmd.extend(["tests/performance"])
    
    if not any([args.unit, args.integration, args.load, args.hardware, args.performance]):
        cmd.extend(["tests/"])  # Run all tests if none specified
    
    # Add coverage options
    if args.coverage:
        cmd.extend([
            "--cov=.",
            "--cov-report=term-missing",
            f"--cov-report=html:{args.report_dir}/coverage"
        ])
    
    # Add benchmark options
    if args.benchmark:
        cmd.extend([
            "--benchmark-only",
            "--benchmark-autosave",
            f"--benchmark-storage={args.report_dir}/benchmarks"
        ])
    
    # Run tests
    print(f"\nRunning tests: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    # Save test output
    output_file = Path(args.report_dir) / "test_output.txt"
    with open(output_file, "w") as f:
        f.write(result.stdout)
        if result.stderr:
            f.write("\n\nErrors:\n")
            f.write(result.stderr)
    
    # Generate test summary
    elapsed = time.time() - start_time
    summary = {
        "timestamp": datetime.now().isoformat(),
        "duration": elapsed,
        "exit_code": result.returncode,
        "command": " ".join(cmd),
        "test_types": {
            "unit": args.unit,
            "integration": args.integration,
            "load": args.load,
            "hardware": args.hardware,
            "performance": args.performance
        }
    }
    
    # Save summary
    summary_file = Path(args.report_dir) / "test_summary.json"
    with open(summary_file, "w") as f:
        json.dump(summary, f, indent=2)
    
    # Print summary
    print("\nTest Summary:")
    print("-" * 40)
    print(f"Duration: {elapsed:.2f} seconds")
    print(f"Exit Code: {result.returncode}")
    print(f"Report Directory: {args.report_dir}")
    
    return result.returncode

def setup_reports_dir(base_dir: str) -> str:
    """Setup reports directory with timestamp"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_dir = Path(base_dir) / timestamp
    
    # Create directories
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "coverage").mkdir(exist_ok=True)
    (report_dir / "benchmarks").mkdir(exist_ok=True)
    
    return str(report_dir)

def main():
    parser = argparse.ArgumentParser(description="Run test suite and generate reports")
    
    # Test selection
    parser.add_argument("--unit", action="store_true", help="Run unit tests")
    parser.add_argument("--integration", action="store_true", help="Run integration tests")
    parser.add_argument("--load", action="store_true", help="Run load tests")
    parser.add_argument("--hardware", action="store_true", help="Run hardware simulation tests")
    parser.add_argument("--performance", action="store_true", help="Run performance tests")
    
    # Test options
    parser.add_argument("--coverage", action="store_true", help="Generate coverage reports")
    parser.add_argument("--benchmark", action="store_true", help="Run benchmarks")
    parser.add_argument("--report-dir", type=str, default="test_reports",
                      help="Base directory for test reports")
    
    args = parser.parse_args()
    
    # Setup report directory
    args.report_dir = setup_reports_dir(args.report_dir)
    
    # Run tests
    exit_code = run_tests(args)
    
    sys.exit(exit_code)

if __name__ == "__main__":
    main() 