# Security Policy

## Supported Versions

This project is pre-1.0; expect frequent changes. Report security issues against the latest `main`.

## Reporting a Vulnerability

Please open a private issue or email the maintainer (see repository profile) with:
- Description of the issue
- Steps to reproduce
- Potential impact / scope
- Suggested remediation if known

Do NOT create public PoC repositories without coordinated disclosure.

## Plugin Execution Risks

Git-Sim loads third-party plugins via Python entry points:
- Plugins run arbitrary Python code in your environment.
- Malicious plugins could read files, exfiltrate data, or alter git repositories.

### Mitigations
- Review plugin source before installation.
- Pin plugin versions.
- Prefer virtual environments.
- Consider running in an isolated container for untrusted plugins.

### Hook Override Behavior
`HookPlugin.override_simulation` can entirely bypass built-in safety checks. A malicious override could:
- Fabricate misleading `SimulationResult` objects.
- Conceal dangerous operations.

Always verify unexpected output by running native git commands manually.

## Dependency Updates

Report outdated vulnerable dependencies (dulwich, rich, textual, typer) via issues. Automated tools (Dependabot, Renovate) may be enabled later.

## Secure Development Recommendations
- Enable `mypy --strict` and `ruff` in CI.
- Keep dependencies minimal.
- Avoid executing shell commands in plugins unless necessary.

## Incident Response
If a vulnerability is confirmed:
1. Acknowledge receipt within 72h.
2. Provide fix or mitigation ETA.
3. Publish advisory once patched.

Thank you for helping keep Git-Sim secure.