# Testing

Test berada pada:

```text
tests/
```

Menjalankan test tertentu:

```bash
pytest tests/[nama_file].py -v
```

Menjalankan seluruh test:

```bash
pytest -v
```

Area yang perlu diuji:

```text
API validation
Prompt injection validation
Retrieval
RBAC retrieval filter
Session & sidebar
Rate limiting (termasuk /api/rate-limit-test)
CORS
Anonymization
Log export
Feedback
Admin endpoints
Document screening (duplicate / confidential)
Versioning (Pricelist)
Retention cleanup
```
