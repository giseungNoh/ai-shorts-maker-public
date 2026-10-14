# Security / Public Repository Policy

This repository is a sanitized portfolio edition.

The original development repository remains private. This public repository intentionally excludes:

- API keys, cookies, session tokens, OAuth material
- personal voice samples and user-specific data
- runtime logs and local machine paths
- browser-session automation and authentication-related implementation
- historical commits from the private repository

Secrets must be provided only through local environment variables or ignored configuration files.
