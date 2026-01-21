# Changelog
All notable changes to the `finance-bot` project will be documented in this file.

## [1.4.0] - 2026-01-22

### Added
- **Manual Account Linking**: Added `/link <token>` command. This serves as a reliable alternative to deep links for users on devices where standard URL redirection fails.
- **Bifrost Compatibility**: Updated `/upgrade` payload format to support Bifrost 1.4.0 features (Duration and Explicit Roles).

### Changed
- **Performance**: Removed the redundant `sync_subscription_status` check in the `/menu` handler.
  - The bot now relies on **Push-Based Cache Invalidation** (introduced in 1.3.3) and lazy provisioning.
  - The dashboard now loads significantly faster as it no longer waits for an upstream HTTP check on every request.

## [1.3.3] - 2026-01-21

### Changed
- **Auth Architecture**: Implemented **Push-Based Cache Invalidation**.
  - The Finance Service now caches token validation results for 24 hours to maximize performance.
  - Added a new `/internal/webhook/auth-event` endpoint to receive invalidation signals from Bifrost (e.g., on ban or password change).
- **Provisioning**: Switched to **Lazy Provisioning**. The `/sync-session` endpoint has been removed. User profiles are now automatically created in the Finance DB upon the first valid request.

## [1.3.2] - 2026-01-20

### Fixed
- **Auth Architecture**: Fixed the "Shared Secret" vulnerability. The Finance Service no longer attempts to decode Bifrost tokens locally.
- **Web Service**: Updated `/sync-session` to validate tokens by calling `Bifrost` directly, removing the need for `JWT_SECRET_KEY` synchronization between services.

## [1.3.1] - 2026-01-20

### Fixed
- **Web Service**: Resolved critical `ImportError` by restoring missing `create_jwt`, `decode_jwt`, and `auth_required` functions in `web_service/app/utils/auth.py`.

## [1.3.0] - 2026-01-20

### Added
- **Payment Delegation**: Added `/upgrade` command which generates a secure deep link to the central **Bifrost Bot**.
- **Dynamic Pricing**: The upgrade link now dynamically passes the price and client ID to the payment gateway.

### Changed
- **Payment Flow**: Removed legacy direct-payment logic; the bot now acts as a gateway to the central Bifrost ecosystem.

## [1.2.2] - 2026-01-20

### Added
- **Web-to-Telegram Linking**: Added endpoints `/auth/link/initiate-telegram` and `/auth/link/complete-telegram` to support Deep Link binding.
- **Account Management**: Refactored `/auth/link-account` to proxy requests to Bifrost's internal IDP API.
- **Telegram Bot**: Updated Bot's `api_client` and `start` command to handle `link_<token>` payloads.

### Changed
- **Auth Flow**: The linking process now offloads identity merging logic completely to Bifrost.

## [1.2.1] - 2026-01-19

### Added
- **Telegram Bot Onboarding**: Added a "Subscription Tier" selection step at the end of the onboarding flow.
- **Telegram Bot Settings**: Added "Link Email" feature to allow Telegram-only users to set email/password credentials for Web login.
- **Telegram Bot API**: Added `link_credentials` method to `api_client.py`.

## [1.2.0] - 2026-01-19

### Added
- **Finance Service Models**: Updated `User` model in `web_service/app/models.py` to support `email`, `password`, and `subscription_tier`.
- **Finance Service Auth**:
  - Added `POST /auth/register` and `POST /auth/login` for Web Email/Password flow.
  - Added `POST /auth/verify-otp` to allow Telegram users to login to Web using the 6-digit Bot code.
  - Added `POST /auth/link-account` to connect Email to Telegram accounts and vice versa.

### Changed
- **Finance Service Auth**: Updated `sync-session` to return premium status.

## [1.1.0] - 2026-01-16

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

## [1.0.0] - 2026-01-01

### Initial Release
- **Core Features**:
  - **Smart Text Input**: Natural language logging for expenses and income (e.g., "Coffee 2.50", "Salary 500").
  - **Dual Currency Support**: Full support for USD and KHR with live or fixed exchange rates.
  - **Debt Management**: Tracking for "Lent" and "Borrowed" amounts with repayment logging.
  - **Reporting**: Weekly/Monthly analytics, spending habits, and CSV exports.
  - **Reminders**: Custom scheduled notifications via Telegram.
- **Architecture**:
  - **Telegram Bot**: Python-based interface using `python-telegram-bot`.
  - **Web Service**: Flask backend handling logic, database operations, and API endpoints.
  - **Database**: MongoDB for persistent storage of transactions, debts, and user settings.