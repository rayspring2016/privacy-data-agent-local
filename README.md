# Privacy Data Agent

Local-first pipeline for sensitive HR and business data:

1. Read CSV or XLSX locally.
2. Replace sensitive names, ID numbers, departments, customer names, phones, and emails with stable tokens.
3. Store the original-to-token mapping in an encrypted local file.
4. Send only anonymized data to a model provider for analysis.
5. Restore original values into the final report locally.

## Privacy Boundary

Raw sensitive values never cross the model boundary. The model receives tokens such as `EMP_0001`, `DEPT_0001`, and `CUSTOMER_0001`.

## Required Environment

```bash
export PRIVACY_AGENT_KEY="$(python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')"
```

## CLI

```bash
privacy-data-agent analyze tests/fixtures/hr_sample.csv --output-dir runs/manual
```
