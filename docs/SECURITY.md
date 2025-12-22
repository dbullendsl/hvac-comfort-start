# Security Policy

## Supported Versions

This repository currently publishes **Beta** releases. Beta releases may change behavior and are intended for technically competent users.

- Supported: **Beta 9** (baseline checkpoint)
- Future supported versions will be documented in `CHANGELOG.md`

## Reporting a Vulnerability

If you believe you have found a security issue:

1. **Do not open a public GitHub issue** with sensitive details.
2. Report privately by contacting the repository owner through GitHub.

Include:
- What you observed
- Steps to reproduce (without secrets)
- Home Assistant / Pyscript versions
- Relevant logs (redacted)

## Sensitive Data Guidance

Do not share:
- API tokens
- passwords
- IP addresses that are not already public
- internal hostnames/domains
- Home Assistant `.storage` contents
- `.secrets.yaml`

If you must share logs, redact sensitive information first.

## Scope

This project controls HVAC behavior through Home Assistant automation and Pyscript. It does not implement network services and does not intentionally store secrets. However, Home Assistant environments frequently contain sensitive configuration data, so care should be taken when sharing logs or configuration fragments.

