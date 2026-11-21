# Multi-Account Architecture Report

Date: 19 Nov 2026
Prepared for: Owner review

## Current State

The codebase contains multi-account infrastructure but it is **NOT DEPLOYED**.

### Deployed Components (Owner's channel only)

- Single YouTube login in `data/auth.json`
- Single OpenRouter key for all models
- Single dashboard at `http://fedora:8913`
- Single container: `studio-dashboard`
- Single storage path: `output/` and `data/`

### Undeployed Multi-Account Code

| Component | Status | Location |
|---|---|---|
| Tenant detection | Gated but unused | `tenantmode.py` (line 1: `is_tenant()` returns False) |
| Proxy routing | Not active | `studio-proxy` directory |
| Per-account credentials | Not configured | `data/tenants.json` does not exist |
| Container isolation | Available | `deploy/tenant.sh` (defaults to deleted VPS) |
| YouTube scopes | Hardcoded | `ytweb.py` - single scope list |

**Verification:**
```bash
$ ls data/tenants.json
ls: cannot access 'data/tenants.json': No such file or directory
$ STUDIO_MODE=tenant .venv/bin/python -c "import tenantmode; print(tenantmode.is_tenant())"
False
```

## Multi-Platform Design (Future)

The architecture for cross-platform publishing is documented in `docs/MULTI_ACCOUNT_ARCHITECTURE.md`:

1. **Private-first publishing**: Never public until approved
2. **Per-account credentials**: Store separately in `~/.config/studio-tenants/`
3. **Idempotency**: Track video IDs to prevent duplicates
4. **Publisher protocol**: Abstract platform behind common interface

## Competitor Research Isolation

Following the session's decision, competitor research is now properly isolated:

- Proposals are tagged `"source": "competitor"` in `news_topics.json`
- `/api/news/queue` refuses competitor topics until status is `competitor_research_approved`
- No download of competitor videos (`metadata_only` / `no_download` enforced)
- Tenant/owner data isolated via `STUDIO_MODE` environment variable

## Resource Constraints

### Free Mode Limits (Currently Active)

| Resource | Daily Cap | Current Usage |
|---|---|---|
| Cloudflare AI Neurons | 10,000 | 2,219.3 |
| OpenRouter Free Models | ~1,000 reqs | Limited by free tier |
| Render Time | CPU-bound | Working |
| Disk Space | 39GB free (96% full) | CRITICAL |

### Paid Mode Requirements (When Ready)

To enable paid models and 25-minute documentaries:

1. Top up OpenRouter balance (currently $-0.0468)
2. Increase `aiart.MAX_PER_VIDEO["doc"]` from 16 to ~110
3. Raise `free_art_cap` or disable free art entirely
4. Expand disk storage or clean outputs

## Recommendations

1. **Approve competitor research gate**: Now implemented and tested (see `test_dashboard_routes.py`)

2. **Address disk space**: Current 96% utilization is a blocking constraint

3. **Prepare for multi-tenant**: When ready, run `deploy/tenant.sh` after:
   - Setting `STUDIO_MODE=tenant`
   - Creating `~/.config/studio-tenants/tenant1/`
   - Adding tenant's OAuth credentials via Settings page

4. **Consider YouTube Reporting API**: Needed for thumbnail analytics (currently not enabled)

## Verdict

**NOT APPLICABLE** - The multi-account infrastructure exists but is not deployed. The system operates as a single-channel studio with free-mode compensation when credits are low. No action required unless owner wishes to add tenants.