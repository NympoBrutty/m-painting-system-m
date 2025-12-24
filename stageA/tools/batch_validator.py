#!/usr/bin/env python3
"""
batch_validator.py v2.0 — Batch validation for Stage A contracts

Features:
- Validates all Stage A contracts in a directory
- Generates per-file reports and summary
- Supports CI/CD integration with proper exit codes
- Parallel validation support (optional)

Usage:
  python stageA/tools/batch_validator.py stageA/contracts \
      --glossary stageA/glossary/glossary_v1.json \
      --schema stageA/schema/contract_schema_stageA_v4.json \
      --out stageA/_reports

Exit codes:
  0 = all passed
  1 = some contracts failed
  2 = fatal error (bad arguments, missing files)
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional


def _load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _save_json(path: Path, data: Dict[str, Any]) -> None:
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8"
    )


def _is_contract_file(p: Path) -> bool:
    """Check if file is a Stage A contract."""
    name = p.name
    # Skip service files
    if name.startswith(("katalog_", "glossary_", "contract_schema_")):
        return False
    if name.endswith(("_lint.json", "_report.json", "summary.json")):
        return False
    # Match contract patterns
    return "_contract_stageA" in name or name.endswith("_contract.json")


def _find_contracts(root: Path, exclude_dir: Optional[Path] = None) -> List[Path]:
    """Find all contract files in directory."""
    contracts = []
    for p in sorted(root.rglob("*.json")):
        if exclude_dir:
            try:
                p.relative_to(exclude_dir)
                continue  # Skip files in output directory
            except ValueError:
                pass
        if _is_contract_file(p):
            contracts.append(p)
    return contracts


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Batch validate Stage A contracts"
    )
    parser.add_argument(
        "contracts_root",
        type=str,
        help="Root directory containing contracts"
    )
    parser.add_argument(
        "--schema",
        type=str,
        default=None,
        help="Path to JSON Schema (auto-detected if not provided)"
    )
    parser.add_argument(
        "--glossary",
        type=str,
        default=None,
        help="Path to glossary JSON (optional)"
    )
    parser.add_argument(
        "--out",
        type=str,
        default="stageA/_reports",
        help="Output directory for reports"
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail on any error (for CI)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output"
    )
    
    args = parser.parse_args()
    
    # Resolve paths
    contracts_root = Path(args.contracts_root).resolve()
    out_dir = Path(args.out).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    
    if not contracts_root.exists() or not contracts_root.is_dir():
        print(f"[FATAL] Contracts root not found: {contracts_root}", file=sys.stderr)
        return 2
    
    # Find schema
    if args.schema:
        schema_path = Path(args.schema).resolve()
    else:
        # Auto-detect: look in stageA/schema/
        repo_root = Path(__file__).resolve().parents[2]
        schema_path = repo_root / "stageA" / "schema" / "contract_schema_stageA_v4.json"
    
    if not schema_path.exists():
        print(f"[FATAL] Schema not found: {schema_path}", file=sys.stderr)
        return 2
    
    # Find glossary
    glossary_path: Optional[Path] = None
    if args.glossary:
        gp = Path(args.glossary).resolve()
        if gp.exists():
            glossary_path = gp
        else:
            print(f"[WARN] Glossary not found: {gp}", file=sys.stderr)
    
    # Import validator
    try:
        # Try relative import first
        lint_dir = Path(__file__).resolve().parents[1] / "lint"
        sys.path.insert(0, str(lint_dir))
        from contract_lint_validator import ContractLintValidator
    except ImportError:
        try:
            # Fallback: try from repo root
            repo_root = Path(__file__).resolve().parents[2]
            sys.path.insert(0, str(repo_root))
            from stageA.lint.contract_lint_validator import ContractLintValidator
        except ImportError as e:
            print(f"[FATAL] Could not import validator: {e}", file=sys.stderr)
            return 2
    
    # Initialize validator
    validator = ContractLintValidator(
        schema_path=schema_path,
        glossary_path=glossary_path,
        strict_mode=args.strict
    )
    
    # Find contracts
    contracts = _find_contracts(contracts_root, exclude_dir=out_dir)
    
    if not contracts:
        print(f"[WARN] No contracts found in: {contracts_root}", file=sys.stderr)
        summary = {
            "timestamp": datetime.now().isoformat(),
            "contracts_root": str(contracts_root),
            "total": 0,
            "passed": 0,
            "failed": 0,
            "results": []
        }
        _save_json(out_dir / "summary.json", summary)
        return 0
    
    # Validate each contract
    results: List[Dict[str, Any]] = []
    passed_count = 0
    failed_count = 0
    failed_files: List[str] = []
    
    print(f"\n{'='*60}")
    print(f"Stage A Contract Validation")
    print(f"{'='*60}")
    print(f"Schema: {schema_path.name}")
    print(f"Glossary: {glossary_path.name if glossary_path else 'N/A'}")
    print(f"Contracts: {len(contracts)}")
    print(f"{'='*60}\n")
    
    for contract_path in contracts:
        try:
            result = validator.validate_contract(contract_path)
            result_dict = result.to_dict()
            results.append(result_dict)
            
            # Save per-file report
            report_name = f"{contract_path.stem}_lint.json"
            _save_json(out_dir / report_name, result_dict)
            
            if result.passed:
                passed_count += 1
                status = "✓ PASS"
                score_str = f"[{result.score}/100]"
            else:
                failed_count += 1
                failed_files.append(str(contract_path))
                status = "✗ FAIL"
                score_str = f"[{result.score}/100]"
            
            # Print result
            warnings_str = f" ({len(result.warnings)} warnings)" if result.warnings else ""
            print(f"{status} {score_str} {contract_path.name}{warnings_str}")
            
            if args.verbose and not result.passed:
                for err in result.errors[:5]:  # Show first 5 errors
                    print(f"      {err.code}: {err.message}")
                if len(result.errors) > 5:
                    print(f"      ... and {len(result.errors) - 5} more errors")
        
        except Exception as e:
            failed_count += 1
            failed_files.append(str(contract_path))
            print(f"✗ FAIL [ERR] {contract_path.name}: {e}", file=sys.stderr)
            results.append({
                "file_path": str(contract_path),
                "passed": False,
                "score": 0,
                "errors": [{"code": "FATAL", "message": str(e)}],
                "warnings": []
            })
    
    # Print summary
    print(f"\n{'='*60}")
    print(f"Summary: {passed_count}/{len(contracts)} passed")
    if failed_count > 0:
        print(f"Failed contracts:")
        for f in failed_files:
            print(f"  - {Path(f).name}")
    print(f"{'='*60}\n")
    
    # Save summary
    summary = {
        "timestamp": datetime.now().isoformat(),
        "contracts_root": str(contracts_root),
        "schema": str(schema_path),
        "glossary": str(glossary_path) if glossary_path else None,
        "total": len(contracts),
        "passed": passed_count,
        "failed": failed_count,
        "pass_rate": f"{(passed_count/len(contracts)*100):.1f}%",
        "failed_files": failed_files,
        "results": results
    }
    _save_json(out_dir / "summary.json", summary)
    
    print(f"Reports saved to: {out_dir}")
    
    return 0 if failed_count == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
