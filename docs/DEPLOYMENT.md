# Deployment and Operations Guide

This document summarizes the recommended steps for shipping the estimate automation platform as a publicly accessible application.

## 1. Packaging and Release

1. Update the version in `pyproject.toml` and `estimate_automation/__init__.py`.
2. Build the distribution:
   ```bash
   python -m build
   ```
3. Publish to PyPI or your private index:
   ```bash
   twine upload dist/*
   ```
4. Container images can be created with:
   ```bash
   docker build -t registry.example.com/estimate-automation:$(git rev-parse --short HEAD) .
   ```

## 2. Environment Configuration

| Variable | Description |
| --- | --- |
| `ESTIMATE_AUTOMATION_API_KEY` | Optional API key to enforce for all requests. |
| `ESTIMATE_AUTOMATION_CORS_ORIGINS` | Comma-separated origins for browser clients. |
| `ESTIMATE_AUTOMATION_DEFAULT_TAX_RATE` | Default tax rate for the Web UI. |
| `ESTIMATE_AUTOMATION_LOG_LEVEL` | Logging verbosity (`INFO`, `DEBUG`, ...). |

## 3. Infrastructure Hardening

- Terminate TLS at the load balancer and forward traffic to the FastAPI app via HTTPS.
- Configure reverse proxies (NGINX, CloudFront, etc.) to restrict upload size (recommended: 10 MB).
- Enable WAF/IPS rules to block suspicious multipart payloads.
- Run the container with a non-root user and read-only filesystem except for `/tmp`.

## 4. Monitoring & Alerting

- Health check: `GET /healthz` (expect `{"status": "ok"}` and HTTP 200).
- Emit access logs via your ingress or add a logging handler that exports JSON to Cloud Logging / ELK.
- Track key metrics: number of generated estimates, validation failures (HTTP 400), authentication failures (HTTP 401).
- Set alerts for repeated `401` events (potential attack) and spikes in `500` errors.

## 5. Backup & Data Policy

- The application processes files in memory only; no persistent storage is required. If audit logging is mandated, store hashed filenames only.
- Keep API keys and secrets in a managed vault (AWS Secrets Manager, GCP Secret Manager, etc.). Rotate keys regularly.

## 6. Incident Response

- Enable structured logging (`ESTIMATE_AUTOMATION_LOG_LEVEL=INFO`).
- Run the bundled WSGI server (`estimate-automation-web`) behind a reverse proxy with `ProxyPreserveHost On` (Apache) or `proxy_set_header Host $host` (NGINX) to capture client IPs.
- Document runbooks for handling 400/500 errors, expired certificates, and dependency vulnerabilities.

## 7. Continuous Delivery Pipeline

1. Run `pip install -e .[cli]` to install optional CLI extras if required.
2. Execute the automated tests:
   ```bash
   pytest
   ```
3. Build the front-end smoke test by launching `estimate-automation-web` and requesting `/healthz`.
4. Publish artifacts (wheels, container images) and deploy to staging, then production after approval.

Maintaining these operational safeguards ensures the application is production-ready and secure for public use.
