"""stageB.generator.generate_module

Stage B — Skeleton Code Generation (Variant A: autogen)

Reads Stage A contracts and generates module skeletons under:
    stageB/modules/<ABBR>/

Rules (strict):
  - Generator ONLY writes files matching *_autogen.py or *_autogen.md
  - It never writes/overwrites manual files (pipeline.py / __manual__.py / __init__.py)
  - Writes are atomic: temp-file + os.replace
  - Autogen header carries traceability: contract_id/version/schema_version + sha256
  - Runtime traceability constants are included (for Stage C/D verification)
  - Output is deterministic (idempotent) for the same input contracts

CLI:
  python -m stageB.generator.generate_module --all
  python -m stageB.generator.generate_module --module SPS
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass
from keyword import iskeyword
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

GENERATOR_VERSION = "1.3.0"

REPO_ROOT = Path(__file__).resolve().parents[2]
STAGEA_CONTRACTS_DIR = REPO_ROOT / "stageA" / "contracts"
STAGEB_MODULES_DIR = REPO_ROOT / "stageB" / "modules"


# -------------------------
# Utilities
# -------------------------

def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _atomic_write_text(path: Path, content: str) -> None:
    """Write file atomically (temp + rename).

    Uses a PID-suffixed temp file to reduce collision risk.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    pid = os.getpid()
    tmp = path.with_suffix(path.suffix + f".tmp.{pid}")
    tmp.write_text(content, encoding="utf-8")
    os.replace(tmp, path)


_identifier_re = re.compile(r"[^0-9a-zA-Z_]+")


def _safe_identifier(name: str, *, lower: bool = True, prefix: str = "f") -> str:
    """Make a safe Python identifier from arbitrary text."""
    s = str(name or "").strip()
    if not s:
        return f"{prefix}_unnamed"

    if lower:
        s = s.lower()

    s = _identifier_re.sub("_", s)
    s = re.sub(r"_+", "_", s).strip("_")

    if not s:
        s = f"{prefix}_unnamed"

    if s[0].isdigit():
        s = f"{prefix}_{s}"

    if iskeyword(s):
        s = f"{s}_"

    return s


def _py_type_from_contract_type(contract_type: str, artifact_type: Optional[str] = None) -> str:
    """Convert contract type to Python type hint with stronger typing."""
    t = (contract_type or "any").lower()

    # Artifact types (from io_contract)
    if artifact_type:
        at = artifact_type.lower()
        if at == "json":
            return "Dict[str, Any]"
        if at == "bbox":
            return "BBox"
        if at == "mask":
            return "MaskArray"
        if at in ("image", "raster"):
            return "ImageArray"
        if at == "svg":
            return "str"
        if at == "path_list":
            return "List[PathData]"

    # Parameter types
    if t == "float":
        return "float"
    if t == "int":
        return "int"
    if t in ("bool", "boolean"):
        return "bool"
    if t == "string":
        return "str"
    if t == "json":
        return "Dict[str, Any]"
    if t == "enum":
        return "str"

    return "Any"


def _py_default_literal(p: Dict[str, Any]) -> Tuple[str, bool]:
    """Convert contract default value to Python literal."""
    if "default" not in p:
        return ("None", False)

    d = p["default"]
    if isinstance(d, str):
        return (repr(d), True)
    if isinstance(d, bool):
        return ("True" if d else "False", True)
    if isinstance(d, (int, float)):
        return (str(d), True)
    if d is None:
        return ("None", True)

    return ("None", True)


@dataclass(frozen=True)
class ContractMeta:
    """Metadata extracted from a Stage A contract."""
    module_id: str
    module_abbr: str
    module_type: str
    version: str
    schema_name: str
    schema_version: str
    contract_sha256: str


def _contract_meta(contract: Dict[str, Any], raw_bytes: bytes) -> ContractMeta:
    schema = contract.get("_schema", {}) or {}
    return ContractMeta(
        module_id=str(contract.get("module_id")),
        module_abbr=str(contract.get("module_abbr")),
        module_type=str(contract.get("module_type")),
        version=str(contract.get("version")),
        schema_name=str(schema.get("name")),
        schema_version=str(schema.get("version")),
        contract_sha256=_sha256_bytes(raw_bytes),
    )


