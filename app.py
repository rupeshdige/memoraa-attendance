from flask import Flask, render_template, redirect, url_for, flash, request, jsonify, send_file, session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from datetime import datetime, date, timedelta
from io import BytesIO
import calendar
import os

from config import Config
from models import db, User, Attendance, Holiday, RegularizationRequest
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.units import inch, mm
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'warning'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


def init_db():
    with app.app_context():
        db.create_all()
        # Create default admin if not exists
        admin = User.query.filter_by(mobile='9324029311').first()
        if not admin:
            admin = User(
                emp_id='ADMIN001',
                name='Ajay (Owner)',
                mobile='9324029311',
                role='admin',
                monthly_salary=0.0
            )
            admin.set_password('Ajay@9311')
            db.session.add(admin)
            db.session.commit()
            print("Default admin created: 9324029311 / Ajay@9311")


# ---------- Auth Routes ----------
@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        mobile = request.form.get('mobile', '').strip()
        password = request.form.get('password', '')
        user = User.query.filter_by(mobile=mobile, is_active=True).first()
        if user and user.check_password(password):
            login_user(user, remember=True)
            flash(f'Welcome back, {user.name}!', 'success')
            return redirect(url_for('dashboard'))
        flash('Invalid mobile number or password.', 'danger')
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))


# ---------- Dashboard ----------
@app.route('/dashboard')
@login_required
def dashboard():
    today = date.today()
    attendance_today = Attendance.query.filter_by(user_id=current_user.id, date=today).first()
    
    # Stats for employee
    month_start = today.replace(day=1)
    present_days = Attendance.query.filter(
        Attendance.user_id == current_user.id,
        Attendance.date >= month_start,
        Attendance.date <= today,
        Attendance.punch_in_time.isnot(None),
        Attendance.punch_out_time.isnot(None)
    ).count()
    
    pending_regs = RegularizationRequest.query.filter_by(user_id=current_user.id, status='pending').count()
    
    # For managers/admins
    team_pending = 0
    if current_user.is_manager():
        if current_user.is_admin():
            team_pending = RegularizationRequest.query.filter_by(status='pending').count()
        else:
            team_ids = [m.id for m in User.query.filter_by(manager_id=current_user.id).all()]
            team_pending = RegularizationRequest.query.filter(
                RegularizationRequest.user_id.in_(team_ids),
                RegularizationRequest.status == 'pending'
            ).count()
    
    holidays = Holiday.query.filter(Holiday.date >= today).order_by(Holiday.date).limit(5).all()
    
    return render_template('dashboard.html',
                           attendance_today=attendance_today,
                           present_days=present_days,
                           pending_regs=pending_regs,
                           team_pending=team_pending,
                           holidays=holidays,
                           today=today)


# ---------- Punch In / Out ----------
@app.route('/punch', methods=['GET', 'POST'])
@login_required
def punch():
    today = date.today()
    attendance = Attendance.query.filter_by(user_id=current_user.id, date=today).first()
    
    if request.method == 'POST':
        action = request.form.get('action')
        lat = request.form.get('lat')
        lng = request.form.get('lng')
        
        try:
            lat = float(lat) if lat else None
            lng = float(lng) if lng else None
        except:
            lat, lng = None, None
        
        now = datetime.now()
        
        if action == 'punch_in':
            if attendance and attendance.punch_in_time:
                flash('You have already punched in today.', 'warning')
            else:
                if not attendance:
                    attendance = Attendance(user_id=current_user.id, date=today)
                    db.session.add(attendance)
                attendance.punch_in_time = now
                attendance.punch_in_lat = lat
                attendance.punch_in_lng = lng
                attendance.status = 'present'
                db.session.commit()
                flash(f'Punched IN successfully at {now.strftime("%H:%M:%S")}', 'success')
        
        elif action == 'punch_out':
            if not attendance or not attendance.punch_in_time:
                flash('Please punch in first.', 'warning')
            elif attendance.punch_out_time:
                flash('You have already punched out today.', 'warning')
            else:
                attendance.punch_out_time = now
                attendance.punch_out_lat = lat
                attendance.punch_out_lng = lng
                db.session.commit()
                flash(f'Punched OUT successfully at {now.strftime("%H:%M:%S")}. Hours: {attendance.working_hours()}', 'success')
        
        return redirect(url_for('punch'))
    
    return render_template('punch.html', attendance=attendance, today=today)


