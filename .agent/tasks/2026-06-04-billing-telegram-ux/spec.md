# Billing And Telegram UX Launch Scope

Date: 2026-06-04

## Goal

Prepare AI Poisk for paid Telegram-first use with editable packages, non-expiring balances, honest result-based billing, clearer onboarding, customer cabinet, manual payment path, and an admin surface for tariff and balance management.

## Product Decisions

- Packages are separate for supplier reports and procurement-document analysis.
- No combined packages in this phase.
- Package names, unit counts, prices, descriptions, active state, and display order are editable in the admin panel.
- Purchased units do not expire.
- A job reserves the required units before launch.
- Units are charged only after the result is successfully delivered to the customer in Telegram.
- Failed jobs release the reservation and do not charge the customer.
- Supplier reports with fewer verified suppliers than the internal target are held for customer confirmation.
- If the customer accepts a partial supplier report, the bot sends the file and charges the reserved units after successful delivery.
- If the customer rejects or does not answer within 24 hours, the report is not delivered and the reservation is released.
- Contacts and manual payment instructions are admin-editable because the real email, Telegram username, and payment text were not provided yet.

## Acceptance Criteria

- Backend stores tariff packages and a billing ledger with grants, reserves, charges, and releases.
- Client balances expose available, reserved, granted, and spent units for both commercial functions.
- Access checks use non-expiring balance while preserving legacy monthly-limit customers through a one-time balance initialization path.
- Telegram `/start` explains how to use the bot with clear formatting and buttons.
- Telegram main menu includes create report, cabinet, tariffs/payment, help, contacts, and Telegram ID.
- Customer cabinet shows available/reserved/spent units and warns when a balance is low.
- Tariffs/payment screen shows active packages grouped by function and manual contact instructions.
- Partial supplier reports wait for inline customer confirmation before delivery and charge.
- Admin UI lets the owner manage tariffs and manually grant package units to clients.
- Tests cover billing ledger behavior, access checks, partial confirmation text, and public API payloads.
- Fresh backend tests and frontend build pass.