def _autogen_header(meta: ContractMeta) -> str:
    """Deterministic autogen file header."""
    return (
        "# ======================================================================\n"
        "# AUTO-GENERATED FILE — DO NOT EDIT MANUALLY\n"
        "#\n"
        f"# generator: stageB.generator.generate_module v{GENERATOR_VERSION}\n"
        f"# contract_id: {meta.module_id} ({meta.module_abbr})\n"
        f"# contract_version: {meta.version}\n"
        f"# schema: {meta.schema_name} {meta.schema_version}\n"
        f"# contract_sha256: {meta.contract_sha256}\n"
        "#\n"
        "# Regenerate with: python -m stageB.generator.generate_module --all\n"
        "# ======================================================================\n\n"
    )


def _traceability_constants_block(meta: ContractMeta) -> str:
    """Runtime constants for traceability (Stage C/D can assert these)."""
    return (
        "# Traceability (runtime)\n"
        f"__generator_version__ = {GENERATOR_VERSION!r}\n"
        f"__contract_id__ = {meta.module_id!r}\n"
        f"__module_abbr__ = {meta.module_abbr!r}\n"
        f"__module_type__ = {meta.module_type!r}\n"
        f"__contract_version__ = {meta.version!r}\n"
        f"__schema_name__ = {meta.schema_name!r}\n"
        f"__schema_version__ = {meta.schema_version!r}\n"
        f"__contract_sha256__ = {meta.contract_sha256!r}\n\n"
    )


# -------------------------
# Autogen file builders
# -------------------------

def build_config_autogen(meta: ContractMeta, contract: Dict[str, Any]) -> str:
    """Generate config_autogen.py with Parameters dataclass and Enum classes."""
    params: Dict[str, Any] = contract.get("parameters", {}) or {}

    enum_classes: Dict[str, str] = {}
    has_optional = False

    # Track required fields (no default present in contract)
    required_py_fields: List[str] = []

    for param_name, spec in sorted(params.items()):
        if spec.get("type") == "enum" and spec.get("enum"):
            class_name = f"{_safe_identifier(param_name, lower=False).title().replace('_', '')}Type"
            enum_classes[param_name] = class_name
            if "default" not in spec:
                has_optional = True
        else:
            if "default" not in spec:
                has_optional = True

    lines: List[str] = []
    lines.append(_autogen_header(meta))
    lines.append("from __future__ import annotations\n\n")
    lines.append("from dataclasses import dataclass\n")
    if enum_classes:
        lines.append("from enum import Enum\n")

    typing_imports = ["Any", "ClassVar", "Dict", "List"]
    if has_optional:
        typing_imports.append("Optional")
    lines.append(f"from typing import {', '.join(sorted(typing_imports))}\n\n")

    # runtime traceability
    lines.append(_traceability_constants_block(meta))

    # Enum classes
    for param_name, spec in sorted(params.items()):
        if param_name in enum_classes:
            enum_values = spec["enum"]
            class_name = enum_classes[param_name]

            lines.append(f"class {class_name}(str, Enum):\n")
            lines.append(f'    """Enum for {param_name} parameter."""\n\n')
            for val in enum_values:
                safe_val = _safe_identifier(str(val), lower=False).upper()
                lines.append(f'    {safe_val} = "{val}"\n')
            lines.append("\n\n")

    mapping: Dict[str, str] = {}

    lines.append("@dataclass\n")
    lines.append("class Parameters:\n")
    lines.append(f'    """Configuration parameters for {meta.module_abbr} module.\n\n')
    lines.append(f"    Contract: {meta.module_id} v{meta.version}\n")
    lines.append('    """\n\n')

    if not params:
        lines.append("    pass  # No parameters declared in contract\n")
        return "".join(lines)

    for param_name in sorted(params.keys()):
        spec = params[param_name] or {}
        py_name = _safe_identifier(param_name)
        if py_name != param_name:
            mapping[py_name] = param_name

        # Determine python type + default
        if param_name in enum_classes:
            py_t = enum_classes[param_name]
            if "default" in spec and spec.get("default") is not None:
                default_literal = f'{py_t}.{_safe_identifier(str(spec["default"]), lower=False).upper()}'
            else:
                default_literal = "None"
                py_t = f"Optional[{py_t}]"
        else:
            base_t = _py_type_from_contract_type(spec.get("type", ""))
            default_literal, has_default = _py_default_literal(spec)
            if not has_default:
                # required in contract: keep default None in Stage B, but mark as required for validation
                required_py_fields.append(py_name)
            if default_literal == "None":
                py_t = f"Optional[{base_t}]" if base_t != "Any" else "Any"
            else:
                py_t = base_t

        desc = (spec.get("description") or "").replace("\n", " ").strip()
        unit = (spec.get("unit") or "").strip()
        rng = spec.get("range")

        comment_bits: List[str] = []
        if py_name != param_name:
            comment_bits.append(f"contract_name={param_name}")
        if desc:
            comment_bits.append(desc)
        if unit:
            comment_bits.append(f"unit={unit}")
        if rng is not None:
            comment_bits.append(f"range={rng}")
        if "default" not in spec:
            comment_bits.append("required_in_contract=true")

        if comment_bits:
            lines.append(f"    # {' | '.join(comment_bits)}\n")
        lines.append(f"    {py_name}: {py_t} = {default_literal}\n\n")

    lines.append("    # Mapping: python_name -> contract_name (ClassVar, immutable)\n")
    lines.append(f"    __contract_field_map__: ClassVar[Dict[str, str]] = {mapping!r}\n\n")

    lines.append("    # Fields that are required by contract (no default provided)\n")
    lines.append(f"    __required_fields__: ClassVar[List[str]] = {sorted(set(required_py_fields))!r}\n\n")

    lines.append("    def validate_required(self) -> List[str]:\n")
    lines.append('        """Validate required fields. Returns list of errors."""\n')
    lines.append("        errors: List[str] = []\n")
    lines.append("        for field_name in self.__required_fields__:\n")
    lines.append("            if getattr(self, field_name, None) is None:\n")
    lines.append("                errors.append(f'{field_name} is required (missing)')\n")
    lines.append("        return errors\n\n")

    lines.append("    def validate_ranges(self) -> List[str]:\n")
    lines.append('        """Validate numeric parameter ranges. Returns list of errors."""\n')
    lines.append("        errors: List[str] = []\n")

    for param_name in sorted(params.keys()):
        spec = params[param_name] or {}
        rng = spec.get("range")
        if rng and len(rng) == 2 and spec.get("type") in ("float", "int"):
            py_name = _safe_identifier(param_name)
            min_val, max_val = rng
            lines.append(f"        if self.{py_name} is not None:\n")
            lines.append(f"            if not ({min_val} <= self.{py_name} <= {max_val}):\n")
            lines.append(f"                errors.append(f'{py_name} must be in [{min_val}, {max_val}], got {{self.{py_name}}}')\n")

    lines.append("        return errors\n\n")

    lines.append("    @classmethod\n")
    lines.append("    def from_contract_dict(cls, data: Dict[str, Any]) -> 'Parameters':\n")
    lines.append('        """Create Parameters from contract-style dict (handles field renaming)."""\n')
    lines.append("        reverse_map = {v: k for k, v in cls.__contract_field_map__.items()}\n")
    lines.append("        mapped = {reverse_map.get(k, k): v for k, v in data.items()}\n")
    lines.append("        filtered = {k: v for k, v in mapped.items() if k in cls.__dataclass_fields__}\n")
    lines.append("        return cls(**filtered)\n")

    return "".join(lines)


