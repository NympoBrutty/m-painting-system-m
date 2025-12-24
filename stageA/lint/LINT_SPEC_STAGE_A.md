# LINT_SPEC_STAGE_A.md — Lint Specification v2.0

## Overview

This document defines all lint rules for Stage A contracts.
The lint validator (`contract_lint_validator.py`) implements these rules.

## Severity Levels

| Level | Code Prefix | Meaning |
|-------|-------------|---------|
| ERROR | E### | Contract is invalid, must fix |
| WARNING | W### | Contract works but has issues |

## Error Codes Registry

### Structure Errors (E01x)

| Code | Rule | Description |
|------|------|-------------|
| E010 | required_fields | Missing required top-level field |
| E011 | schema_block | Invalid `_schema` block |
| E012 | timestamp_format | Invalid ISO8601 timestamp |
| E013 | module_identity | Invalid module_id, module_abbr, or module_type |
| E014 | module_name_i18n | Missing uk/en in module_name |
| E015 | io_contract | Invalid io_contract structure |
| E016 | policies | Invalid policies configuration |
| E017 | relations | Invalid relations structure |

### Parameter Errors (E02x)

| Code | Rule | Description |
|------|------|-------------|
| E020 | parameters_structure | Parameters must be non-empty object with required fields |
| E021 | parameter_type | Invalid parameter type or missing enum for enum type |

### Constraint Errors (E03x)

| Code | Rule | Description |
|------|------|-------------|
| E030 | constraints_structure | Constraints must have `expr` and `error_code` |
| E031 | constraint_code_undefined | Constraint references undefined error code |

### Validation Rules Errors (E04x)

| Code | Rule | Description |
|------|------|-------------|
| E040 | validation_structure | Validation rules must have required fields |
| E041 | validation_code_undefined | Validation rule references undefined code |

### Error Codes Errors (E05x)

| Code | Rule | Description |
|------|------|-------------|
| E050 | error_codes_structure | Error codes must have code, level, title, message |
| E051 | error_code_duplicate | Duplicate error code |

### Algorithm Errors (E06x)

| Code | Rule | Description |
|------|------|-------------|
| E060 | algorithm_structure | Algorithm must have artifact_registry and steps |
| E061 | data_flow_uses | Step uses undefined artifact |
| E062 | data_flow_outputs | Output not produced by any step |
| E063 | step_structure | Step missing required fields |

### Artifact Errors (E07x)

| Code | Rule | Description |
|------|------|-------------|
| E070 | artifact_registry | Output not in artifact_registry |
| E071 | output_scope | Output artifacts must have scope: public |

### Test Cases Errors (E08x)

| Code | Rule | Description |
|------|------|-------------|
| E080 | test_cases_structure | Test cases must have required fields and types |

### Glossary Errors (E10x)

| Code | Rule | Description |
|------|------|-------------|
| E100 | glossary_strict | Term not in glossary (strict mode) |

### Warnings (W###)

| Code | Rule | Description |
|------|------|-------------|
| W020 | parameter_not_grouped | Parameter not in any parameter_group |
| W081 | no_warning_test | No warning-type test case |
| W101 | glossary_warn | Term not in glossary (warn mode) |

## Required Fields

### Top-Level (all required)

```
_schema, module_id, module_abbr, module_type, module_name,
version, description, io_contract, parameters, parameter_groups,
constraints, validation, error_codes, algorithm, relations,
test_cases, policies
```

### _schema (all required)

```
name, version, stage, maturity_stage, static_frame_only,
underpainting_intent, created_at, updated_at
```

### Parameter Definition (required)

```
type, unit, description
```

### Constraint Definition (required)

```
expr, error_code
```

### Validation Rule (required)

```
name, condition, severity, message, error_code
```

### Error Code Definition (required)

```
code, level, title, message
```

### Algorithm Step (required)

```
id, name, type, uses, produces, description
```

### Test Case (required)

```
id, type, name, input, expected
```

## Format Patterns

| Field | Pattern | Example |
|-------|---------|---------|
| module_id | `A-<ROMAN>-<N>` | A-I-3, A-III-2.1 |
| module_abbr | `[A-Z0-9]{2,8}` | SPS, NSS, LINE |
| version | `<M>.<m>.<p>` (SemVer) | 1.0.0, 2.1.3 |
| timestamp | ISO8601 +02:00 | 2025-12-24T22:00:00+02:00 |
| error_code | `E###` | E001, E042 |
| warning_code | `W###` | W001, W003 |
| step_id | `S###` | S001, S010 |

## Enum Values

### module_type
```
PROCESS, RULESET, BRIDGE
```

### maturity_stage
```
pilot, draft, stable
```

### underpainting_intent
```
structure_only, structure_plus_masks, structure_plus_metadata
```

### parameter.type
```
float, int, boolean, enum, string
```

### step.type
```
load, transform, filter, validate, normalize, classify, export, validate_module
```

### test_case.type
```
positive, negative, warning
```

## Constraints DSL

Format: `string_expr` (DSL version 1.0)

```json
{
  "expr": "shot_type == 'ECU' => framing_tightness >= 0.85",
  "error_code": "E001"
}
```

Operators:
- Comparison: `==`, `!=`, `>`, `>=`, `<`, `<=`
- Logical: `&&`, `||`, `!`
- Implication: `=>`
- Grouping: `()`

## Test Cases Requirements

- Minimum 3 test cases
- At least 1 `positive` type
- At least 1 `negative` type
- Recommended: at least 1 `warning` type

## Glossary Policy

| Policy | Behavior |
|--------|----------|
| strict | Missing terms cause E100 errors |
| warn | Missing terms cause W101 warnings |
| off | Glossary not checked |

## Score Calculation

```
Base score: 100
Each ERROR: -10 points (min 0 if errors exist → max 50)
Each WARNING: -5 points (if no errors → 70-100)
```

| Score | Status |
|-------|--------|
| 100 | Perfect |
| 90-99 | Excellent |
| 70-89 | Good (warnings only) |
| 50-69 | Needs work |
| 0-49 | Failed |
