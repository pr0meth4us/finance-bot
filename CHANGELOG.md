# Changelog
All notable changes to the `finance-bot` project will be documented in this file.

## [Unreleased] - 2026-01-16

### Added
- **Finance Service Models**: Created `web_service/app/models.py` containing the `User` class to handle `account_id` mapping and local profile provisioning, as well as centralized category constants.
- **Finance Service Auth**: Added `POST /auth/sync-session` in `web_service/app/auth/routes.py` to allow the Telegram Bot to sync verified Bifrost sessions with the Finance Backend.

### Changed
- **Finance Service Auth**: Refactored `web_service/app/auth/routes.py` to remove legacy proxy endpoints (`proxy_request_otp`, `proxy_verify_otp`) in favor of direct Bifrost usage by clients.
- **Finance Service Users**: Updated `web_service/app/users/routes.py` to use the new `User` model for finding/creating profiles, reducing code duplication.
- **Infrastructure**: Added `bifrost` service to `docker-compose.yml`. Updated `web` and `telegram` services to communicate with Bifrost.
- **Auth (Telegram Bot)**: 
  - Updated `telegram_bot/api_client.py` to include `sync_session` method.
  - Updated `telegram_bot/decorators.py` to call `sync_session` after successful login.