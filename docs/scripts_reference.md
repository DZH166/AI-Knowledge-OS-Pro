# Scripts Reference

Run scripts from the repository root unless a script explicitly says otherwise.

| Script | Purpose | Example | Modifies Data | CI |
| --- | --- | --- | --- | --- |
| `scripts/audit_codebase.py` | Generate V4.1 inventory, predevelopment audit and dead-code reports. | `python scripts/audit_codebase.py` | Writes docs reports | No |
| `scripts/capture_showcase.py` | Capture README/demo screenshots after local app pages load. | `python scripts/capture_showcase.py` | Writes screenshots | No |
| `scripts/check_demo_ready.py` | Validate isolated synthetic demo DB readiness. | `python scripts/check_demo_ready.py --database-path backend/data/demo_showcase.db` | No | Yes |
| `scripts/check_encoding.py` | Validate UTF-8 text and mojibake markers. | `python scripts/check_encoding.py` | No | Yes |
| `scripts/check_frontend_smoke.py` | Static route/navigation smoke check for frontend files. | `python scripts/check_frontend_smoke.py` | No | Yes |
| `scripts/check_release.py` | Inspect generated release zip for required/forbidden entries. | `python scripts/check_release.py --version V3.8` | No | Yes |
| `scripts/check_repo_clean.py` | Ensure forbidden generated/user data is not tracked. | `python scripts/check_repo_clean.py` | No | Yes |
| `scripts/check_secrets.py` | Scan tracked text for secret-like values. | `python scripts/check_secrets.py` | No | Yes |
| `scripts/check_version.py` | Check visible project version consistency. | `python scripts/check_version.py` | No | Yes |
| `scripts/evaluate_rag.py` | Run demo RAG evaluation checks. | `python scripts/evaluate_rag.py --demo` | Reads demo DB | Yes |
| `scripts/generate_learning_package.py` | Build a learning package draft from Git changes and evidence. | `python scripts/generate_learning_package.py --version V4.1` | Writes only when output is requested by caller | No |
| `scripts/release.py` | Build or dry-run release package with exclusions and secret scan. | `python scripts/release.py --version V3.8 --dry-run` | Writes release zip unless `--dry-run` | Yes |
| `scripts/reset_demo_data.py` | Reset isolated demo database only. | `python scripts/reset_demo_data.py` | Writes demo DB | No |
| `scripts/seed_demo_data.py` | Seed synthetic demo database. | `python scripts/seed_demo_data.py --database-path backend/data/demo_showcase.db --reset` | Writes demo DB | Yes |
| `scripts/seed_showcase.py` | Seed richer synthetic showcase data and media metadata. | `python scripts/seed_showcase.py --reset` | Writes showcase DB and synthetic assets | No |
| `scripts/setup_demo.py` | Start Redis/Qdrant optionally and prepare demo data. | `python scripts/setup_demo.py --skip-docker --reset` | Writes demo DB | No |
| `scripts/smoke_test_real_services.py` | Manual smoke helper for configured real providers. | `python scripts/smoke_test_real_services.py` | Calls external services if configured | No |

## Safety Notes

- Release and check scripts must not read or print real secret values.
- Demo and showcase scripts must only write explicitly synthetic data.
- `reset_demo_data.py` refuses paths outside the intended demo database.
- `release.py --dry-run` is the default safe verification command for CI and local release review.
