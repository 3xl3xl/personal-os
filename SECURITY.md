# Security Policy

Personal OS is designed to keep personal data safe and portable across sessions, tools, and AI clients. This document defines the baseline security rules for the project.

## Repository scope vs. private runtime data

- This Git repository holds only: code, schema/field definitions, policies, and documentation.
- Private runtime data — personal facts, financial data (balances, income, expenses), goals (financial and life targets), location/jurisdiction, transactions, and account data — belongs exclusively to a private runtime data store outside version control.
- Actual personal data must never be committed to this repository, even though it is private. Specifications and documentation describe the *shape* of this data (field names, structures) — never the actual values.

## Secrets

- Secrets (API keys, OAuth tokens, passwords, private keys) must never be committed to this repository.
- Credentials must be provided via environment variables or a secure secret store (e.g. OS keychain, a dedicated secrets manager) — never hardcoded or checked into version control.

## Personal & financial data

- Personal financial data (bank account details, card numbers, transaction history, balances) must never be committed to this repository.
- Any local storage of personal data must live outside version control (see `.gitignore`).

## Access control

- Principle of least privilege: any component, integration, or AI client is granted only the access it needs to do its job — nothing more.
- Read, write, and financial-action permissions must be kept separate and must never be bundled into a single undifferentiated permission.
- Financial execution (any action that moves money or executes a financial transaction) is **blocked by default** and requires explicit, separate authorization to enable.

## Incident response

- If a secret is accidentally committed — even if later removed from history — treat the credential as compromised and rotate it immediately.
- Document any accidental exposure before continuing development.