# ---------- Regularization ----------
@app.route('/regularize', methods=['GET', 'POST'])
@login_required
def regularize():
    if request.method == 'POST':
        reg_date = request.form.get('date')
        punch_in = request.form.get('punch_in')
        punch_out = request.form.get('punch_out')
        reason = request.form.get('reason', '').strip()
        
        if not reg_date or not reason:
            flash('Date and reason are required.', 'danger')
            return redirect(url_for('regularize'))
        
        try:
            reg_date = datetime.strptime(reg_date, '%Y-%m-%d').date()
        except:
            flash('Invalid date format.', 'danger')
            return redirect(url_for('regularize'))
        
        if reg_date > date.today():
            flash('Cannot regularize future dates.', 'danger')
            return redirect(url_for('regularize'))
        
        existing = RegularizationRequest.query.filter_by(user_id=current_user.id, date=reg_date, status='pending').first()
        if existing:
            flash('A pending request already exists for this date.', 'warning')
            return redirect(url_for('regularize'))
        
        req_in = datetime.strptime(f"{reg_date} {punch_in}", '%Y-%m-%d %H:%M') if punch_in else None
        req_out = datetime.strptime(f"{reg_date} {punch_out}", '%Y-%m-%d %H:%M') if punch_out else None
        
        reg = RegularizationRequest(
            user_id=current_user.id,
            date=reg_date,
            requested_punch_in=req_in,
            requested_punch_out=req_out,
            reason=reason
        )
        db.session.add(reg)
        db.session.commit()
        flash('Regularization request submitted successfully. Waiting for manager approval.', 'success')
        return redirect(url_for('my_requests'))
    
    return render_template('regularize.html', today=date.today().isoformat())


@app.route('/my_requests')
@login_required
def my_requests():
    requests = RegularizationRequest.query.filter_by(user_id=current_user.id).order_by(RegularizationRequest.created_at.desc()).all()
    return render_template('my_requests.html', requests=requests)


@app.route('/manager/requests')
@login_required
def manager_requests():
    if not current_user.is_manager():
        flash('Access denied.', 'danger')
        return redirect(url_for('dashboard'))
    
    if current_user.is_admin():
        pending = RegularizationRequest.query.filter_by(status='pending').order_by(RegularizationRequest.created_at.desc()).all()
    else:
        team_ids = [m.id for m in User.query.filter_by(manager_id=current_user.id).all()]
        pending = RegularizationRequest.query.filter(
            RegularizationRequest.user_id.in_(team_ids),
            RegularizationRequest.status == 'pending'
        ).order_by(RegularizationRequest.created_at.desc()).all()
    
    return render_template('manager_requests.html', requests=pending)


@app.route('/manager/request/<int:req_id>/<action>', methods=['POST'])
@login_required
def review_request(req_id, action):
    if not current_user.is_manager():
        flash('Access denied.', 'danger')
        return redirect(url_for('dashboard'))
    
    reg = RegularizationRequest.query.get_or_404(req_id)
    
    # Check permission
    if not current_user.is_admin():
        if reg.employee.manager_id != current_user.id:
            flash('You can only review your team members.', 'danger')
            return redirect(url_for('manager_requests'))
    
    comment = request.form.get('comment', '')
    
    if action == 'approve':
        reg.status = 'approved'
        reg.reviewed_by = current_user.id
        reg.reviewed_at = datetime.utcnow()
        reg.manager_comment = comment
        
        # Update or create attendance
        att = Attendance.query.filter_by(user_id=reg.user_id, date=reg.date).first()
        if not att:
            att = Attendance(user_id=reg.user_id, date=reg.date)
            db.session.add(att)
        att.punch_in_time = reg.requested_punch_in
        att.punch_out_time = reg.requested_punch_out
        att.status = 'regularized'
        att.notes = f'Regularized by {current_user.name}. Reason: {reg.reason}'
        db.session.commit()
        flash('Request approved and attendance updated.', 'success')
    
    elif action == 'reject':
        reg.status = 'rejected'
        reg.reviewed_by = current_user.id
        reg.reviewed_at = datetime.utcnow()
        reg.manager_comment = comment
        db.session.commit()
        flash('Request rejected.', 'info')
    
    return redirect(url_for('manager_requests'))


