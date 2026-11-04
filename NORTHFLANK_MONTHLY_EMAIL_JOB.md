# Northflank Monthly Email Job

Create a Northflank **Cron Job** that uses the same SpendWise repository and production environment variables.

- Command: `python manage.py send_monthly_analysis_emails`
- Schedule: `0 * * * *` (once an hour)
- Concurrency policy: `Forbid`
- Time zone used by SpendWise: `Asia/Kolkata`

The job runs hourly so the admin schedule can control the day and time without editing Northflank again. If Northflank misses the configured hour or day, the next run catches up during that month. Successful recipients are recorded individually so failed recipients can be retried without duplicate emails. The command checks the Auto send setting and sends the previous completed calendar month's report.

Copy the web service's runtime variables to the job, especially `SECRET_KEY`, `DATABASE_URL` or the database variables, and all `SMTP_*` variables. The job fails visibly if SMTP credentials are missing in production. Manage deployments for the job in Northflank.
