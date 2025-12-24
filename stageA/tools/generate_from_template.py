#!/usr/bin/env python3
"""
generate_from_template.py v2.0 — Generate valid Stage A contracts

Creates a new contract that passes JSON Schema v4 validation:
- All required fields populated
- Proper structure for constraints (expr string format)
- Valid error_codes and test_cases
- Correct policies configuration

Usage:
  python stageA/tools/generate_from_template.py \
      --module-id A-V-1 \
      --module-abbr TONE \
      --module-type PROCESS \
      --module-name-uk "ТОНАЛЬНА КАРТА" \
      --module-name-en "TONE MAP" \
      --out stageA/contracts/A-V-1_TONE_contract_stageA_FINAL.json
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict


# Validation patterns
MODULE_ID_RE = re.compile(r"^A-(?:[IVXLCDM]+)-\d+(?:\.\d+)?$")
ABBR_RE = re.compile(r"^[A-Z0-9]{2,8}$")


def _now_iso(tz_offset: str = "+02:00") -> str:
    """Generate ISO8601 timestamp with timezone."""
    m = re.match(r"^([+-])(\d{2}):(\d{2})$", tz_offset)
    if not m:
        raise ValueError(f"Invalid timezone: {tz_offset}")
    
    sign, hh, mm = m.group(1), int(m.group(2)), int(m.group(3))
    delta = timedelta(hours=hh, minutes=mm)
    if sign == "-":
        delta = -delta
    
    tz = timezone(delta)
    return datetime.now(tz=tz).strftime("%Y-%m-%dT%H:%M:%S") + tz_offset


def _validate_inputs(module_id: str, module_abbr: str, module_type: str) -> None:
    """Validate input arguments."""
    if not MODULE_ID_RE.match(module_id):
        raise ValueError(f"Invalid module_id: {module_id} (expected A-<ROMAN>-<N>)")
    if not ABBR_RE.match(module_abbr):
        raise ValueError(f"Invalid module_abbr: {module_abbr} (expected 2-8 uppercase)")
    if module_type not in {"PROCESS", "RULESET", "BRIDGE"}:
        raise ValueError(f"Invalid module_type: {module_type}")


def build_contract(
    *,
    module_id: str,
    module_abbr: str,
    module_type: str,
    module_name_uk: str,
    module_name_en: str,
    tz: str = "+02:00",
    version: str = "1.0.0",
    schema_version: str = "4.0.0",
) -> Dict[str, Any]:
    """Build a valid Stage A contract from template."""
    
    timestamp = _now_iso(tz)
    
    # Determine underpainting_intent based on module_type
    underpainting_intent = {
        "PROCESS": "structure_plus_masks",
        "RULESET": "structure_plus_masks",
        "BRIDGE": "structure_only"
    }.get(module_type, "structure_only")
    
    contract: Dict[str, Any] = {
        "_schema": {
            "name": "A-PRACTICAL.contract",
            "version": schema_version,
            "stage": "A.contract_only",
            "maturity_stage": "draft",
            "static_frame_only": True,
            "underpainting_intent": underpainting_intent,
            "created_at": timestamp,
            "updated_at": timestamp
        },
        
        "module_id": module_id,
        "module_abbr": module_abbr,
        "module_type": module_type,
        "module_name": {
            "uk": module_name_uk,
            "en": module_name_en
        },
        "version": version,
        
        "description": f"Модуль {module_id} ({module_abbr}) — TODO: додати детальний опис призначення та функціоналу модуля.",
        
        "io_contract": {
            "inputs": [
                {
                    "artifact_id": "input_data",
                    "type": "json",
                    "scope": "public",
                    "description": "TODO: Вхідні дані модуля"
                }
            ],
            "outputs": [
                {
                    "artifact_id": "output_result",
                    "type": "json",
                    "scope": "public",
                    "description": "TODO: Вихідні дані модуля"
                }
            ]
        },
        
        "parameters": {
            "strength": {
                "type": "float",
                "unit": "fraction",
                "range": [0.0, 1.0],
                "default": 0.5,
                "description": "TODO: Основний параметр впливу модуля (0.0–1.0)."
            },
            "mode": {
                "type": "enum",
                "enum": ["auto", "manual"],
                "default": "auto",
                "unit": "category",
                "description": "TODO: Режим роботи модуля."
            },
            "enabled": {
                "type": "boolean",
                "unit": "flag",
                "default": True,
                "description": "TODO: Прапорець активації модуля."
            }
        },
        
        "parameter_groups": {
            "main": ["strength", "mode"],
            "control": ["enabled"]
        },
        
        "constraints": [
            {
                "expr": "strength >= 0.0 && strength <= 1.0",
                "error_code": "E001"
            },
            {
                "expr": "mode == 'auto' || mode == 'manual'",
                "error_code": "E002"
            }
        ],
        
        "validation": {
            "rules": [
                {
                    "name": "low_strength_warning",
                    "condition": "strength < 0.1",
                    "severity": "warning",
                    "message": "strength < 0.1 може не дати помітного ефекту.",
                    "error_code": "W001"
                },
                {
                    "name": "high_strength_warning",
                    "condition": "strength > 0.9",
                    "severity": "warning",
                    "message": "strength > 0.9 може призвести до надмірного ефекту.",
                    "error_code": "W002"
                }
            ]
        },
        
        "error_codes": [
            {
                "code": "E001",
                "level": "error",
                "title": {"uk": "Strength поза діапазоном", "en": "Strength out of range"},
                "message": {"uk": "strength має бути в межах [0.0, 1.0].", "en": "strength must be within [0.0, 1.0]."}
            },
            {
                "code": "E002",
                "level": "error",
                "title": {"uk": "Невідомий режим", "en": "Unknown mode"},
                "message": {"uk": "mode має бути 'auto' або 'manual'.", "en": "mode must be 'auto' or 'manual'."}
            },
            {
                "code": "W001",
                "level": "warning",
                "title": {"uk": "Низький strength", "en": "Low strength"},
                "message": {"uk": "strength < 0.1 може не дати ефекту.", "en": "strength < 0.1 may have no visible effect."}
            },
            {
                "code": "W002",
                "level": "warning",
                "title": {"uk": "Високий strength", "en": "High strength"},
                "message": {"uk": "strength > 0.9 може бути надмірним.", "en": "strength > 0.9 may be excessive."}
            }
        ],
        
        "algorithm": {
            "artifact_registry": [
                {"artifact_id": "output_result", "scope": "public"},
                {"artifact_id": "intermediate_data", "scope": "private"}
            ],
            "steps": [
                {
                    "id": "S001",
                    "name": "load_input",
                    "type": "load",
                    "uses": ["input_data"],
                    "produces": ["loaded_data"],
                    "description": "TODO: Завантаження вхідних даних."
                },
                {
                    "id": "S002",
                    "name": "process",
                    "type": "transform",
                    "uses": ["loaded_data", "strength", "mode"],
                    "produces": ["intermediate_data"],
                    "description": "TODO: Основна обробка даних."
                },
                {
                    "id": "S003",
                    "name": "validate",
                    "type": "validate",
                    "uses": ["intermediate_data"],
                    "produces": ["validation_report"],
                    "description": "TODO: Валідація результатів."
                },
                {
                    "id": "S004",
                    "name": "export",
                    "type": "export",
                    "uses": ["intermediate_data", "validation_report"],
                    "produces": ["output_result"],
                    "description": "TODO: Експорт результатів."
                }
            ]
        },
        
        "relations": {
            "depends_on": [],
            "influences": [],
            "conflicts_with": []
        },
        
        "test_cases": [
            {
                "id": f"TC_{module_abbr}_POS_01",
                "type": "positive",
                "name": "Valid default configuration",
                "input": {
                    "strength": 0.5,
                    "mode": "auto",
                    "enabled": True
                },
                "expected": {"pass": True}
            },
            {
                "id": f"TC_{module_abbr}_POS_02",
                "type": "positive",
                "name": "Valid manual mode",
                "input": {
                    "strength": 0.8,
                    "mode": "manual"
                },
                "expected": {"pass": True}
            },
            {
                "id": f"TC_{module_abbr}_NEG_01",
                "type": "negative",
                "name": "Strength below range",
                "input": {
                    "strength": -0.5
                },
                "expected": {"pass": False, "error_code": "E001"}
            },
            {
                "id": f"TC_{module_abbr}_NEG_02",
                "type": "negative",
                "name": "Strength above range",
                "input": {
                    "strength": 1.5
                },
                "expected": {"pass": False, "error_code": "E001"}
            },
            {
                "id": f"TC_{module_abbr}_WARN_01",
                "type": "warning",
                "name": "Low strength warning",
                "input": {
                    "strength": 0.05,
                    "mode": "auto"
                },
                "expected": {"pass": True, "warning_code": "W001"}
            }
        ],
        
        "policies": {
            "unit_policy": "strict",
            "constraints_dsl": {
                "dsl_version": "1.0",
                "syntax": "string_expr"
            },
            "glossary_policy": "warn",
            "i18n_policy": {
                "default_lang": "uk",
                "supported_langs": ["uk", "en"]
            }
        }
    }
    
    return contract


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate a valid Stage A contract from template"
    )
    parser.add_argument("--module-id", required=True, help="Module ID (e.g., A-V-1)")
    parser.add_argument("--module-abbr", required=True, help="Module abbreviation (e.g., TONE)")
    parser.add_argument("--module-type", required=True, choices=["PROCESS", "RULESET", "BRIDGE"])
    parser.add_argument("--module-name-uk", required=True, help="Module name in Ukrainian")
    parser.add_argument("--module-name-en", required=True, help="Module name in English")
    parser.add_argument("--out", required=True, help="Output file path")
    parser.add_argument("--version", default="1.0.0", help="Contract version")
    parser.add_argument("--tz", default="+02:00", help="Timezone offset")
    
    args = parser.parse_args()
    
    try:
        _validate_inputs(args.module_id, args.module_abbr, args.module_type)
    except ValueError as e:
        print(f"[ERROR] {e}")
        return 2
    
    contract = build_contract(
        module_id=args.module_id,
        module_abbr=args.module_abbr,
        module_type=args.module_type,
        module_name_uk=args.module_name_uk,
        module_name_en=args.module_name_en,
        version=args.version,
        tz=args.tz
    )
    
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(contract, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8"
    )
    
    print(f"[OK] Generated contract: {out_path}")
    print(f"     Module: {args.module_id} ({args.module_abbr})")
    print(f"     Type: {args.module_type}")
    print(f"\n     NOTE: Search for 'TODO' to complete the contract.")
    
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
