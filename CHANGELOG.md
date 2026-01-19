# Changelog
All notable changes to the `finance-bot` project will be documented in this file.

## [1.2.0] - 2026-01-19

### Added
- **Finance Service Models**: Updated `User` model in `web_service/app/models.py` to support `email`, `password`, and `subscription_tier`. Added methods for linking accounts (`link_email`, `link_telegram`).
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