def build_io_types_autogen(meta: ContractMeta, contract: Dict[str, Any]) -> str:
    """Generate io_types_autogen.py with typed Inputs/Outputs dataclasses."""
    io = contract.get("io_contract", {}) or {}
    ins = io.get("inputs", []) or []
    outs = io.get("outputs", []) or []

    needs_list = any(str(i.get("type") or "").lower() == "path_list" for i in (ins + outs))

    lines: List[str] = []
    lines.append(_autogen_header(meta))
    lines.append("from __future__ import annotations\n\n")
    lines.append("from dataclasses import dataclass\n")

    typing_imports = ["Any", "ClassVar", "Dict", "Optional", "TypeAlias"]
    if needs_list:
        typing_imports.append("List")
    lines.append(f"from typing import {', '.join(sorted(typing_imports))}\n\n")

    lines.append(_traceability_constants_block(meta))

    lines.append("# Type aliases for artifact types (Stage C will provide concrete implementations)\n")
    lines.append("BBox: TypeAlias = Dict[str, float]  # {x, y, width, height}\n")
    lines.append("MaskArray: TypeAlias = Any  # numpy array or similar\n")
    lines.append("ImageArray: TypeAlias = Any  # numpy array or PIL Image\n")
    lines.append("PathData: TypeAlias = Dict[str, Any]  # SVG path data\n\n")

    def emit_dataclass(kind: str, items: List[Dict[str, Any]]) -> None:
        lines.append("@dataclass\n")
        lines.append(f"class {kind}:\n")
        lines.append(f'    """{kind} artifacts for {meta.module_abbr} module.\n\n')
        if items:
            lines.append("    Artifacts:\n")
            for item in items:
                aid = item.get("artifact_id", "")
                atype = item.get("type", "")
                lines.append(f"        - {aid}: {atype}\n")
        lines.append('    """\n\n')

        if not items:
            lines.append("    pass\n\n")
            return

        mapping: Dict[str, str] = {}
        for item in items:
            aid = str(item.get("artifact_id") or "").strip()
            atype = str(item.get("type") or "").strip()
            desc = (item.get("description") or "").replace("\n", " ").strip()

            py_name = _safe_identifier(aid)
            if py_name != aid:
                mapping[py_name] = aid

            py_type = _py_type_from_contract_type("", artifact_type=atype)

            comment = f"type={atype}"
            if desc:
                comment += f" | {desc}"
            if py_name != aid:
                comment += f" | contract_artifact_id={aid}"

            lines.append(f"    # {comment}\n")
            lines.append(f"    {py_name}: Optional[{py_type}] = None\n\n")

        lines.append("    # Mapping: python_name -> contract_artifact_id (ClassVar, immutable)\n")
        lines.append(f"    __contract_field_map__: ClassVar[Dict[str, str]] = {mapping!r}\n\n")

        lines.append("    @classmethod\n")
        lines.append(f"    def from_contract_dict(cls, data: Dict[str, Any]) -> '{kind}':\n")
        lines.append('        """Create instance from contract-style dict (handles field renaming)."""\n')
        lines.append("        reverse_map = {v: k for k, v in cls.__contract_field_map__.items()}\n")
        lines.append("        mapped = {reverse_map.get(k, k): v for k, v in data.items()}\n")
        lines.append("        filtered = {k: v for k, v in mapped.items() if k in cls.__dataclass_fields__}\n")
        lines.append("        return cls(**filtered)\n\n")

    emit_dataclass("Inputs", ins)
    emit_dataclass("Outputs", outs)
    return "".join(lines)