# ---------- Holidays ----------
@app.route('/holidays')
@login_required
def holidays():
    all_holidays = Holiday.query.order_by(Holiday.date.desc()).all()
    return render_template('holidays.html', holidays=all_holidays)


@app.route('/holidays/add', methods=['GET', 'POST'])
@login_required
def add_holiday():
    if not current_user.is_manager():
        flash('Only managers/admins can add holidays.', 'danger')
        return redirect(url_for('holidays'))
    
    if request.method == 'POST':
        h_date = request.form.get('date')
        name = request.form.get('name', '').strip()
        desc = request.form.get('description', '').strip()
        
        try:
            h_date = datetime.strptime(h_date, '%Y-%m-%d').date()
        except:
            flash('Invalid date.', 'danger')
            return redirect(url_for('add_holiday'))
        
        if Holiday.query.filter_by(date=h_date).first():
            flash('Holiday already exists for this date.', 'warning')
            return redirect(url_for('add_holiday'))
        
        holiday = Holiday(date=h_date, name=name, description=desc, created_by=current_user.id)
        db.session.add(holiday)
        db.session.commit()
        flash(f'Holiday "{name}" added successfully.', 'success')
        return redirect(url_for('holidays'))
    
    return render_template('add_holiday.html')


@app.route('/holidays/delete/<int:hid>', methods=['POST'])
@login_required
def delete_holiday(hid):
    if not current_user.is_admin():
        flash('Only admin can delete holidays.', 'danger')
        return redirect(url_for('holidays'))
    h = Holiday.query.get_or_404(hid)
    db.session.delete(h)
    db.session.commit()
    flash('Holiday deleted.', 'info')
    return redirect(url_for('holidays'))


# ---------- Admin: Employees ----------
@app.route('/admin/employees')
@login_required
def employees():
    if not current_user.is_admin():
        flash('Admin access only.', 'danger')
        return redirect(url_for('dashboard'))
    users = User.query.order_by(User.role, User.name).all()
    managers = User.query.filter(User.role.in_(['admin', 'manager'])).all()
    return render_template('employees.html', users=users, managers=managers)


