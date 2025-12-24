# Stage A — Contract Canon

[![Stage A CI](https://github.com/YOUR_USERNAME/painting-system/actions/workflows/stageA-ci.yml/badge.svg)](https://github.com/YOUR_USERNAME/painting-system/actions)

Stage A є **єдиним джерелом істини** для проекту «малювання».

Він визначає:
- Структуру модулів та їхні типи (PROCESS / RULESET / BRIDGE)
- Входи та виходи (io_contract)
- Параметри з одиницями вимірювання та діапазонами
- Обмеження (constraints) та правила валідації
- Алгоритм виконання з data flow
- Канон контрактів (незалежний від реалізацій)

Stage A **не містить реалізацій** і **не прив'язаний до конкретного рушія**  
(Python / AI / інше — це наступні стадії).

## Версія

- **Schema Version:** 4.0.0
- **Catalog Version:** 4.0.0
- **Контракти:** 3 пілотних модулі

## Швидкий старт

### Валідація контрактів

```bash
# Валідація всіх контрактів
python stageA/tools/batch_validator.py stageA/contracts \
    --glossary stageA/glossary/glossary_v1.json \
    --out stageA/_reports

# Запуск тестів
python -m unittest discover -s stageA/tests -p "test_*.py" -v
```

### Генерація нового контракту

```bash
python stageA/tools/generate_from_template.py \
    --module-id A-V-1 \
    --module-abbr TONE \
    --module-type PROCESS \
    --module-name-uk "ТОНАЛЬНА КАРТА" \
    --module-name-en "TONE MAP" \
    --out stageA/contracts/A-V-1_TONE_contract_stageA_FINAL.json
```

## Структура Stage A

```
stageA/
├── contracts/       # Контракти модулів (Stage A)
│   ├── A-I-3_SPS_contract_stageA_FINAL.json
│   ├── A-III-2_NSS_contract_stageA_FINAL.json
│   └── A-IV-2_LINE_contract_stageA_FINAL.json
├── glossary/        # Глосарій термінів
│   └── glossary_v1.json
├── katalog/         # Індекс усіх модулів
│   └── katalog_4_0.json
├── schema/          # JSON Schema для контрактів
│   └── contract_schema_stageA_v4.json
├── lint/            # Lint-спека + валідатори
│   ├── LINT_SPEC_STAGE_A.md
│   └── contract_lint_validator.py
├── tools/           # Інструменти
│   ├── batch_validator.py
│   └── generate_from_template.py
└── tests/           # Тести
    └── test_stageA_contracts.py
```

## Пілотні модулі

| ID | Abbr | Type | Назва | Опис |
|----|------|------|-------|------|
| A-I-3 | SPS | BRIDGE | Shot / Plan System | Канонічна система планів і кадрування |
| A-III-2 | NSS | RULESET | Negative Space System | Аналіз негативного простору |
| A-IV-2 | LINE | PROCESS | Line Engine | Нормалізація контурних ліній |

## Contracts (stageA/contracts/)

Кожен файл:
- Описує **один модуль**
- Має строгий контрактний канон
- Валідний через **JSON Schema v4 + lint**
- Містить всі обов'язкові секції:
  - `_schema` — метадані схеми
  - `io_contract` — входи/виходи
  - `parameters` — параметри з одиницями
  - `constraints` — жорсткі обмеження (помилки)
  - `validation` — м'які правила (попередження)
  - `error_codes` — реєстр кодів помилок
  - `algorithm` — кроки виконання з data flow
  - `test_cases` — тестові сценарії

### Приклад контракту

```json
{
  "_schema": {
    "name": "A-PRACTICAL.contract",
    "version": "4.0.0",
    "stage": "A.contract_only",
    "maturity_stage": "pilot",
    "static_frame_only": true,
    "underpainting_intent": "structure_only",
    "created_at": "2025-12-24T22:00:00+02:00",
    "updated_at": "2025-12-24T22:00:00+02:00"
  },
  "module_id": "A-I-3",
  "module_abbr": "SPS",
  "module_type": "BRIDGE",
  ...
}
```

## Schema (stageA/schema/)

JSON Schema для Stage A контрактів (draft 2020-12):
- Перевіряє структуру та обов'язкові поля
- Валідує формати (module_id, timestamps, error codes)
- Забезпечує типізацію параметрів

## Lint (stageA/lint/)

Семантична валідація контрактів:
- Required sections
- Policy rules
- Constraints DSL format
- Error code coverage
- Data flow validation
- Glossary coverage (optional)

## Glossary (stageA/glossary/)

Єдині визначення термінів:
- Всі терміни з контрактів **мають бути присутні**
- Режими перевірки: `strict` / `warn` / `off`
- Включає одиниці вимірювання та типи артефактів

## Katalog (stageA/katalog/)

Легкий індекс усіх модулів:
- `module_id`, `module_abbr`, `module_type`
- `version`, `maturity_stage`, `readiness`
- Посилання на контракти
- Залежності між модулями

## CI/CD

GitHub Actions автоматично:
1. Валідує всі контракти через batch_validator
2. Запускає тести
3. Перевіряє синхронізацію з каталогом

## Типи модулів

| Тип | Призначення |
|-----|-------------|
| **PROCESS** | Генеративні модулі — створюють нові артефакти |
| **RULESET** | Валідаційні модулі — перевіряють правила |
| **BRIDGE** | Mapping модулі — з'єднують різні системи |

## Constraints DSL

Формат виразів (syntax: `string_expr`):

```json
{
  "expr": "shot_type == 'ECU' => framing_tightness >= 0.85",
  "error_code": "E001"
}
```

Підтримувані оператори:
- Порівняння: `==`, `!=`, `>`, `>=`, `<`, `<=`
- Логічні: `&&`, `||`, `!`
- Імплікація: `=>`

## Версіонування

- **Schema version** — версія JSON Schema (4.0.0)
- **Contract version** — версія конкретного контракту (SemVer)
- **Maturity stage** — рівень зрілості (`pilot` → `draft` → `stable`)

---

**Stage A — це канон,  
Stage B+ — це реалізації.**

## Ліцензія

MIT License — див. LICENSE файл.
