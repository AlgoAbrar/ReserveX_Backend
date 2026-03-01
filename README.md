# 🍽️ ReserveX - Restaurant Reservation System

![Django](https://img.shields.io/badge/Django-6.0-green)
![DRF](https://img.shields.io/badge/DRF-3.15-blue)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-blue)
![JWT](https://img.shields.io/badge/JWT-Authentication-orange)
![Vercel](https://img.shields.io/badge/Vercel-Deployable-black)

## 📋 Overview

ReserveX is a production-ready restaurant reservation system built with Django 6. It provides a complete solution for restaurant booking management with role-based access control, payment processing, and comprehensive dashboards.

### 🎯 Key Features

- **User Roles**: USER, MANAGER, ADMIN with specific permissions
- **Restaurant Management**: Multi-branch restaurant support
- **Table Booking**: Real-time availability with conflict prevention
- **Menu Management**: Digital menu with categories and pricing
- **Payment Integration**: Simulated payment gateway (Stripe-ready)
- **Dashboard Analytics**: Role-specific dashboards
- **Email Notifications**: Booking confirmations and reminders
- **API Documentation**: Swagger/ReDoc integration

## 🏗️ Architecture

```markdown
# ReserveX

A full-featured Restaurant Reservation & Management System built with Django and Django REST Framework.

---

## 📁 Project Structure

```

reservex/
├── reservex/        # Project core
├── users/           # User management & authentication
├── restaurants/     # Restaurant, branch, table, menu
├── bookings/        # Booking system
├── payments/        # Payment processing
├── dashboard/       # Analytics dashboards
├── core/            # Utilities & signals
├── api/             # API versioning
└── templates/       # HTML templates

````

---

## 🚀 Quick Start

### Prerequisites

- Python 3.11 or 3.12  
- PostgreSQL (optional, SQLite for development)  
- Git  

---

## ⚙️ Installation

### 1️⃣ Clone the repository

```bash
git clone https://github.com/yourusername/reservex.git
cd reservex
````

### 2️⃣ Create virtual environment

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Mac/Linux
source venv/bin/activate
```

### 3️⃣ Install dependencies

```bash
pip install -r requirements.txt
```

### 4️⃣ Configure environment variables

```bash
cp .env.example .env
# Edit .env with your configuration
```

### 5️⃣ Run migrations

```bash
python manage.py makemigrations
python manage.py migrate
```

### 6️⃣ Load demo data (optional)

```bash
python manage.py loaddata demodata.json
```

### 7️⃣ Create superuser

```bash
python manage.py createsuperuser
```

### 8️⃣ Run development server

```bash
python manage.py runserver
```

Visit:

```
http://127.0.0.1:8000/api/v1/
```

---

# 🔑 API Endpoints

## Authentication (`/api/v1/auth/`)

| Method | Endpoint        | Description          |
| ------ | --------------- | -------------------- |
| POST   | `/users/`       | Register new user    |
| POST   | `/jwt/create/`  | Login (get JWT)      |
| POST   | `/jwt/refresh/` | Refresh JWT          |
| GET    | `/users/me/`    | Current user profile |

---

## Restaurants (`/api/v1/restaurants/`)

| Method | Endpoint              | Description              |
| ------ | --------------------- | ------------------------ |
| GET    | `/`                   | List all restaurants     |
| GET    | `/{id}/`              | Restaurant details       |
| GET    | `/{id}/branches/`     | Restaurant branches      |
| GET    | `/{id}/menu/`         | Restaurant menu          |
| GET    | `/{id}/availability/` | Check table availability |
| GET    | `/featured/`          | Featured restaurants     |

---

## Bookings (`/api/v1/bookings/`)

| Method | Endpoint               | Description              |
| ------ | ---------------------- | ------------------------ |
| GET    | `/`                    | List bookings            |
| POST   | `/`                    | Create booking           |
| GET    | `/my-bookings/`        | User's bookings          |
| GET    | `/upcoming/`           | Upcoming bookings        |
| GET    | `/check-availability/` | Check table availability |

---

## Payments (`/api/v1/payments/`)

| Method | Endpoint        | Description            |
| ------ | --------------- | ---------------------- |
| POST   | `/start/`       | Start payment process  |
| GET    | `/my-payments/` | User's payments        |
| POST   | `/{id}/refund/` | Refund payment (admin) |

---

## Dashboard (`/api/v1/dashboard/`)

| Method | Endpoint             | Description       |
| ------ | -------------------- | ----------------- |
| GET    | `/user/overview/`    | User dashboard    |
| GET    | `/manager/overview/` | Manager dashboard |
| GET    | `/admin/overview/`   | Admin dashboard   |

---

# 📚 Documentation

* Swagger UI: `http://127.0.0.1:8000/swagger/`
* ReDoc: `http://127.0.0.1:8000/redoc/`
* Health Check: `http://127.0.0.1:8000/health/`

---

# 🛠️ Technology Stack

## Backend

* Django 6 — Web framework
* Django REST Framework — API development
* PostgreSQL — Database
* JWT — Authentication
* Djoser — Auth endpoints
* Cloudinary — Media storage

## Tools & Libraries

* drf-yasg — API documentation
* django-cors-headers — CORS support
* django-filter — Query filtering
* WhiteNoise — Static files
* python-decouple — Environment configuration

## Deployment

* Vercel — Hosting platform
* Gunicorn — WSGI server
* WhiteNoise — Static file serving

---

# 👥 User Roles & Permissions

## USER

* Browse restaurants
* Make reservations
* View booking history
* Cancel own bookings
* Make payments

## MANAGER

* Manage assigned restaurants
* Confirm/reject bookings
* Add/edit tables
* Manage menu items
* View restaurant analytics

## ADMIN

* Full system access
* Manage users & roles
* Manage all restaurants
* View platform analytics
* Process refunds

---

# 📊 Database Schema

## Core Models

* **User** (email, name, phone, role)
* **Restaurant** (name, cuisine, location, manager)
* **Branch** (restaurant, address, phone, hours)
* **Table** (branch, number, capacity, type)
* **MenuItem** (restaurant, name, price, category)
* **Booking** (user, table, date, time, status)
* **Payment** (booking, amount, status, transaction_id)

---

# 🔒 Security Features

* JWT authentication
* Role-based access control
* Email verification
* Password validation
* SQL injection protection
* XSS protection
* CSRF protection
* Secure headers (HSTS, CSP)

---

# 🚢 Deployment

## Vercel Deployment

Install Vercel CLI:

```bash
npm i -g vercel
```

Configure `vercel.json` (already included).

Set environment variables in the Vercel dashboard.

Deploy:

```bash
vercel --prod
```

---

## Environment Variables

```env
SECRET_KEY=your-secret-key
DEBUG=False
ALLOWED_HOSTS=.vercel.app,example.com
DATABASE_URL=postgresql://...
CLOUDINARY_URL=cloudinary://...
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
```

---

# 🧪 Testing

```bash
# Run tests
python manage.py test

# Run with coverage
coverage run manage.py test
coverage report
coverage html
```

---

# 📈 Performance Optimizations

* Database indexing on frequently queried fields
* Query optimization (`select_related`, `prefetch_related`)
* Connection pooling for PostgreSQL
* Static file compression (WhiteNoise)
* Redis caching ready (configurable)

---

# 🤝 Contributing

1. Fork the repository
2. Create feature branch

   ```bash
   git checkout -b feature/AmazingFeature
   ```
3. Commit changes

   ```bash
   git commit -m "Add AmazingFeature"
   ```
4. Push to branch

   ```bash
   git push origin feature/AmazingFeature"
   ```
5. Open a Pull Request

---

# 📝 License

This project is proprietary software. All rights reserved.

---

# 📧 Contact

* Email: [support@reservex.com](mailto:support@reservex.com)
* Website: [https://reservex.com](https://reservex.com)
* GitHub: [https://github.com/AlgoAbrar/reservex_backend](https://github.com/yourusername/reservex)

---

# 🙏 Acknowledgments

* Django REST Framework team
* Djoser contributors
* Cloudinary for media hosting
* Vercel for hosting platform

---

# 📊 Project Status

* ✅ Phase 1: Core Setup — Complete
* ✅ Phase 2: User Management — Complete
* ✅ Phase 3: Restaurant Management — Complete
* ✅ Phase 4: Booking System — Complete
* ✅ Phase 5: Payment Integration — Complete
* ✅ Phase 6: Dashboard — Complete
* ✅ Phase 7: API & Documentation — Complete
* 🟡 Phase 8: Testing — In Progress
* ⚪ Phase 9: Deployment — Ready
* ⚪ Phase 10: Production Launch — Pending