def build_validators_autogen(meta: ContractMeta, contract: Dict[str, Any]) -> str:
    """Generate validators_autogen.py with constraint stubs."""
    constraints = contract.get("constraints", []) or []

    validation_block = contract.get("validation", {}) or {}
    rules = validation_block.get("rules", []) if isinstance(validation_block, dict) else []

    out: List[str] = []
    out.append(_autogen_header(meta))
    out.append("from __future__ import annotations\n\n")
    out.append("from typing import Any, Dict, List, NamedTuple, Optional\n\n")
    out.append("from .config_autogen import Parameters\n\n")
    out.append(_traceability_constants_block(meta))

    out.append("class ValidationIssue(NamedTuple):\n")
    out.append('    """Represents a validation issue."""\n\n')
    out.append("    code: str\n")
    out.append("    message: str\n")
    out.append("    severity: str  # 'error' | 'warning'\n")
    out.append("    field: Optional[str] = None\n\n\n")

    out.append("# Constraints from contract\n")
    out.append("CONSTRAINTS: List[Dict[str, Any]] = [\n")
    for c in constraints:
        out.append("    {\n")
        out.append(f"        'expr': {c.get('expr', '')!r},\n")
        out.append(f"        'error_code': {c.get('error_code', '')!r},\n")
        out.append("    },\n")
    out.append("]\n\n")

    out.append("# Validation rules from contract\n")
    out.append("VALIDATION_RULES: List[Dict[str, Any]] = [\n")
    for r in rules:
        out.append("    {\n")
        out.append(f"        'name': {r.get('name', '')!r},\n")
        out.append(f"        'condition': {r.get('condition', '')!r},\n")
        out.append(f"        'severity': {r.get('severity', '')!r},\n")
        out.append(f"        'message': {r.get('message', '')!r},\n")
        out.append(f"        'error_code': {r.get('error_code', '')!r},\n")
        out.append("    },\n")
    out.append("]\n\n\n")

    out.append("# Individual constraint validators (stubs for Stage C)\n\n")
    for c in constraints:
        expr = c.get("expr", "")
        error_code = c.get("error_code", "")
        func_name = f"check_{_safe_identifier(error_code)}"

        out.append(f"def {func_name}(params: Parameters) -> Optional[ValidationIssue]:\n")
        out.append(f'    """Check constraint: {expr}\n\n')
        out.append(f"    Error code: {error_code}\n")
        out.append('    """\n')
        out.append("    # TODO(Stage C): implement constraint logic\n")
        out.append(f"    # Expression: {expr}\n")
        out.append("    _ = params\n")
        out.append("    return None\n\n\n")

    out.append("def validate_parameters(params: Parameters) -> List[ValidationIssue]:\n")
    out.append(f'    """Validate {meta.module_abbr} parameters against all constraints.\n\n')
    out.append("    Returns a list of validation issues (empty = OK).\n")
    out.append('    """\n')
    out.append("    issues: List[ValidationIssue] = []\n\n")

    out.append("    # Required fields\n")
    out.append("    for err in params.validate_required():\n")
    out.append("        issues.append(ValidationIssue(\n")
    out.append("            code='REQUIRED_MISSING',\n")
    out.append("            message=err,\n")
    out.append("            severity='error',\n")
    out.append("        ))\n\n")

    out.append("    # Numeric ranges\n")
    out.append("    for err in params.validate_ranges():\n")
    out.append("        issues.append(ValidationIssue(\n")
    out.append("            code='RANGE_ERROR',\n")
    out.append("            message=err,\n")
    out.append("            severity='error',\n")
    out.append("        ))\n\n")

    out.append("    # Individual constraints\n")
    for c in constraints:
        error_code = c.get("error_code", "")
        func_name = f"check_{_safe_identifier(error_code)}"
        out.append(f"    if (issue := {func_name}(params)) is not None:\n")
        out.append("        issues.append(issue)\n")

    out.append("\n    return issues\n\n\n")

    out.append("def is_valid(params: Parameters) -> bool:\n")
    out.append('    """Quick check if parameters are valid."""\n')
    out.append("    return len(validate_parameters(params)) == 0\n")

    return "".join(out)


