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
- 🐳 **Docker Support**: Easy deployment with Docker and Nginx

## 🛠️ Tech Stack

- Django
- Django REST Framework
- PostgreSQL (configurable)
- Jazzmin for admin UI enhancement
- Docker & Docker Compose for containerization
- Nginx for reverse proxy and SSL termination

## 📂 Project Structure

The project is organized into several Django apps:

- **authentication**: Handles user registration and login
- **conference**: Manages conference data and related operations
- **person**: Handles attendees, categories, tasks, and assignments
- **user**: Custom user model with role-based permissions

## 📥 Installation

You can install Hamayesh Negar either using Docker (recommended) or traditional methods.

### 🐳 Docker Installation (Recommended)

#### Prerequisites
- Docker and Docker Compose installed on your server
- Root/sudo access for SSL certificate setup (if using Let's Encrypt)

#### Quick Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/Hamayesh-Negar/Back-end.git
   cd Back-end
   ```

2. Create your environment file:
   ```bash
   cp .env.example .env
   ```

3. Edit the `.env` file to configure your settings:
   ```bash
   nano .env
   ```
   
   Important settings to configure:
   - `DOMAIN` and `EMAIL` for SSL certificates
   - `USE_LETSENCRYPT` (set to `true` for production)
   - Database credentials
   - Django secret key

4. Run the setup script to configure the environment:
   ```bash
   sudo ./setup.sh
   ```
   This script will:
   - Create required directories
   - Set up SSL certificates (Let's Encrypt)
   - Build Docker containers

5. Start the application:
   ```bash
   docker-compose up -d
   ```

6. Access the application at `https://your-domain.com/admin/`

### 📋 Traditional Installation

#### Prerequisites
- Python 3.8+
- PostgreSQL (recommended) or other database

#### Setup

1. Clone the repository:
   ```
   git clone https://github.com/Hamayesh-Negar/Back-end.git
   cd Back-end
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

8. Access the application at `https://your-domain.com/admin/`

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

For production deployment, we recommend using Docker with Let's Encrypt SSL certificates:

1. Configure your `.env` file with production settings.

2. Run the setup script with sudo to obtain and install Let's Encrypt certificates:
   ```bash
   sudo ./setup.sh
   ```

3. Start the services:
   ```bash
   docker-compose up -d
   ```

### SSL Certificate Management

The Docker setup includes automatic SSL certificate management:

Let's Encrypt certificates can be automatically obtained and renewed.
  - Set `USE_LETSENCRYPT=true` in your `.env` file
  - Certificates will be automatically renewed before expiry

## 🛠️ Development

For local development, you can use either method:

### Docker-based Development

1. Set `DEBUG=1` in your `.env` file
2. Use `USE_LETSENCRYPT=false` to use self-signed certificates
3. Start the containers: `docker-compose up`

### Traditional Development

1. Use virtual environment and run `python manage.py runserver`
2. Configure your `.env` file with local database settings
