# 🎪 Hamayesh Negar - Conference Management System

Hamayesh Negar is a comprehensive Django-based conference management system designed to streamline the organization and administration of conferences and events. The system provides robust functionality for managing attendees, tasks, categories, and user permissions.

## ✨ Features

- 📅 **Conference Management**: Create and manage conferences with details such as name, description, start/end dates
- 👥 **Attendee Management**: Register and track conference attendees with unique identification codes
- ✅ **Task Assignment**: Create tasks, assign them to attendees, and track completion status
- 🏷️ **Category System**: Organize attendees into categories for better management
- 👮 **User Roles**: Three-tier user system (Super User, Hamayesh Manager, Hamayesh Yar) with appropriate permissions
- 🖥️ **Admin Interface**: Customized Django admin with Jazzmin for improved UX
- 🔌 **RESTful API**: Comprehensive API for integration with other services or frontend applications
- 🔐 **Authentication**: Token-based authentication for API access

## 🛠️ Tech Stack

- Django 5.1
- Django REST Framework
- PostgreSQL (configurable)
- Jazzmin for admin UI enhancement

## 📂 Project Structure

The project is organized into several Django apps:

- **authentication**: Handles user registration and login
- **conference**: Manages conference data and related operations
- **person**: Handles attendees, categories, tasks, and assignments
- **user**: Custom user model with role-based permissions

## 📥 Installation

### 📋 Prerequisites

- Python 3.8+
- PostgreSQL (recommended) or other database

### 🚀 Setup

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/hamayesh-negar.git
   cd hamayesh-negar
   ```

2. Create and activate a virtual environment:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

4. Create a `.env` file in the project root with the following variables:
   ```
   SECRET_KEY=your_secret_key
   DEBUG=1
   ALLOWED_HOSTS=localhost 127.0.0.1
   
   DATABASE_ENGINE=django.db.backends.postgresql
   DATABASE_NAME=hamayesh_negar
   DATABASE_USER=your_db_user
   DATABASE_PASSWORD=your_db_password
   DATABASE_HOST=localhost
   DATABASE_PORT=5432
   ```

5. Run migrations:
   ```
   python manage.py migrate
   ```

6. Create a superuser:
   ```
   python manage.py createsuperuser
   ```

7. Run the development server:
   ```
   python manage.py runserver
   ```

8. Access the admin interface at http://localhost:8000/admin/

## 🔗 API Endpoints

The system provides a comprehensive RESTful API with the following main endpoints:

- `/api/v1/conferences/`: Conference management
- `/api/v1/categories/`: Category management
- `/api/v1/persons/`: Attendee management
- `/api/v1/tasks/`: Task management
- `/api/v1/person_tasks/`: Task assignment management
- `/api/v1/user/users/`: User management
- `/auth/register/`: User registration
- `/auth/login/`: User login
- `/api/token/`: Token authentication

## 👤 User Roles

The system supports three user roles:

1. **Super User**: Full access to all features and data
2. **Hamayesh Manager**: Can manage conferences, attendees, tasks, and Hamayesh Yars
3. **Hamayesh Yar**: Limited access based on assigned permissions

## 🚢 Deployment

For production deployment, consider the following steps:

1. Set `DEBUG=0` in your environment variables
2. Configure `ALLOWED_HOSTS` with your domain
3. Use a production-grade server (Gunicorn, uWSGI)
4. Set up a reverse proxy (Nginx, Apache)
5. Configure proper database settings
6. Collect static files:
   ```
   python manage.py collectstatic
   ```
