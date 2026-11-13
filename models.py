from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, date

db = SQLAlchemy()

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    emp_id = db.Column(db.String(20), unique=True, nullable=False)  # e.g. EMP001 or mobile for admin
    name = db.Column(db.String(100), nullable=False)
    mobile = db.Column(db.String(15), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='employee')  # admin, manager, employee
    manager_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    monthly_salary = db.Column(db.Float, default=0.0)  # Base monthly salary
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    manager = db.relationship('User', remote_side=[id], backref='team_members')
    attendances = db.relationship('Attendance', backref='employee', lazy='dynamic')
    regularization_requests = db.relationship('RegularizationRequest', 
                                               foreign_keys='RegularizationRequest.user_id',
                                               backref='employee', lazy='dynamic')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def is_admin(self):
        return self.role == 'admin'

    def is_manager(self):
        return self.role in ('admin', 'manager')

    def __repr__(self):
        return f'<User {self.emp_id} - {self.name}>'


class Attendance(db.Model):
    __tablename__ = 'attendances'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    date = db.Column(db.Date, nullable=False, default=date.today)
    punch_in_time = db.Column(db.DateTime, nullable=True)
    punch_out_time = db.Column(db.DateTime, nullable=True)
    punch_in_lat = db.Column(db.Float, nullable=True)
    punch_in_lng = db.Column(db.Float, nullable=True)
    punch_out_lat = db.Column(db.Float, nullable=True)
    punch_out_lng = db.Column(db.Float, nullable=True)
    status = db.Column(db.String(20), default='pending')  # present, regularized, absent, half_day
    notes = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint('user_id', 'date', name='unique_user_date'),)

    def is_present(self):
        return self.punch_in_time is not None and self.punch_out_time is not None

    def working_hours(self):
        if self.punch_in_time and self.punch_out_time:
            delta = self.punch_out_time - self.punch_in_time
            return round(delta.total_seconds() / 3600, 2)
        return 0.0

    def __repr__(self):
        return f'<Attendance {self.user_id} {self.date}>'


class Holiday(db.Model):
    __tablename__ = 'holidays'
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(255), nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    creator = db.relationship('User', backref='created_holidays')

    def __repr__(self):
        return f'<Holiday {self.date} - {self.name}>'


class RegularizationRequest(db.Model):
    __tablename__ = 'regularization_requests'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    requested_punch_in = db.Column(db.DateTime, nullable=True)
    requested_punch_out = db.Column(db.DateTime, nullable=True)
    reason = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, approved, rejected
    reviewed_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    manager_comment = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    reviewer = db.relationship('User', foreign_keys=[reviewed_by], backref='reviewed_requests')

    def __repr__(self):
        return f'<RegRequest {self.user_id} {self.date} {self.status}>'