# WallStBots — Full-Stack Feature Audit
**Date:** May 28, 2026  
**Legend:** ✅ Built | ⚠️ Partial | ❌ Not Built

---

## 1. Account Registration, Authentication, & Security

| Feature | Status | Notes |
|---|---|---|
| Standard Signup Form | ✅ Built | Email + password signup in auth.js, backend `/auth/signup` endpoint wired |
| Email Verification Workflow | ⚠️ Partial | Backend sends confirmation email on signup; no "Resend verification" button, no landing page redirect logic in frontend |
| Standard Credentials Login | ✅ Built | Email/password → JWT (access + refresh tokens), stored in localStorage |
| Social OAuth 2.0 (Google, GitHub, Apple) | ❌ Not Built | No OAuth login buttons or strategies anywhere |
| Multi-Factor Authentication (MFA/2FA) | ❌ Not Built | No TOTP, QR code, or backup code system |
| Active Session & Device History | ❌ Not Built | No session management UI; tokens stored but no visibility/revoke control |
| Password Recovery & Reset | ⚠️ Partial | Backend likely has endpoint; no "Forgot password" link visible in login.html |
| Enterprise SSO (SAML / OIDC) | ❌ Not Built | Not applicable for current scale |

---

## 2. User Profile & Account Management

| Feature | Status | Notes |
|---|---|---|
| Avatar & Profile Photo Upload | ❌ Not Built | No profile picture UI anywhere |
| Notification Preferences Matrix | ❌ Not Built | No in-app or email notification settings UI |
| Internationalization (i18n / l10n) | ❌ Not Built | English-only; no locale/timezone/currency selector |
| GDPR / CCPA Privacy Center (Data Export, Account Deletion) | ❌ Not Built | No self-service data export or delete account flow |

---

## 3. Member Dashboard & Data Visualization

| Feature | Status | Notes |
|---|---|---|
| KPI Metric Cards | ✅ Built | Portfolio value, day P&L, total P&L, % change cards on fund pages |
| Multi-Axis Interactive Charts | ⚠️ Partial | Chart.js race/performance chart exists; no hover tooltips, no pie/donut chart, limited responsiveness |
| Relational Dynamic Data Tables | ⚠️ Partial | Signals table with filter tabs (BUY/SELL/HOLD) exists; no column sorting, no pagination, no column visibility toggles |
| Date-Range Controllers | ❌ Not Built | No date range picker; charts show all-time data only |
| Single-Click Data Exporters (CSV / Excel / PDF) | ❌ Not Built | No export functionality anywhere |

---

## 4. Content & Asset Management (CRUD)

| Feature | Status | Notes |
|---|---|---|
| Universal Global Search | ⚠️ Partial | Stock/ticker search exists on portfolio page (`/stocks/search` API); not a global sticky top-bar search |
| Rich Text Editor | ❌ Not Built | No WYSIWYG or markdown editor |
| Media Vault / File Uploader | ❌ Not Built | No drag-and-drop file upload UI |
| Mass Batch Processing Utilities | ❌ Not Built | No multi-select, bulk actions, or batch queue |

---

## 5. Billing, Subscriptions, & Commerce

| Feature | Status | Notes |
|---|---|---|
| Tier Selection Pricing Cards | ✅ Built | MEMBER ($49.99/mo), INSIDER ($69.99/mo), SYNDICATE ($99.99/mo) pricing page with monthly/annual toggle |
| Gateway Checkout Integration | ⚠️ Partial | PayPal subscriptions form wired; no Stripe/Braintree; no PCI-compliant card element |
| Self-Service Subscription Lifecycle | ⚠️ Partial | Free signup and referral code validation exist; no upgrade/downgrade/cancel UI |
| Billing Vault & Payment Profiles | ❌ Not Built | No saved payment method display or update form |
| Automated PDF Invoice Generator | ❌ Not Built | No invoice history or downloadable receipts |

---

## 6. Communications & Social Interactions

| Feature | Status | Notes |
|---|---|---|
| Direct & Group Messaging | ❌ Not Built | No chat/messaging system |
| Unread Notification Hub | ❌ Not Built | No bell icon, notification panel, or badge counter |
| Threaded Comment Modules | ❌ Not Built | No comment sections on any page |
| Rich Text @Mention System | ❌ Not Built | Not applicable without messaging/comments |
| Shareable Link Builder | ❌ Not Built | No "generate shareable link" feature (referral codes exist but are different) |

---

## 7. Audit Logs & System Utilities

| Feature | Status | Notes |
|---|---|---|
| Personal User Activity Feed | ❌ Not Built | No login history or user event log |
| Help Desk Ticket Creation | ❌ Not Built | No support form in-app (FAQ/chatbot exists but no ticket submission) |
| Interactive Onboarding Walkthrough | ❌ Not Built | No guided tour or tooltip overlay for new users |
| Global Maintenance Broadcast Panel | ❌ Not Built | No banner/alert system for maintenance notices |

---

## Summary

| Section | ✅ Built | ⚠️ Partial | ❌ Not Built |
|---|---|---|---|
| 1. Auth & Security | 2 | 2 | 4 |
| 2. User Profile | 0 | 0 | 4 |
| 3. Dashboard & Data Viz | 1 | 2 | 2 |
| 4. Content & CRUD | 0 | 1 | 3 |
| 5. Billing | 1 | 2 | 2 |
| 6. Communications & Social | 0 | 0 | 5 |
| 7. Audit & Utilities | 0 | 0 | 4 |
| **TOTAL** | **4** | **7** | **24** |

---

**What's solid today:** Auth (login/signup/JWT), pricing tiers, KPI cards, fund performance charts, signals table with filtering, PayPal checkout, stock search.

**Biggest gaps to close for a production-ready SaaS:** Password reset flow, notification preferences, Stripe integration with subscription lifecycle, CSV/Excel export, and a maintenance banner system.
