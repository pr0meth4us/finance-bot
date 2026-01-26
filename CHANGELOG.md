# Changelog

## [0.6.8] - 2026-01-26

### Fixed
- **Auth Service**: Corrected the Bifrost integration in `web_service/app/utils/auth.py`.
  - Switched from the non-existent `/auth/api/me` endpoint to the correct `POST /internal/validate-token` endpoint found in Bifrost source.
  - Implemented `HTTPBasicAuth` using the service's Client Credentials.
  - Updated payload format to send `{"jwt": token}` as expected by Bifrost's `validate_token` route.
  - Added robust response parsing to map Bifrost's `app_specific_role` to the local User model.

## [0.6.7] - 2026-01-26

### Fixed
- **Core Architecture**: Resolved critical decorator inconsistency in the Web Service.
  - Replaced the simple `auth_required` decorator with a **Decorator Factory** in `app/utils/auth.py`.
  - This supports the `@auth_required(min_role="user")` syntax used throughout the application routes.
- **Data Integrity**: Updated `auth_required` to explicitly set `g.account_id`, `g.role`, and `g.email`, fixing `AttributeError` crashes in `transactions`, `debts`, and `settings` endpoints.
- **Consistency**: Renamed internal calls in `auth.py` to match `app/models.py` (`get_by_account_id` instead of `find_by_account_id`, `create` instead of `create_user`).
- **Dependencies**: Added missing exports `service_auth_required` and `invalidate_token_cache` to `app/utils/auth.py` to fix `ImportError` in `auth/routes.py`.
# Changelog

## [0.6.6] - 2026-01-26

### Fixed
- **Web Service Auth**: Completely rewrote `auth_required` in `web_service/app/utils/auth.py`.
  - It now functions as a "Decorator Factory," allowing arguments like `@auth_required(min_role="premium_user")`.
  - Added logic to explicitly set `g.account_id` from the token, fixing `AttributeError` in routes.
  - Implemented the `403 Forbidden` check if a user lacks the required `min_role`.
- **Web Service Debts**: Updated `web_service/app/debts/routes.py` to handle empty JSON bodies gracefully and ensure `g.account_id` is available.

## [0.6.4] - 2026-01-26

### Fixed
- **API Client**: Fixed 7 debt endpoints in `telegram_bot/api_client/debts.py` that were suppressing `401 Unauthorized` errors, preventing the automatic re-login logic from triggering.
  - Fixed: `add_reminder`, `get_all_debts_by_person`, `get_all_settled_debts_by_person`, `get_debt_details`, `cancel_debt`, `update_debt`, `record_lump_sum_repayment`.

## [0.6.3] - 2026-01-26

### Fixed
- **Security**: Removed hardcoded Admin IDs in `handlers/analytics.py` and `handlers/settings.py`. Now uses `ADMIN_USER_ID` environment variable.
- **Auth**: Fixed `ensure_auth` decorator in `api_client/core.py` to gracefully handle 401 errors by clearing the token and returning `None`, preventing handler crashes while ensuring re-login on the next request.
- **API Client**: Updated all API modules (`transactions`, `settings`, `analytics`, `debts`, `auth`) to propagate `401 Unauthorized` exceptions to the `ensure_auth` decorator instead of swallowing them.

## [0.6.2] - 2026-01-23

### Added
- **API Client**: Introduced explicit `BIFROST_TIMEOUT` (60s) in `telegram_bot/api_client/core.py`.

### Changed
- **Reliability**: Standardized all Bifrost API calls (`get_login_code`, `login_to_bifrost`, `sync_subscription_status`, `create_payment_intent`) to use the dedicated 60-second timeout, separating them from the default Web Service timeout.

## [0.6.1] - 2026-01-23

### Added
- **Auth**: Added `/auth/link-command` endpoint to securely generate Telegram linking strings server-side.

## [0.6.0] - 2026-01-23

### Added
- **Bifrost 2.3.3 Support**:
  - The Web Service now extracts `duration` (e.g., '1m') and `expires_at` from `subscription_success` webhooks.
  - **Database**: The `expires_at` timestamp is now stored in the user's `settings` collection to accurately track subscription validity.
- **Profile Sync**: Implemented webhook support for `account_update` events. Changes to `email`, `username`, or `telegram_id` in Bifrost now automatically propagate to the Finance App database.

### Changed
- **Performance**: Refactored `auth_required` to remove per-request identity syncing, significantly reducing database load on high-traffic endpoints.
- **Notifications**: The "Premium Activated" Telegram alert now informs the user of their specific **Plan Duration** and **Expiration Date**.
- **Localization**: Converted date formats and code-like strings in all locale files to use HTML `<code>` tags. This prevents formatting errors when the bot uses `parse_mode='HTML'`.

### Fixed
- **Provisioning**: Fixed logic in `web_service/app/models.py` to ensure `telegram_id` is stored immediately during Lazy Provisioning (initial user creation).
- **Locales**:
  - Added missing Khmer (km) keys for `onboarding.ask_subscription`, `keyboards.plan_free`, and `keyboards.plan_premium`.
  - Added missing Khmer keys for `settings.link_email`.

## [0.5.3] - 2026-01-22

### Changed
- **Bifrost Alignment**:
  - Standardized all premium logic to use `role: "premium_user"` matching Bifrost's `secure-intent` target role.
  - Updated `auth_event_webhook` to parse `subscription_success` and `subscription_expired` payloads exactly as defined in Bifrost docs.
  - Implemented `X-Bifrost-Signature` verification using HMAC-SHA256.

