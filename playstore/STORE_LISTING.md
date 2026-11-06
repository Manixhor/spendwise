# Spendwise Play Store draft

**App name:** Spendwise

**Short description:** Track expenses, budgets, savings goals, and monthly money insights.

**Full description:**

Spendwise helps you see where your money goes. Record expenses and income, organize transactions by category, set savings goals, and review your progress each month.

Features include quick expense entry, recurring payment reminders, monthly analysis, CSV and spreadsheet imports, exports, and simple spending insights. Sign in to keep your information with your account and use it across devices.

Spendwise is a personal tracking tool. It does not connect to your bank, move money, or provide financial advice. An internet connection is needed for account features. Push notifications are not supported in the current Android app.

**Category:** Finance

**Privacy policy:** `https://site--spendwise--m9lhjm5ftxzt.code.run/privacy/` after deployment and verification.

**Privacy contact:** `manigururam06@gmail.com`

**Account deletion:** `https://site--spendwise--m9lhjm5ftxzt.code.run/account/delete/` after deployment and verification.

**Reviewer access:** Create a dedicated demo account with non-sensitive sample data and provide its login in Play Console's App access section. Do not place credentials in this repository.

**Graphics:** `icon-512.png` and `feature-graphic-1024x500.png`. Capture real Android phone screenshots after installing and testing the final APK.

## Data safety review before Console submission

- Account name, email, optional avatar, financial entries, account settings, and device push subscription details are stored to provide the service.
- Page view counts and security attempt data are stored for operation and abuse prevention.
- Hosting and email providers process service data. If AI motivation is enabled in production, saved and spent totals are sent to OpenAI. Verify the production configuration before answering the Play form.
- Financial import files are parsed by the server; verify whether source files are retained in production.
- Confirm actual encryption, retention, backup deletion, and provider sharing practices before making final Data safety declarations.

## Release gate

1. Verify the live privacy page displays `manigururam06@gmail.com`.
2. Complete the external security actions in `SECURITY_REMEDIATION.md`.
3. Test the installed Android app and capture real screenshots.
4. Complete Play Console app content, Data safety, content rating, target audience, and reviewer access.
5. Run the required closed test if the developer account is subject to it.
6. Keep the production Play submission on hold until separately requested.
