# Release Notes: PurpleMerit Smart Checkout (v2.4.0)

## Feature Overview
Introduces a high-performance, single-page checkout experience designed to reduce friction and improve conversion.

## Key Changes
- Replaced multi-step form with a React-based single-page application.
- Integrated new payment gateway (Stripe-Next).
- Added real-time inventory validation.

## Known Risks
- Database load may increase due to real-time validation.
- Initial cache warm-up period required for static assets.
- Potential compatibility issues with legacy browsers (IE11).
- Increased API latency expected in the first 48 hours as edge functions propagate.