def build_pipeline_autogen(meta: ContractMeta, contract: Dict[str, Any]) -> str:
    """Generate pipeline_autogen.py with skeleton pipeline from algorithm steps."""
    algo = contract.get("algorithm", {}) or {}
    steps = algo.get("steps", []) or []
    artifact_registry = algo.get("artifact_registry", []) or []

    lines: List[str] = []
    lines.append(_autogen_header(meta))
    lines.append("from __future__ import annotations\n\n")
    lines.append("from dataclasses import dataclass, field\n")
    lines.append("from typing import Any, ClassVar, Dict, List, Optional\n\n")
    lines.append("from .config_autogen import Parameters\n")
    lines.append("from .io_types_autogen import Inputs, Outputs\n")
    lines.append("from .validators_autogen import validate_parameters\n\n")

    lines.append(_traceability_constants_block(meta))

    lines.append("@dataclass\n")
    lines.append("class StepResult:\n")
    lines.append('    """Result of a single pipeline step."""\n\n')
    lines.append("    id: str\n")
    lines.append("    name: str\n")
    lines.append("    step_type: str\n")
    lines.append("    status: str  # 'ok' | 'skipped' | 'error'\n")
    lines.append("    uses: List[str] = field(default_factory=list)\n")
    lines.append("    produces: List[str] = field(default_factory=list)\n")
    lines.append("    data: Dict[str, Any] = field(default_factory=dict)\n")
    lines.append("    error: Optional[str] = None\n\n\n")

    lines.append("@dataclass\n")
    lines.append("class PipelineState:\n")
    lines.append('    """State passed between pipeline steps."""\n\n')
    lines.append("    inputs: Inputs\n")
    lines.append("    params: Parameters\n")
    lines.append("    artifacts: Dict[str, Any] = field(default_factory=dict)\n")
    lines.append("    step_results: List[StepResult] = field(default_factory=list)\n\n\n")

    step_methods: List[Tuple[str, Dict[str, Any]]] = []
    for idx, s in enumerate(steps):
        sid = s.get("id")
        sname = s.get("name")
        key = sid if sid else (sname if sname else f"step_{idx+1}")
        method = f"_step_{_safe_identifier(str(key))}"
        step_methods.append((method, s))

    lines.append(f"class {meta.module_abbr}Pipeline:\n")
    lines.append(f'    """{meta.module_abbr} Pipeline — {meta.module_type}\n\n')
    lines.append(f"    Contract: {meta.module_id} v{meta.version}\n\n")
    lines.append("    Steps:\n")
    for method, s in step_methods:
        sid = s.get("id", "")
        sname = s.get("name", "")
        stype = s.get("type", "")
        lines.append(f"        {sid}: {sname} ({stype})\n")
    lines.append('    """\n\n')

    lines.append("    ARTIFACT_REGISTRY: ClassVar[List[Dict[str, str]]] = [\n")
    for art in artifact_registry:
        lines.append(f"        {{'artifact_id': {art.get('artifact_id', '')!r}, 'scope': {art.get('scope', '')!r}}},\n")
    lines.append("    ]\n\n")

    lines.append("    def __init__(self, params: Parameters) -> None:\n")
    lines.append("        self.params = params\n")
    lines.append("        self._state: Optional[PipelineState] = None\n\n")

    lines.append("    def run(self, inputs: Inputs) -> Outputs:\n")
    lines.append('        """Execute the full pipeline."""\n')
    lines.append("        issues = validate_parameters(self.params)\n")
    lines.append("        errors = [i for i in issues if i.severity == 'error']\n")
    lines.append("        if errors:\n")
    lines.append("            raise ValueError(f'Parameter validation failed: {errors}')\n\n")
    lines.append("        self._state = PipelineState(inputs=inputs, params=self.params)\n\n")
    lines.append("        # Execute steps\n")
    for method, s in step_methods:
        sid = s.get("id", "")
        sname = s.get("name", "")
        lines.append(f"        self.{method}()  # {sid}: {sname}\n")
    lines.append("\n        return self._build_outputs()\n\n")

    for method, s in step_methods:
        sid = s.get("id", "")
        sname = s.get("name", "")
        stype = s.get("type", "")
        uses = s.get("uses", [])
        produces = s.get("produces", [])
        desc = (s.get("description") or "").replace("\n", " ").strip()

        lines.append(f"    def {method}(self) -> None:\n")
        lines.append(f'        """{sid}: {sname}\n\n')
        if desc:
            lines.append(f"        {desc}\n\n")
        lines.append(f"        Type: {stype}\n")
        lines.append(f"        Uses: {uses}\n")
        lines.append(f"        Produces: {produces}\n")
        lines.append('        """\n')
        lines.append("        # TODO(Stage C): implement this step\n")
        lines.append("        assert self._state is not None\n")
        lines.append("        self._state.step_results.append(StepResult(\n")
        lines.append(f"            id={sid!r},\n")
        lines.append(f"            name={sname!r},\n")
        lines.append(f"            step_type={stype!r},\n")
        lines.append("            status='ok',\n")
        lines.append(f"            uses={uses!r},\n")
        lines.append(f"            produces={produces!r},\n")
        lines.append("        ))\n\n")

    lines.append("    def _build_outputs(self) -> Outputs:\n")
    lines.append('        """Build final Outputs from pipeline state."""\n')
    lines.append("        # TODO(Stage C): populate outputs from self._state.artifacts\n")
    lines.append("        assert self._state is not None\n")
    lines.append("        return Outputs()\n\n\n")

    lines.append("def run_skeleton(inputs: Inputs, params: Parameters) -> Outputs:\n")
    lines.append(f'    """Convenience function to run {meta.module_abbr} pipeline."""\n')
    lines.append(f"    pipeline = {meta.module_abbr}Pipeline(params)\n")
    lines.append("    return pipeline.run(inputs)\n")

    return "".join(lines)


