# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed
- Simplified analysis setup to Ollama only; removed OpenAI controls, credentials, SDK dependencies and runtime selection. Legacy OpenAI settings are removed on save.

### Added
- Provider-neutral SMTP settings with sender, recipient, username, port, verified SSL/TLS or STARTTLS, optional relay authentication, and a no-email connection test.
- English/Swedish interface switch with an independently saved default language.
- News history selection counts, select/clear-all controls, and confirmed deletion of the entire archive.
- Markdown files `README.md`, `CONTRIBUTING.md`, `CODE_OF_CONDIFCT.md`.
- Setup project configuration.
