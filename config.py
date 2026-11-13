import os
from datetime import timedelta

basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'memoraa-photography-secret-key-2026-ajay'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///' + os.path.join(basedir, 'memoraa.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    # Company info
    COMPANY_NAME = "Memoraa"
    COMPANY_TAGLINE = "Capturing Moments, Creating Memories"
    COMPANY_THEME = "Photography Studio"