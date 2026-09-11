## Context

See proposal.md for motivation. The org has 4 Go repositories that would benefit
from CodeQL analysis (`complyctl`, `complytime-providers`, `complypack`,
`complytime-collector-components`), plus `complyapi` in the future. Three use
standard single-module layouts where CodeQL autobuild works out of the box. One
(`complytime-collector-components`) has a multi-module workspace with a broken
`go.work` that requires a custom build command.

The existing security pipeline covers dependency SCA (OSV-Scanner), secrets and
misconfig (Trivy), and supply chain posture (Scorecard). SonarCloud provides
opt-in SAST and code quality. No tool currently performs interprocedural
taint-tracking analysis on Go source code.

Constraints from the constitution: reusable workflows use the `reusable_` prefix,
consumer workflows use `ci_` prefix, all action refs are SHA-pinned, permissions
follow least privilege with job-level grants only.

## Goals / Non-Goals

**Goals:**

- Provide a reusable CodeQL workflow generic enough for any Go repo in the org
- Support both autobuild and custom build commands
- Control Go version from the repository, solving the runner version mismatch
- Allow future extension to non-Go languages
- Keep alerts advisory by default

**Non-Goals:**

- Syncing consumer workflows to downstream repos (opt-in model)
- Replacing SonarCloud (complementary tools)
- Running CodeQL on org-infra itself (no Go application code)
- Scheduled analysis runs (event-based only per user decision)

## Decisions

### D1: Adoption model -- opt-in cross-repo call (not synced)

Repos create their own consumer workflow calling
`complytime/org-infra/.github/workflows/reusable_codeql.yml@main`.

**Alternative considered: Synced consumer workflow (like `ci_security.yml`)**

Rejected because: (a) only 3-4 repos need this, making sync overhead
disproportionate (Constitution II: Simplicity & Isolation); (b) one repo
(`complytime-collector-components`) needs a custom `build-command` containing
spaces, which is incompatible with the sync-config `vars` system (regex `\S+`
substitution only supports single-token values); (c) advisory rollout benefits
from deliberate per-repo opt-in rather than automatic distribution.

### D2: Single-language input with caller-side matrix

The workflow accepts one `language` per invocation. Multi-language repos use a
GitHub Actions matrix strategy in their consumer workflow to invoke it once per
language.

**Alternative considered: JSON array `languages` input with internal matrix**

Rejected because: (a) per-language build configuration (Go needs setup-go +
build, Python needs neither) cannot be cleanly parameterized in a single matrix;
(b) failure isolation is worse (one language failing blocks all results); (c)
single-language is idiomatic for reusable workflows and follows the Composability
principle.

### D3: Conditional Go-specific steps

The `setup-go` and build steps use `if: inputs.language == 'go'` conditions.
Non-compiled languages (Python, JavaScript) skip directly from `codeql/init` to
`codeql/analyze`.

**Alternative considered: Separate workflows per language family**

Rejected because: the init/analyze envelope is identical across all languages.
Only the middle (setup + build) differs, and a simple conditional handles this
without workflow proliferation.

### D4: Autobuild as default build mode

When `build-command` is empty (default), the workflow uses
`github/codeql-action/autobuild`. When non-empty, the workflow runs the provided
command in a `run:` step instead.

**Alternative considered: Always require explicit build command**

Rejected because: 3 of 4 target repos work with autobuild out of the box.
Requiring a build command for standard repos violates Convention Over
Configuration.

### D5: `default` query suite as default

The `query-suite` input defaults to `default` (highest precision, lowest false
positive rate).

**Alternative considered: `security-extended` as default**

Rejected because: during initial advisory rollout, minimizing noise is more
important than maximizing coverage. Repos can opt into `security-extended` once
they've triaged initial findings.

### D6: Advisory alerts by default, blocking opt-in

The `fail-on-alert` input defaults to `false`. CodeQL findings appear as Code
Scanning alerts but do not fail the workflow.

**Alternative considered: Blocking by default**

Rejected because: initial adoption would force repos to triage all existing
findings before any PR could merge. Advisory mode allows gradual remediation.

### D7: Contract test without CodeQL execution

The `ci_test_codeql.yml` test workflow validates input handling, step
conditionality, and permissions without running actual CodeQL analysis
(which requires a real codebase and significant runner time).

**Alternative considered: Full integration test with a sample Go project**

Rejected because: org-infra has no Go application code, and maintaining a test
fixture adds complexity. The contract test validates that the workflow structure
is correct; actual CodeQL analysis is validated when downstream repos adopt.

### D8: Step sequence for Go analysis

```
checkout → setup-go → codeql/init → build → codeql/analyze
```

The `setup-go` step MUST run before `codeql/init` so that the correct Go
toolchain is on PATH when CodeQL's tracer initializes. This ordering is critical:
if CodeQL initializes before setup-go, the tracer may bind to the wrong Go
version.

**Alternative considered: setup-go between init and build**

Not viable because CodeQL's init step needs to find the Go compiler at
initialization time to configure the extractor correctly.

## Risks / Trade-offs

**[Risk] Autobuild fails on a repo we assumed would work** --
Mitigation: the `build-command` input provides an escape hatch. Repos can
switch from autobuild to a manual command without changes to the reusable
workflow. Validated that 3/4 current repos pass autobuild via local codebase
inspection.

**[Risk] CodeQL surfaces many findings on initial adoption, creating alert
fatigue** -- Mitigation: `default` query suite minimizes false positives.
Advisory mode means findings don't block PRs. Repos can triage at their own
pace.

**[Risk] SonarCloud and CodeQL report duplicate findings** --
Mitigation: overlap is partial (both flag some common patterns like hardcoded
credentials). Code Scanning deduplicates by tool + rule ID. Developers can
dismiss duplicates. The tools serve different primary purposes (SonarCloud:
quality + coverage gates; CodeQL: taint-tracking SAST).

**[Risk] Action version drift across repos** --
Mitigation: the reusable workflow centralizes action pins in one file. All
consumer repos call the same reusable, so updating the SHA pin in org-infra
propagates to all callers on their next run (they reference `@main`).

**[Trade-off] Not syncing means manual consumer workflow creation** --
Accepted because: 3-4 repos is manageable. The quickstart guide provides
copy-paste templates. Consumer workflows are 5-15 lines each.

### D9: Consumer workflows reference `@main`

Consumer workflows call `reusable_codeql.yml@main`, receiving updates
automatically when the reusable workflow is improved.

**Alternative considered: Tagged release references (`@v1.0.0`)**

Rejected because: (a) the existing SonarCloud pattern also uses `@main` for
cross-repo calls, providing precedent; (b) tagged releases add versioning
overhead for a small consumer set; (c) the advisory-only default means a
regression in the reusable workflow does not break PR merges in downstream repos.

**Mitigation for bad merges**: if a breaking change reaches `main`, downstream
repos can temporarily delete or skip their `ci_codeql.yml` consumer workflow.
Since CodeQL is advisory, no PR merge is blocked during recovery.

### D10: SHA pin maintenance via existing automation

New `codeql-action` SHA pins are covered by the org's existing Dependabot
configuration. Dependabot monitors `github-actions` ecosystem pins in
`.github/workflows/` and creates PRs for new versions. This applies to all
three `codeql-action` subactions (`init`, `autobuild`, `analyze`).

**Alternative considered: Manual quarterly pin bumps**

Rejected because: the org already has automated dependency management
infrastructure. Adding manual tracking for 3 pins would be inconsistent with
existing practice and risk staleness.

## Open Questions

- What is `complyapi`'s Go module structure? It will need assessment when
  populated to determine if autobuild works or a custom build command is needed.
