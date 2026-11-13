# Memoraa Attendance & Payroll System

Professional employee attendance, regularization, holiday management and salary slip system built for **Memoraa Photography Studio**.

**Theme:** Yellow (#FFD700) + Black  
**Stack:** Python Flask • SQLite • ReportLab (PDF) • Bootstrap 5 • Geolocation API

---

## Features

- **Admin Login** (Mobile: `9324029311` / Password: `Ajay@9311`)
- Admin can create Employees / Managers, assign managers, set monthly salary structure
- **Punch In / Punch Out** with live browser Geolocation (lat/long saved)
- **Custom Holidays** – Managers & Admin can add company holidays
- **Regularization** – Employee requests missed punches → Manager approves/rejects → Attendance auto-updated
- **Salary Calculation** based on present days (complete punch-in + punch-out)
  - Working days = Total days − Sundays − Holidays
  - Daily rate = Monthly Salary / Working Days
  - Earned = Daily rate × Present days
- **PDF Salary Slips** – Beautiful branded slips downloadable anytime
- Role-based access (Admin / Manager / Employee)
- Responsive Yellow & Black photography-themed UI

---

## Quick Start (Local)

```bash
# 1. Clone / enter folder
cd memoraa_attendance

# 2. Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run
python app.py
```

Open: http://127.0.0.1:5000

**Default Admin Login**
- Mobile: `9324029311`
- Password: `Ajay@9311`

---

## Deploy Live (GitHub + Render)

### 1. Push to GitHub
```bash
git init
git add .
git commit -m "Memoraa Attendance System"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/memoraa-attendance.git
git push -u origin main
```

### 2. Deploy on Render.com (Free tier)
1. Go to [render.com](https://render.com) → New → Web Service
2. Connect your GitHub repo
3. Settings:
   - **Runtime**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app --bind 0.0.0.0:$PORT`
4. Add Environment Variable (optional but recommended):
   - `SECRET_KEY` = any long random string
5. Create Web Service → Wait for deploy

Your app will be live at: `https://your-app-name.onrender.com`

> Note: Free tier sleeps after inactivity. First request after sleep may take 30-60s. SQLite works for small teams; for production consider PostgreSQL.

### Alternative: Railway / PythonAnywhere / VPS
Any platform that supports Flask + persistent disk works.

---

## Project Structure

```
memoraa_attendance/
├── app.py              # Main application & routes
├── models.py           # Database models
├── config.py           # Configuration
├── requirements.txt
├── README.md
├── templates/          # Jinja2 HTML templates
└── static/             # (CSS/JS if needed)
```

---

## How Salary Works

1. Admin sets **Monthly Salary** when creating/editing employee.
2. System calculates expected working days in the month (excludes Sundays + Holidays).
3. Only days with **both Punch In + Punch Out** (or approved regularization) count as present.
4. Employee downloads PDF salary slip for any recent month from the Salary page.

---

## Security Notes

- Change the default admin password after first login (edit employee).
- Set a strong `SECRET_KEY` in production.
- For production, switch to PostgreSQL and enable HTTPS.

---

Built with ❤️ for Memoraa Photography Studio  
Capturing Moments, Creating Memories
