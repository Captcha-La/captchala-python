# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [1.0.1] - 2026-11-27

### Changed
- README in Japanese, Korean, Spanish, Portuguese (BR) and German, with a language switcher in every README.
- Build: the version is set only in `src/captchala/_version.py`. No runtime changes.

## [1.0.0] - 2026-11-26

### Added
- `Client` (sync, standard library only) and `AsyncClient` (asyncio, httpx via
  the `async` extra) with `validate()`, `issue_server_token()`,
  `moderation_check()` and `moderation_text()`. Default base URL
  `https://verify.captcha.la`.
- `validate()` options: `client_ip`, `keep_token`, `expected_action`,
  `expected_hostname` (string or list), and the identity fields `bind_uid`,
  `bind_account`, `bind_email`, `bind_phone`, `scene`.
- `ValidateResult` exposes `hostname`, `challenge_ts`, `risk_level`,
  `risk_labels`, `captcha_args`, `binding`, `binding_match` /
  `binding_mismatch`, `test`, degraded-token fields and `raise_if_invalid()`.
- `issue_server_token()` options: `bind_ip`, `ttl`, `max_uses`, `bind_uid`,
  `bind_account`, `bind_email`, `bind_phone`, `scene`, `bind_device_id`,
  `bind_fingerprint`.
- `offline_` tokens are verified against the backup service; client-only
  tokens (`client_` / `co_`) are accepted only when the API and the backup
  service are both unreachable, with cached, single-flight probes and a
  `reject_client_only` option.
- Retries with exponential backoff and jitter, per-attempt timeouts.
- Typed errors: `CaptchaLaError`, `ConfigurationError`, `NetworkError`,
  `RequestTimeoutError`, `APIError`, `AuthenticationError`, `RateLimitError`,
  `InvalidResponseError`, `ValidationFailedError`.
- `user_message()` for user-safe error text, `client_ip_from_headers()`.
- Django helpers (`captchala.contrib.django`): `CaptchaLaField`,
  `CaptchaLaFormMixin`, `captchala_required`, `verify_request`.
- Flask extension (`captchala.contrib.flask`): `CaptchaLa` with `required()`
  and `verify()`.
- Type hints throughout (`py.typed`).
