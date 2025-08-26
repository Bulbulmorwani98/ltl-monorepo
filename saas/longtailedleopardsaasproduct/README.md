Welcome to the LTL project. This document provides a step-by-step guide to help you set up and run the application in your local development environment.


# 🐆 Long-Tailed Leopard SaaS Project

Welcome to the Long-Tailed Leopard SaaS project! This guide will help you set up and run the application in your local development environment.

## 📋 Table of Contents
- [🐆 Long-Tailed Leopard SaaS Project](#-long-tailed-leopard-saas-project)
    - [📋 Table of Contents](#-table-of-contents)
    - [✅ Prerequisites](#-prerequisites)
    - [⚙️ Setup Guide](#️-setup-guide)
        - [1. Clone Repository](#1-clone-repository)
        - [2. Create virtual environment](#2-create-virtual-environment)
        - [3. Activate environment](#3-activate-environment)
            - [Windows](#windows)
            - [macOS/Linux](#macoslinux)
        - [4. Load libs for env from requirements.txt](#4-load-libs-for-env-from-requirementstxt)
        - [5. Database Configuration](#5-database-configuration)
        - [6. Apply Migrations](#6-apply-migrations)
        - [7. Create Superadmin](#7-create-superadmin)
        - [8. Create superuser](#8-create-superuser)
        - [9. Create tenant](#9-create-tenant)
        - [10. Add domain](#10-add-domain)
        - [11. Run Server](#11-run-server)
- [🌐 Accessing the Application](#-accessing-the-application)
    - [API Documentation (Swagger)](#api-documentation-swagger)
    - [Credentials](#credentials)

## ✅ Prerequisites

Before you begin, ensure you have the following installed:

- Python 3.10.12
- pip (Python package manager)
- Virtualenv (recommended)
- PostgreSQL or MySQL
- Git (optional but recommended)

## ⚙️ Setup Guide

### 1. Clone Repository

git clone  <git_clone_link>
cd longtailedleopardsaasproduct

### 2. Create virtual environment(if running without docker then consider this as step 2 and follow on, otherwise jump to step 5)
python -m venv venv

### 3. Activate environment
#### Windows:
venv\Scripts\activate
#### macOS/Linux:
source venv/bin/activate

### 4. Load libs for env from requirements.txt 
pip install -r requirements.txt

### 5. Configure the .env
Add .env file to project root.


### 6. Database Configuration
#### Update your .env file with appropriate database configs:

DB_NAME=your_db_name

DB_USER=your_db_user

DB_PASSWORD=your_db_password

DB_HOST=localhost

DB_PORT=5432

### 7. Docker Setup(Start Containers)(If not using docker then skip the step no:-6)
docker-compose down --remove-orphans
docker-compose build --no-cache
docker-compose up -d

Create a new database in your DBMS (if you are using docker, you can use the docker-compose.yml in the root).


### 8. Database Configuration
#### Update your .env file with appropriate database configs:

DB_NAME=your_db_name

DB_USER=your_db_user

DB_PASSWORD=your_db_password

DB_HOST=localhost

DB_PORT=5432

Create a new database in your DBMS (if you are using docker, you can use the docker-compose.yml in the root).

### 9. Apply Migrations

Set up the database schema:

bash
python manage.py migrate 
or for docker(docker-compose exec web python manage.py migrate_schemas --shared)

### 10. Create Superadmin
Create a superuser account and tenant:

bash
python manage.py shell 
or for docker(docker-compose exec web python manage.py shell)

Then execute:

from apps.accounts.models import Company, Domain, User

from datetime import date, timedelta

### 11. Create superuser
user = User.objects.create(
    email='superadmin@yopmail.com',
    is_staff=True,
    is_superuser=True,
    role=0
)
user.set_password('Test@123')
user.save()

### 12. Create tenant
tenant = Company.objects.create(
    name="Super Admin Org",
    paid_until=date.today() + timedelta(days=30),
    on_trial=True,
    schema_name="public"
)

### 13. Add domain
Domain.objects.create(
    domain="localhost",
    tenant=tenant,
    is_primary=True
)
Exit the shell with exit().

### 14. Run Server(if running the project without docker)
Start the development server:

bash
python manage.py runserver

### Note:- If running the project with docker, simply open the swagger url 'http://localhost:8000/swagger/' in the browser after creating the superuser.

#### API Documentation (Swagger)
http://localhost:8000/swagger/

### Credentials:
Email: superadmin@yopmail.com
Password: Test@123
