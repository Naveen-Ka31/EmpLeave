# Empleave — Employee Leave Management System

A full-stack Django web application for managing employee leaves
with multi-level approval workflows and automatic email notifications.

## Features
- Role-based access — Employee, Manager, HR, Boss
- Multi-level approval — Employee → Manager → HR/Boss
- Leave balance tracking per employee
- Automatic email notifications at every stage
- HR dashboard to add employees
- MySQL database

## Tech Stack
- Python, Django 4.2
- MySQL
- Bootstrap 5
- Gmail SMTP

## Setup

### 1. Clone the repo
git clone https://github.com/Naveen-Ka31/empleave.git
cd empleave

### 2. Create virtual environment
python -m venv venv
venv\Scripts\activate

### 3. Install dependencies
pip install -r requirements.txt

### 4. Create MySQL database
CREATE DATABASE empleave_db CHARACTER SET utf8mb4;

### 5. Set environment variables
Create a .env file:
DB_NAME=empleave_db
DB_USER=root
DB_PASSWORD=your_password
EMAIL_HOST_USER=your_gmail@gmail.com
EMAIL_HOST_PASSWORD=your_app_password

### 6. Run migrations
python manage.py makemigrations
python manage.py migrate

### 7. Create superuser
python manage.py createsuperuser

### 8. Run server
python manage.py runserver

## Roles

| Role | Access |
|------|--------|
| Employee | Apply leave, view balance |
| Manager | Review team requests |
| HR | Add employees, final approval |
| Boss | Company-wide view, final approval |