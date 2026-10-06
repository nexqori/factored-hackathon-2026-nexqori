# Branches, reviews and releases

## Branch roles

| Branch | Purpose |
| --- | --- |
| `main` | Stable, reviewed release line. No direct development. |
| `develop` | Shared integration line before promotion to `main`. |
| `feature/<scope>` | One product capability. |
| `fix/<scope>` | One defect or regression. |
| `docs/<scope>` | Documentation-only changes. |
| `release/<version>` | Optional release stabilization when several changes need coordinated validation. |

`prod`, `test` and `valid` are not additional permanent branches: production is a deployed revision of `main`; tests and validation are CI checks. Creating a branch does not create or deploy an environment. Personal branches `bryan`, `santiago` and `araceli` remain available to the team. Legacy `codex/*` branches are removed only after their commits have been integrated; open PRs are retained.

## Workflow

1. Fetch the latest integration branch and create a short-lived branch, for example `feature/refund-tracking`.
2. Commit one concrete change with a descriptive message: `fix(voice): apply refund-only navigation`.
3. Open a small PR into `develop`; describe the problem, resulting behavior and verification. Urgent fixes to the stable version may target `main` directly.
4. Require passing checks and review before merging. Promote reviewed integration changes through a PR from `develop` to `main`.
5. Delete the merged working branch. Synchronize personal branches by fast-forward when possible; never overwrite unmerged work.

Application CI runs frontend tests/build and backend tests. The intent and security laboratories have separate checks. Secret scanning covers committed history. Automated checks do not replace the customer → administrator → customer demonstration or actual provider testing.

## Versioning and deployment

Use `vMAJOR.MINOR.PATCH` tags for verified releases. Update package/API version metadata consistently before creating a new version tag. Do not move published tags. `v0.2.0` remains a historical release; a branch cleanup is not a new product version.

The current cloud update process uses a reviewed source archive, a private database backup, service health checks and verification that existing records were preserved. This repository's CI does **not** currently deploy AWS automatically. Deployment credentials belong in private server configuration or GitHub Actions secrets, never in the README.

Keep `.env`, access files, provider keys, datasets, private PDFs and backups outside Git. The working state is in [ESTADO.md](../ESTADO.md); developer setup is in [INICIO-EQUIPO.md](../INICIO-EQUIPO.md).