def build_cli_autogen(meta: ContractMeta, contract: Dict[str, Any]) -> str:
    """Generate cli_autogen.py with minimal CLI stub."""
    lines: List[str] = []
    lines.append(_autogen_header(meta))
    lines.append("from __future__ import annotations\n\n")
    lines.append("import argparse\n")
    lines.append("import json\n")
    lines.append("import sys\n")
    lines.append("from pathlib import Path\n")
    lines.append("from typing import Any, Dict, List, Optional\n\n")
    lines.append("from .config_autogen import Parameters\n")
    lines.append("from .io_types_autogen import Inputs\n")
    lines.append("from .pipeline_autogen import run_skeleton\n")
    lines.append("from .validators_autogen import validate_parameters\n\n")

    lines.append(_traceability_constants_block(meta))

    lines.append("def main(argv: Optional[List[str]] = None) -> int:\n")
    lines.append(f'    """CLI entry point for {meta.module_abbr} module."""\n')
    lines.append("    parser = argparse.ArgumentParser(\n")
    lines.append(f"        prog='{meta.module_abbr.lower()}',\n")
    lines.append(f"        description='{meta.module_id} — {meta.module_abbr} ({meta.module_type})',\n")
    lines.append("    )\n")
    lines.append("    parser.add_argument('--inputs', type=str, help='Path to JSON inputs file')\n")
    lines.append("    parser.add_argument('--params', type=str, help='Path to JSON params file')\n")
    lines.append("    parser.add_argument('--output', type=str, help='Path to write JSON output')\n")
    lines.append("    parser.add_argument('--validate-only', action='store_true', help='Only validate, do not run')\n")
    lines.append("    args = parser.parse_args(argv)\n\n")

    lines.append("    inputs_data: Dict[str, Any] = {}\n")
    lines.append("    if args.inputs:\n")
    lines.append("        inputs_data = json.loads(Path(args.inputs).read_text(encoding='utf-8'))\n")
    lines.append("    inputs_obj = Inputs.from_contract_dict(inputs_data)\n\n")

    lines.append("    params_data: Dict[str, Any] = {}\n")
    lines.append("    if args.params:\n")
    lines.append("        params_data = json.loads(Path(args.params).read_text(encoding='utf-8'))\n")
    lines.append("    params_obj = Parameters.from_contract_dict(params_data)\n\n")

    lines.append("    if args.validate_only:\n")
    lines.append("        issues = validate_parameters(params_obj)\n")
    lines.append("        result: Dict[str, Any] = {\n")
    lines.append("            'valid': len(issues) == 0,\n")
    lines.append("            'issues': [i._asdict() for i in issues],\n")
    lines.append("        }\n")
    lines.append("        print(json.dumps(result, indent=2, ensure_ascii=False))\n")
    lines.append("        return 0 if result['valid'] else 1\n\n")

    lines.append("    try:\n")
    lines.append("        outputs = run_skeleton(inputs_obj, params_obj)\n")
    lines.append("        result = {'status': 'ok', 'outputs': outputs.__dict__}\n")
    lines.append("    except Exception as e:\n")
    lines.append("        result = {'status': 'error', 'error': str(e)}\n")
    lines.append("        print(f'Error: {e}', file=sys.stderr)\n")
    lines.append("        return 1\n\n")

    lines.append("    output_json = json.dumps(result, indent=2, ensure_ascii=False)\n")
    lines.append("    if args.output:\n")
    lines.append("        Path(args.output).write_text(output_json, encoding='utf-8')\n")
    lines.append("    else:\n")
    lines.append("        print(output_json)\n\n")
    lines.append("    return 0\n\n\n")

    lines.append("if __name__ == '__main__':\n")
    lines.append("    sys.exit(main())\n")

    return "".join(lines)


