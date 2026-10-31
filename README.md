# BASRA INTERNATIONAL ACADEMY — Attendance Management System

Flask website for student attendance, admin/teacher accounts, classes, class periods, and attendance reports.

## Features
- Admin and Teacher/User login
- Student register (Admin only)
- User account creation (Admin only)
- Timetable and automatic detection of the currently active period
- Attendance statuses: Present, Absent, Late, Excused
- Daily attendance report
- PostgreSQL on Render; SQLite fallback for local testing
- Somalia timezone (`Africa/Mogadishu`)

## Run locally (Windows)
1. Install Python 3.11 or newer.
2. Extract this ZIP and open PowerShell in the extracted folder.
3. Run:
   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   $env:ADMIN_USERNAME="admin"
   $env:ADMIN_PASSWORD="Set-A-Strong-Password-Here"
   $env:SECRET_KEY="Replace-With-A-Long-Random-Secret"
   python app.py
   ```
4. Open `http://127.0.0.1:5000`.

If you do not set `ADMIN_PASSWORD` during local testing, the starter creates `admin` with password `ChangeMe123!`. Change this immediately; do not use that default online.

## Deploy to Render
1. Create a private GitHub repository and upload the extracted project files.
2. In Render, choose **New + → Blueprint**, connect the repository, and let Render read `render.yaml`.
3. When asked for `ADMIN_PASSWORD`, enter a strong unique password. Keep it private.
4. Create the web service and PostgreSQL database. Wait for deployment to finish.
5. Open the Render-provided website URL and sign in with the configured admin username/password.

## Important
- The first admin account is created from `ADMIN_USERNAME` and `ADMIN_PASSWORD` when the app starts for the first time.
- If you change the environment password after the admin account already exists, it does not automatically change the stored account password. Change it through a dedicated password-management feature before using this for real school data.
- This is a starter version. Before production use with real student records, add CSRF protection, password change/reset, audit logs, backups, and teacher-to-class permissions. Do not share passwords in chat.
- The initial version lets signed-in teachers mark attendance for students in a selected class. Restrict teacher access by assigned class before using with sensitive live records.
