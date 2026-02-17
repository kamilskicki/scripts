# Security Policy

## Supported versions

Security fixes are provided for the latest `master/main` branch.

## Reporting a vulnerability

Please do not open a public issue for security-sensitive findings.

Report privately via GitHub Security Advisories:

1. Open the repository
2. Go to `Security` tab
3. Click `Report a vulnerability`
4. Include reproduction steps, affected scripts, and impact

## Secrets handling

- never commit webhook URLs or bot tokens
- use environment variables (`YouTube/.env.example`)
- rotate leaked tokens immediately