def build_readme_autogen(meta: ContractMeta, contract: Dict[str, Any]) -> str:
    """Generate README_autogen.md with full module documentation."""
    name_uk = (contract.get("module_name", {}) or {}).get("uk", "")
    name_en = (contract.get("module_name", {}) or {}).get("en", "")
    desc = contract.get("description", "") or ""

    io = contract.get("io_contract", {}) or {}
    ins = io.get("inputs", []) or []
    outs = io.get("outputs", []) or []
    params = contract.get("parameters", {}) or {}
    constraints = contract.get("constraints", []) or []
    algo = contract.get("algorithm", {}) or {}
    steps = algo.get("steps", []) or []

    md: List[str] = []
    md.append(f"# {meta.module_id} — {meta.module_abbr}\n\n")
    md.append(f"**Type:** `{meta.module_type}`\n\n")

    if name_en:
        md.append(f"**English:** {name_en}\n\n")
    if name_uk:
        md.append(f"**Українською:** {name_uk}\n\n")

    md.append("---\n\n")

    md.append("## Traceability\n\n")
    md.append("| Field | Value |\n")
    md.append("|-------|-------|\n")
    md.append(f"| contract_version | `{meta.version}` |\n")
    md.append(f"| schema | `{meta.schema_name} {meta.schema_version}` |\n")
    md.append(f"| contract_sha256 | `{meta.contract_sha256[:16]}...` |\n")
    md.append(f"| generator | `v{GENERATOR_VERSION}` |\n\n")

    md.append("## Description\n\n")
    md.append(f"{desc}\n\n")

    md.append("## Inputs\n\n")
    if ins:
        md.append("| Artifact | Type | Scope | Description |\n")
        md.append("|----------|------|-------|-------------|\n")
        for item in ins:
            aid = item.get("artifact_id", "")
            atype = item.get("type", "")
            scope = item.get("scope", "public")
            adesc = (item.get("description") or "").replace("\n", " ")
            md.append(f"| `{aid}` | `{atype}` | {scope} | {adesc} |\n")
    else:
        md.append("_No inputs defined._\n")
    md.append("\n")

    md.append("## Outputs\n\n")
    if outs:
        md.append("| Artifact | Type | Scope | Description |\n")
        md.append("|----------|------|-------|-------------|\n")
        for item in outs:
            aid = item.get("artifact_id", "")
            atype = item.get("type", "")
            scope = item.get("scope", "public")
            adesc = (item.get("description") or "").replace("\n", " ")
            md.append(f"| `{aid}` | `{atype}` | {scope} | {adesc} |\n")
    else:
        md.append("_No outputs defined._\n")
    md.append("\n")

    md.append("## Parameters\n\n")
    if params:
        md.append("| Name | Type | Default | Range | Description |\n")
        md.append("|------|------|---------|-------|-------------|\n")
        for name in sorted(params.keys()):
            spec = params[name] or {}
            ptype = spec.get("type", "")
            default = spec.get("default", "—") if "default" in spec else "—"
            rng = spec.get("range", "")
            rng_str = f"`{rng}`" if rng else "—"
            pdesc = (spec.get("description") or "").replace("\n", " ")
            md.append(f"| `{name}` | `{ptype}` | `{default}` | {rng_str} | {pdesc} |\n")
    else:
        md.append("_No parameters defined._\n")
    md.append("\n")

    md.append("## Algorithm Steps\n\n")
    if steps:
        md.append("| ID | Name | Type | Uses | Produces |\n")
        md.append("|----|------|------|------|----------|\n")
        for s in steps:
            sid = s.get("id", "")
            sname = s.get("name", "")
            stype = s.get("type", "")
            uses = ", ".join(s.get("uses", []) or [])
            produces = ", ".join(s.get("produces", []) or [])
            md.append(f"| `{sid}` | {sname} | `{stype}` | {uses} | {produces} |\n")
    else:
        md.append("_No steps defined._\n")
    md.append("\n")

    md.append("## Constraints\n\n")
    if constraints:
        md.append("| Error Code | Expr |\n")
        md.append("|------------|------|\n")
        for c in constraints:
            code = c.get("error_code", "")
            expr = c.get("expr", "")
            md.append(f"| `{code}` | `{expr}` |\n")
    else:
        md.append("_No constraints defined._\n")
    md.append("\n")

    md.append("---\n\n")
    md.append(f"_Auto-generated by stageB.generator v{GENERATOR_VERSION}. Do not edit manually._\n")

    return "".join(md)