### Added
- **Migration**: Added `migrate_legacy_users.sh` to convert existing `tier: premium` records to `role: premium_user`.

## [0.5.2] - 2026-01-22

### Added
- **Subscription Notifications**: The Web Service now listens for `subscription_success` and `subscription_expired` webhook events from Bifrost.
- **Telegram Push**: Implemented `send_telegram_alert` in the Web Service to push immediate notifications to the Telegram user when their subscription status changes, without waiting for the next bot interaction.

### Changed
- **Webhook Handler**: Refactored `auth_event_webhook` in `web_service/app/auth/routes.py` to look up the user's Telegram ID via `account_id` and trigger notifications accordingly.

## [0.5.1] - 2026-01-22

### Fixed
- **Config Validation**: Added specific check for `BIFROST_CLIENT_ID` being set to the placeholder value "lookup_skipped", which was causing `App lookup_skipped not found` errors in the auth service.
- **Webhook Robustness**: Improved error handling in `web_service/app/auth/routes.py` to prevent `ConnectionResetError` (server crash) if malformed data or empty tokens are received in the `auth-event` webhook.

## [0.5.0] - 2026-01-22

### Added
- **Secure Payment Flow**: Updated `/upgrade` command to use the "Intent-Based" payment system.
- The bot now calls Bifrost's `POST /secure-intent` to register transactions server-side.
- **Pricing Packages**: Added selection menu for **1 Month ($5.00)** and **1 Year ($45.00)** plans.
- **API Client**: Added `api_client.payment` module to handle secure intent creation.

### Security
- Removed client-side link generation to prevent parameter tampering (price manipulation).

## [0.4.0] - 2026-01-22

### Added
- **Manual Account Linking**: Added `/link <token>` command.
  This serves as a reliable alternative to deep links for users on devices where standard URL redirection fails.
- **Bifrost Compatibility**: Updated `/upgrade` payload format to support Bifrost 1.4.0 features (Duration and Explicit Roles).

### Changed
- **Performance**: Removed the redundant `sync_subscription_status` check in the `/menu` handler.
- The bot now relies on **Push-Based Cache Invalidation** (introduced in 0.3.3) and lazy provisioning.
- The dashboard now loads significantly faster as it no longer waits for an upstream HTTP check on every request.

## [0.3.3] - 2026-01-21

### Changed
- **Auth Architecture**: Implemented **Push-Based Cache Invalidation**.
- The Finance Service now caches token validation results for 24 hours to maximize performance.
- Added a new `/internal/webhook/auth-event` endpoint to receive invalidation signals from Bifrost (e.g., on ban or password change).
- **Provisioning**: Switched to **Lazy Provisioning**. The `/sync-session` endpoint has been removed.
  User profiles are now automatically created in the Finance DB upon the first valid request.

## [0.3.2] - 2026-01-20

### Fixed
- **Auth Architecture**: Fixed the "Shared Secret" vulnerability.
  The Finance Service no longer attempts to decode Bifrost tokens locally.
- **Web Service**: Updated `/sync-session` to validate tokens by calling `Bifrost` directly, removing the need for `JWT_SECRET_KEY` synchronization between services.

## [0.3.1] - 2026-01-20

### Fixed
- **Web Service**: Resolved critical `ImportError` by restoring missing `create_jwt`, `decode_jwt`, and `auth_required` functions in `web_service/app/utils/auth.py`.

## [0.3.0] - 2026-01-20

### Added
- **Payment Delegation**: Added `/upgrade` command which generates a secure deep link to the central **Bifrost Bot**.
- **Dynamic Pricing**: The upgrade link now dynamically passes the price and client ID to the payment gateway.

### Changed
- **Payment Flow**: Removed legacy direct-payment logic; the bot now acts as a gateway to the central Bifrost ecosystem.

## [0.2.2] - 2026-01-20

### Added
- **Web-to-Telegram Linking**: Added endpoints `/auth/link/initiate-telegram` and `/auth/link/complete-telegram` to support Deep Link binding.
- **Account Management**: Refactored `/auth/link-account` to proxy requests to Bifrost's internal IDP API.
- **Telegram Bot**: Updated Bot's `api_client` and `start` command to handle `link_<token>` payloads.

### Changed
- **Auth Flow**: The linking process now offloads identity merging logic completely to Bifrost.

## [0.2.1] - 2026-01-19

### Added
- **Telegram Bot Onboarding**: Added a "Subscription Tier" selection step at the end of the onboarding flow.
- **Telegram Bot Settings**: Added "Link Email" feature to allow Telegram-only users to set email/password credentials for Web login.
- **Telegram Bot API**: Added `link_credentials` method to `api_client.py`.

## [0.2.0] - 2026-01-19

### Added
- **Finance Service Models**: Updated `User` model in `web_service/app/models.py` to support `email`, `password`, and `subscription_tier`.
- **Finance Service Auth**:
  - Added `POST /auth/register` and `POST /auth/login` for Web Email/Password flow.
  - Added `POST /auth/verify-otp` to allow Telegram users to login to Web using the 6-digit Bot code.
  - Added `POST /auth/link-account` to connect Email to Telegram accounts and vice versa.

### Changed
- **Finance Service Auth**: Updated `sync-session` to return premium status.

## [0.1.0] - 2026-01-16

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

## [0.0.1] - 2026-01-01

### Added
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