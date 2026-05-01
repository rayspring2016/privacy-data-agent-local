# Privacy Data Agent

Local-first pipeline for sensitive HR and business data.

## Flow

1. Read CSV or XLSX locally.
2. Detect sensitive values from columns and patterns.
3. Replace raw values with stable tokens.
4. Save token mapping in an encrypted local file.
5. Send only anonymized CSV to the model.
6. Save the anonymized model report.
7. Restore original values into the final report locally.

## Sensitive Data Covered

- Employee/person names from name-like columns
- Chinese resident ID numbers
- Departments and organizations
- Customer/client/company names
- Phone numbers
- Email addresses

## Generate Local Mapping Key

```bash
export PRIVACY_AGENT_KEY="$(python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')"
```

Keep this key local. Without it, `mapping.enc.json` cannot be restored.

## Run with Fake Provider

```bash
privacy-data-agent analyze tests/fixtures/hr_sample.csv --output-dir runs/manual
```

The fake provider is deterministic and does not call the network. It writes `runs/manual/model_prompt.anonymized.md` so you can inspect exactly what would have been sent to the model.

## Run with OpenAI-Compatible Provider

```bash
export OPENAI_API_KEY="your_api_key"
privacy-data-agent analyze tests/fixtures/hr_sample.csv \
  --output-dir runs/openai \
  --provider openai \
  --model gpt-4.1-mini \
  --instruction "请分析销售额、客户跟进风险和可复制动作。"
```

## Output Files

- `anonymized.csv`: model-safe data with tokens.
- `mapping.enc.json`: encrypted local mapping file.
- `model_prompt.anonymized.md`: prompt captured by fake provider.
- `model_report.anonymized.md`: model output before restoration.
- `model_report.restored.md`: final local report with original values restored.
- `run_manifest.json`: file manifest for the run.

## Privacy Check

Run:

```bash
pytest -q
```

The test suite verifies raw fixture values do not appear in anonymized data, captured model prompts, or anonymized model reports.