# -------------------------
# Generation orchestration
# -------------------------

def generate_for_contract_path(contract_path: Path) -> Path:
    """Generate all autogen files for a single contract."""
    raw = contract_path.read_bytes()
    contract = json.loads(raw.decode("utf-8"))
    meta = _contract_meta(contract, raw)

    mod_dir = STAGEB_MODULES_DIR / meta.module_abbr
    mod_dir.mkdir(parents=True, exist_ok=True)

    autogen_map = {
        "config_autogen.py": build_config_autogen(meta, contract),
        "io_types_autogen.py": build_io_types_autogen(meta, contract),
        "validators_autogen.py": build_validators_autogen(meta, contract),
        "pipeline_autogen.py": build_pipeline_autogen(meta, contract),
        "cli_autogen.py": build_cli_autogen(meta, contract),
        "README_autogen.md": build_readme_autogen(meta, contract),
    }

    for fname, content in autogen_map.items():
        if not (fname.endswith("_autogen.py") or fname.endswith("_autogen.md")):
            raise RuntimeError(f"Refusing to write non-autogen file: {fname}")
        _atomic_write_text(mod_dir / fname, content)

    return mod_dir


def discover_contracts() -> List[Path]:
    """Find all Stage A contract files."""
    return sorted(STAGEA_CONTRACTS_DIR.glob("*_contract_stageA_FINAL.json"))


def _filter_contracts_by_abbr(contracts: List[Path], abbr: str) -> List[Path]:
    wanted = abbr.strip().upper()
    out: List[Path] = []
    for p in contracts:
        try:
            data = _read_json(p)
            if str(data.get("module_abbr") or "").strip().upper() == wanted:
                out.append(p)
        except Exception:
            continue
    return out


def main(argv: List[str] | None = None) -> int:
    """CLI entry point for generator."""
    parser = argparse.ArgumentParser(
        description="Generate Stage B module skeletons from Stage A contracts"
    )
    parser.add_argument("--all", action="store_true", help="Generate for all Stage A contracts")
    parser.add_argument("--module", type=str, default=None, help="Module ABBR to generate (e.g., SPS)")
    args = parser.parse_args(argv)

    contracts = discover_contracts()
    if args.module:
        contracts = _filter_contracts_by_abbr(contracts, args.module)

    if not args.all and not args.module:
        parser.error("Specify --all or --module <ABBR>")

    if not contracts:
        print("No contracts found for selection", file=sys.stderr)
        return 1

    print("Generated:")
    for contract_path in contracts:
        out_dir = generate_for_contract_path(contract_path)
        print(f"  - {out_dir.relative_to(REPO_ROOT)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
