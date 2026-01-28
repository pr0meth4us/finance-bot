# Changelog

## [0.6.15] - 2026-01-28

### Refactored
- **Authentication Architecture**: Transitioned `web_service` to a "Pure Bifrost" model.
- **Routes**: Updated `auth/routes.py` to **proxy** `/login` and `/verify-otp` requests directly to Bifrost API, removing local token generation.
- **Utils**: Cleaned up `utils/auth.py` to remove `create_jwt` and enforce strict Bifrost token validation.
- **Lazy Provisioning**: The `auth_required` decorator now automatically creates/syncs a local `User` record when a valid Bifrost token is presented.

## [0.6.14] - 2026-01-28

### Refactored
- **Backend Auth**: Completely replaced `web_service/app/utils/auth.py` with a robust Bifrost-integrated version.
- **Compatibility**: Added alias wrappers (`login_required`, `role_required`) to the new `auth_required` core to maintain backward compatibility with existing routes.
- **Security**: Implemented real-time token validation against Bifrost Internal API using Basic Auth.

## [0.6.13] - 2026-01-28

### Fixed
- **Role Standardization**: Conducted a complete overhaul of role verification logic to strictly enforce `'premium_user'`.
- **Legacy Removal**: Deprecated and removed all code that accepted `'premium'` as an alias for premium users.
- **Backend Auth**: Updated `web_service/app/utils/auth.py` to perform strict equality checks on user roles, rejecting any ambiguous role names.
- **Bot Commands**: Updated `/upgrade` and `/menu` handlers to strictly validate against `'premium_user'`.

## [0.6.12] - 2026-01-28

### Fixed
- **Profile Loading**: Fixed a critical issue where the bot failed to load user settings (Name, Role, Currency Preferences) during a "cold start" (when a cached JWT existed but memory was empty).
- **Premium Access**: Resolved the bug where premium users were incorrectly blocked from features because their role defaulted to 'user' instead of 'premium_user'.
- **Decorator Logic**: Updated `authenticate_user` in `telegram_bot/decorators.py` to explicitly fetch and cache the user profile from the API if it is missing from `context.user_data`.

## [0.6.11] - 2026-01-27

### Fixed
- **Bot Crash**: Resolved `AttributeError: module 'api_client' has no attribute 'get_cached_token'` which was causing the bot to crash on every interaction.
- **Stability**: Fixed the crash loop that resulted in `telegram.error.Conflict` errors due to rapid container restarts.
- **API Client**: Added `get_cached_token` to `telegram_bot/api_client/core.py` and exported it in `__init__.py`.

## [0.6.10] - 2026-01-26

### Fixed
- **Auth Integration**: Updated `web_service/app/utils/auth.py` to match the actual Bifrost Internal API.
- Endpoint: Changed from `/auth/api/verify` (404) to `POST /internal/validate-token`.
  - Auth Method: Switched from Bearer Token to **Basic Auth** (Client ID/Secret).
  - Payload: Sending `{"jwt": token}` in the body instead of query params.
- **Bot Stability**: Hardened `telegram_bot/decorators.py` to gracefully handle `PremiumFeatureException`.
  - Instead of crashing or trying to edit the message (which fails if content is identical), it now shows a **native Telegram alert** (popup).
  - Added specific handling for `MessageNotModified` to prevent log spam and crashes when the UI state is already correct.

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