# =============================================================================
# Stage A (+ Stage B) — Makefile
# =============================================================================
# Usage:
#   make              — show help
#   make validate     — validate all contracts
#   make test         — run unit tests
#   make all          — validate + test (Stage A full check)
#   make quick        — quick validation only (no tests)
#   make new          — generate new contract template (interactive)
#   make clean        — remove generated reports + caches
#
#   make stageB       — Stage B: generate skeletons + run B-Gate tests
#   make stageB-gen   — Stage B: generate only
#   make stageB-test  — Stage B: tests only
#   make all-stages   — Stage A + Stage B
# =============================================================================

.PHONY: help all validate test quick new clean lint ci stageB stageB-gen stageB-test all-stages

# Default Python interpreter
PYTHON ?= python3

# Paths
CONTRACTS_DIR := stageA/contracts
SCHEMA := stageA/schema/contract_schema_stageA_v4.json
GLOSSARY := stageA/glossary/glossary_v1.json
REPORTS_DIR := stageA/_reports

# Colors (optional, for pretty output)
GREEN := \033[0;32m
YELLOW := \033[0;33m
RED := \033[0;31m
NC := \033[0m # No Color

# =============================================================================
# HELP (default target)
# =============================================================================
help:
	@echo ""
	@echo "╔══════════════════════════════════════════════════════════════╗"
	@echo "║           Stage A (+ Stage B) — Make Commands                ║"
	@echo "╚══════════════════════════════════════════════════════════════╝"
	@echo ""
	@echo "  Stage A:"
	@echo "    make all          — Full validation + tests (recommended)"
	@echo "    make validate     — Validate all contracts"
	@echo "    make test         — Run unit tests"
	@echo "    make quick        — Quick validation (skip tests)"
	@echo "    make lint         — Lint contracts with verbose output"
	@echo "    make new          — Generate new contract from template"
	@echo "    make clean        — Remove generated reports + caches"
	@echo ""
	@echo "  Stage B:"
	@echo "    make stageB       — Generate skeletons + B-Gate tests"
	@echo "    make stageB-gen   — Generate skeletons only"
	@echo "    make stageB-test  — Run B-Gate tests only"
	@echo "    make all-stages   — Stage A + Stage B"
	@echo ""
	@echo "Examples:"
	@echo "  make all"
	@echo "  make stageB"
	@echo "  make all-stages"
	@echo "  make new MODULE_ID=A-V-1 ABBR=TONE TYPE=PROCESS"
	@echo ""

# =============================================================================
# STAGE A — MAIN TARGETS
# =============================================================================

## Full validation + tests
all: validate test
	@echo ""
	@echo "$(GREEN)✅ Stage A checks passed!$(NC)"

## Validate all contracts
validate:
	@echo ""
	@echo "▶ Validating contracts..."
	@mkdir -p $(REPORTS_DIR)
	@$(PYTHON) stageA/tools/batch_validator.py $(CONTRACTS_DIR) \
		--glossary $(GLOSSARY) \
		--schema $(SCHEMA) \
		--out $(REPORTS_DIR) \
		--verbose

## Run unit tests
test:
	@echo ""
	@echo "▶ Running unit tests..."
	@$(PYTHON) -m unittest discover -s stageA/tests -p "test_*.py" -v

## Quick validation (no tests)
quick:
	@echo ""
	@echo "▶ Quick validation..."
	@$(PYTHON) stageA/tools/batch_validator.py $(CONTRACTS_DIR) \
		--glossary $(GLOSSARY) \
		--schema $(SCHEMA)

## Lint with verbose output
lint:
	@echo ""
	@echo "▶ Linting contracts..."
	@$(PYTHON) stageA/tools/batch_validator.py $(CONTRACTS_DIR) \
		--glossary $(GLOSSARY) \
		--schema $(SCHEMA) \
		--out $(REPORTS_DIR) \
		--verbose

# =============================================================================
# STAGE A — GENERATE NEW CONTRACT
# =============================================================================

## Generate new contract from template
## Usage: make new MODULE_ID=A-V-1 ABBR=TONE TYPE=PROCESS NAME_UK="..." NAME_EN="..."
new:
ifndef MODULE_ID
	@echo "$(RED)Error: MODULE_ID is required$(NC)"
	@echo "Usage: make new MODULE_ID=A-V-1 ABBR=TONE TYPE=PROCESS NAME_UK=\"...\" NAME_EN=\"...\""
	@exit 1
endif
ifndef ABBR
	@echo "$(RED)Error: ABBR is required$(NC)"
	@exit 1
endif
ifndef TYPE
	@echo "$(RED)Error: TYPE is required (PROCESS/RULESET/BRIDGE)$(NC)"
	@exit 1
endif
	@$(PYTHON) stageA/tools/generate_from_template.py \
		--module-id $(MODULE_ID) \
		--module-abbr $(ABBR) \
		--module-type $(TYPE) \
		--module-name-uk "$(or $(NAME_UK),TODO: Ukrainian name)" \
		--module-name-en "$(or $(NAME_EN),TODO: English name)" \
		--out $(CONTRACTS_DIR)/$(MODULE_ID)_$(ABBR)_contract_stageA_FINAL.json
	@echo ""
	@echo "$(GREEN)✅ Contract created: $(CONTRACTS_DIR)/$(MODULE_ID)_$(ABBR)_contract_stageA_FINAL.json$(NC)"
	@echo "$(YELLOW)→ Don't forget to fill in TODO sections!$(NC)"

# =============================================================================
# STAGE B — SKELETON GENERATION + GATES
# =============================================================================

## Stage B: generate + test
stageB: stageB-gen stageB-test
	@echo ""
	@echo "$(GREEN)✅ Stage B checks passed!$(NC)"

## Stage B: generate only
stageB-gen:
	@echo ""
	@echo "▶ Stage B: Generating skeletons..."
	@$(PYTHON) run_stageB.py --gen

## Stage B: tests only
stageB-test:
	@echo ""
	@echo "▶ Stage B: Running B-Gate tests..."
	@$(PYTHON) -m unittest discover -s stageB/tests -p "test_*.py" -v

## Stage A + Stage B
all-stages: all stageB
	@echo ""
	@echo "$(GREEN)✅ All stages passed (Stage A + Stage B)!$(NC)"

# =============================================================================
# CLEANUP
# =============================================================================

## Remove generated reports + caches
clean:
	@echo "▶ Cleaning up..."
	@rm -rf $(REPORTS_DIR)
	@rm -rf stageB/_reports 2>/dev/null || true
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@find . -type f -name "*.tmp" -delete 2>/dev/null || true
	@echo "$(GREEN)✅ Cleaned$(NC)"

# =============================================================================
# CI SIMULATION
# =============================================================================

## Simulate CI pipeline locally
ci: clean all-stages
	@echo ""
	@echo "$(GREEN)✅ CI simulation passed!$(NC)"