@app.route('/admin/employee/add', methods=['GET', 'POST'])
@login_required
def add_employee():
    if not current_user.is_admin():
        flash('Admin access only.', 'danger')
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        emp_id = request.form.get('emp_id', '').strip().upper()
        name = request.form.get('name', '').strip()
        mobile = request.form.get('mobile', '').strip()
        password = request.form.get('password', '')
        role = request.form.get('role', 'employee')
        manager_id = request.form.get('manager_id') or None
        monthly_salary = float(request.form.get('monthly_salary') or 0)
        
        if not all([emp_id, name, mobile, password]):
            flash('All fields are required.', 'danger')
            return redirect(url_for('add_employee'))
        
        if User.query.filter_by(emp_id=emp_id).first() or User.query.filter_by(mobile=mobile).first():
            flash('Employee ID or Mobile already exists.', 'danger')
            return redirect(url_for('add_employee'))
        
        user = User(
            emp_id=emp_id,
            name=name,
            mobile=mobile,
            role=role,
            manager_id=int(manager_id) if manager_id else None,
            monthly_salary=monthly_salary
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash(f'Employee {name} ({emp_id}) created successfully.', 'success')
        return redirect(url_for('employees'))
    
    managers = User.query.filter(User.role.in_(['admin', 'manager'])).all()
    return render_template('add_employee.html', managers=managers)


@app.route('/admin/employee/edit/<int:uid>', methods=['GET', 'POST'])
@login_required
def edit_employee(uid):
    if not current_user.is_admin():
        flash('Admin access only.', 'danger')
        return redirect(url_for('dashboard'))
    
    user = User.query.get_or_404(uid)
    
    if request.method == 'POST':
        user.name = request.form.get('name', '').strip()
        user.role = request.form.get('role', 'employee')
        manager_id = request.form.get('manager_id') or None
        user.manager_id = int(manager_id) if manager_id else None
        user.monthly_salary = float(request.form.get('monthly_salary') or 0)
        user.is_active = request.form.get('is_active') == 'on'
        
        new_pass = request.form.get('password', '').strip()
        if new_pass:
            user.set_password(new_pass)
        
        db.session.commit()
        flash('Employee updated.', 'success')
        return redirect(url_for('employees'))
    
    managers = User.query.filter(User.role.in_(['admin', 'manager']), User.id != uid).all()
    return render_template('edit_employee.html', user=user, managers=managers)


# ---------- Attendance History ----------
@app.route('/attendance')
@login_required
def attendance_history():
    month = request.args.get('month', date.today().strftime('%Y-%m'))
    try:
        year, mon = map(int, month.split('-'))
        start = date(year, mon, 1)
        end = date(year, mon, calendar.monthrange(year, mon)[1])
    except:
        start = date.today().replace(day=1)
        end = date.today()
        month = start.strftime('%Y-%m')
    
    records = Attendance.query.filter(
        Attendance.user_id == current_user.id,
        Attendance.date >= start,
        Attendance.date <= end
    ).order_by(Attendance.date.desc()).all()
    
    return render_template('attendance.html', records=records, month=month)


# ---------- Salary ----------
@app.route('/salary')
@login_required
def salary():
    months = []
    today = date.today()
    for i in range(6):
        d = today - timedelta(days=30*i)
        months.append(d.strftime('%Y-%m'))
    return render_template('salary.html', months=months, salary=current_user.monthly_salary)


@app.route('/salary/slip/<month>')
@login_required
def salary_slip(month):
    try:
        year, mon = map(int, month.split('-'))
        start = date(year, mon, 1)
        end = date(year, mon, calendar.monthrange(year, mon)[1])
    except:
        flash('Invalid month.', 'danger')
        return redirect(url_for('salary'))
    
    # Present days
    present = Attendance.query.filter(
        Attendance.user_id == current_user.id,
        Attendance.date >= start,
        Attendance.date <= end,
        Attendance.punch_in_time.isnot(None),
        Attendance.punch_out_time.isnot(None)
    ).all()
    present_days = len(present)
    
    # Holidays in month
    holidays_count = Holiday.query.filter(Holiday.date >= start, Holiday.date <= end).count()
    
    # Working days (approx: total days - Sundays - holidays)
    total_days = (end - start).days + 1
    sundays = sum(1 for i in range(total_days) if (start + timedelta(days=i)).weekday() == 6)
    expected_working = max(1, total_days - sundays - holidays_count)
    
    monthly = current_user.monthly_salary or 0
    daily_rate = monthly / expected_working if expected_working else 0
    earned = round(daily_rate * present_days, 2)
    
    # Generate PDF
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'Title', parent=styles['Heading1'], fontSize=22, textColor=colors.HexColor('#FFD700'),
        alignment=TA_CENTER, spaceAfter=6, fontName='Helvetica-Bold'
    )
    subtitle = ParagraphStyle(
        'Sub', parent=styles['Normal'], fontSize=11, textColor=colors.HexColor('#333333'),
        alignment=TA_CENTER, spaceAfter=20
    )
    heading = ParagraphStyle(
        'Head', parent=styles['Heading2'], fontSize=14, textColor=colors.HexColor('#000000'),
        spaceBefore=15, spaceAfter=8, fontName='Helvetica-Bold'
    )
    normal = ParagraphStyle('Norm', parent=styles['Normal'], fontSize=10, leading=14)
    
    elements = []
    elements.append(Paragraph("MEMORAA", title_style))
    elements.append(Paragraph("Photography Studio • Capturing Moments", subtitle))
    elements.append(Paragraph(f"<b>SALARY SLIP</b> — {calendar.month_name[mon]} {year}", 
                              ParagraphStyle('Slip', parent=styles['Heading2'], alignment=TA_CENTER, fontSize=16, spaceAfter=15)))
    
    # Employee info
    info_data = [
        ['Employee Name:', current_user.name, 'Emp ID:', current_user.emp_id],
        ['Mobile:', current_user.mobile, 'Role:', current_user.role.title()],
        ['Month:', f"{calendar.month_name[mon]} {year}", 'Generated:', datetime.now().strftime('%d-%b-%Y %H:%M')],
    ]
    info_table = Table(info_data, colWidths=[90, 150, 70, 150])
    info_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#555555')),
        ('TEXTCOLOR', (2, 0), (2, -1), colors.HexColor('#555555')),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica-Bold'),
        ('FONTNAME', (3, 0), (3, -1), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 20))
    
    # Salary calculation
    elements.append(Paragraph("Salary Calculation", heading))
    calc_data = [
        ['Particulars', 'Details', 'Amount (₹)'],
        ['Monthly Base Salary', f'As per structure', f'{monthly:,.2f}'],
        ['Expected Working Days', f'{expected_working} (excl. Sundays & Holidays)', ''],
        ['Days Present', f'{present_days} days (with Punch In & Out)', ''],
        ['Daily Rate', f'₹{daily_rate:,.2f}', ''],
        ['Gross Earned Salary', f'{present_days} × ₹{daily_rate:,.2f}', f'{earned:,.2f}'],
        ['Net Payable', '', f'₹ {earned:,.2f}'],
    ]
    calc_table = Table(calc_data, colWidths=[160, 220, 100])
    calc_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a1a1a')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#FFD700')),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (2, 0), (2, -1), 'RIGHT'),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#FFF8DC')),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, -1), (-1, -1), 11),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CCCCCC')),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(calc_table)
    elements.append(Spacer(1, 25))
    
    # Attendance summary
    elements.append(Paragraph("Attendance Summary (Present Days)", heading))
    if present:
        att_data = [['Date', 'Punch In', 'Punch Out', 'Hours', 'Status']]
        for a in present:
            att_data.append([
                a.date.strftime('%d-%b-%Y'),
                a.punch_in_time.strftime('%H:%M') if a.punch_in_time else '-',
                a.punch_out_time.strftime('%H:%M') if a.punch_out_time else '-',
                str(a.working_hours()),
                a.status.title()
            ])
        att_table = Table(att_data, colWidths=[90, 80, 80, 60, 80])
        att_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#333333')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#AAAAAA')),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#FFFDE7')]),
        ]))
        elements.append(att_table)
    else:
        elements.append(Paragraph("No complete punch records found for this month.", normal))
    
    elements.append(Spacer(1, 40))
    elements.append(Paragraph("This is a computer-generated salary slip from Memoraa Attendance System.", 
                              ParagraphStyle('Footer', parent=normal, alignment=TA_CENTER, textColor=colors.gray, fontSize=8)))
    elements.append(Paragraph("© Memoraa Photography Studio", 
                              ParagraphStyle('Footer2', parent=normal, alignment=TA_CENTER, textColor=colors.HexColor('#FFD700'), fontSize=9)))
    
    doc.build(elements)
    buffer.seek(0)
    
    filename = f"Memoraa_SalarySlip_{current_user.emp_id}_{month}.pdf"
    return send_file(buffer, as_attachment=True, download_name=filename, mimetype='application/pdf')


# ---------- Admin view all attendance / salary ----------
@app.route('/admin/attendance')
@login_required
def admin_attendance():
    if not current_user.is_manager():
        flash('Access denied.', 'danger')
        return redirect(url_for('dashboard'))
    
    month = request.args.get('month', date.today().strftime('%Y-%m'))
    emp_id = request.args.get('emp_id')
    
    try:
        year, mon = map(int, month.split('-'))
        start = date(year, mon, 1)
        end = date(year, mon, calendar.monthrange(year, mon)[1])
    except:
        start = date.today().replace(day=1)
        end = date.today()
        month = start.strftime('%Y-%m')
    
    query = Attendance.query.filter(Attendance.date >= start, Attendance.date <= end)
    
    if current_user.is_admin():
        if emp_id:
            u = User.query.filter_by(emp_id=emp_id).first()
            if u:
                query = query.filter_by(user_id=u.id)
    else:
        team_ids = [m.id for m in User.query.filter_by(manager_id=current_user.id).all()]
        query = query.filter(Attendance.user_id.in_(team_ids))
    
    records = query.order_by(Attendance.date.desc()).all()
    employees = User.query.filter(User.role != 'admin').all() if current_user.is_admin() else User.query.filter_by(manager_id=current_user.id).all()
    
    return render_template('admin_attendance.html', records=records, month=month, employees=employees, selected_emp=emp_id)


# ---------- API for location (optional helper) ----------
@app.route('/api/location', methods=['POST'])
@login_required
def save_location():
    data = request.get_json()
    # Just acknowledge; actual save happens on punch
    return jsonify({'status': 'ok'})


if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)