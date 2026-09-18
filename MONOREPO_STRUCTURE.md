# Comment Checker Monorepo Structure

## Overview

This document describes the structure of the Comment Checker monorepo, which includes:
- **Backend**: FastAPI application for comment classification and user management
- **Frontend**: Astro with Next.js for the web interface
- **Database**: PostgreSQL 18 (Alpine) for data storage

## Directory Structure

```
comment-checker/
├── backend/
│   ├── src/
│   │   ├── api/
│   │   │   ├── v1/
│   │   │   │   ├── auth.py          # Authentication endpoints
│   │   │   │   ├── comments.py      # Comment CRUD endpoints
│   │   │   │   ├── classifications.py # Classification endpoints
│   │   │   │   ├── dashboard.py     # Dashboard statistics
│   │   │   │   ├── invites.py       # Invite management
│   │   │   │   └── users.py         # User management
│   │   │   └── __init__.py
│   │   ├── config/
│   │   │   ├── __init__.py
│   │   │   └── settings.py         # Application settings
│   │   ├── core/
│   │   │   ├── dependencies.py    # Dependency injections
│   │   │   └── security.py        # Security utilities
│   │   ├── db/
│   │   │   ├── base.py            # SQLAlchemy base
│   │   │   ├── session.py         # Database session management
│   │   │   └── models/
│   │   │       ├── __init__.py
│   │   │       ├── user.py         # User model
│   │   │       ├── comment.py      # Comment model
│   │   │       ├── classification.py # Classification model
│   │   │       └── token.py        # Token models
│   │   ├── migrations/
│   │   │   ├── versions/
│   │   │   │   └── initial_migration.py
│   │   │   ├── alembic.ini
│   │   │   └── env.py
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── auth.py          # Auth service
│   │   │   ├── classification.py # Classification service
│   │   │   └── comment.py       # Comment service
│   │   ├── utils/
│   │   │   ├── __init__.py
│   │   │   ├── csv_parser.py    # CSV parsing utilities
│   │   │   └── security.py       # Password hashing, JWT
│   │   └── main.py              # FastAPI application entry
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── conftest.py          # Pytest fixtures
│   │   ├── test_auth.py         # Auth tests
│   │   ├── test_comments.py     # Comment tests
│   │   ├── test_invite.py       # Invite tests
│   │   └── test_users.py        # User tests
│   ├── Dockerfile
│   ├── requirements.txt
│   └── .env.example
│
├── frontend/
│   ├── public/
│   ├── src/
│   │   ├── components/
│   │   │   ├── ui/
│   │   │   │   ├── Button.tsx
│   │   │   │   ├── Input.tsx
│   │   │   │   ├── Modal.tsx
│   │   │   │   └── NotificationToast.tsx
│   │   │   ├── tables/
│   │   │   │   └── DataTable.tsx
│   │   │   └── index.ts
│   │   ├── hooks/
│   │   │   └── useNotifications.ts
│   │   ├── layouts/
│   │   │   └── RootLayout.astro
│   │   ├── pages/
│   │   │   ├── comments/
│   │   │   │   └── [id].astro
│   │   │   ├── login.astro
│   │   │   ├── register.astro
│   │   │   ├── upload.astro
│   │   │   ├── invites.astro
│   │   │   ├── classifications.astro
│   │   │   ├── reset-password.astro
│   │   │   └── index.astro
│   │   ├── services/
│   │   │   ├── api.ts
│   │   │   └── auth.ts
│   │   ├── types/
│   │   │   └── index.ts
│   │   └── utils/
│   │       └── index.ts
│   ├── package.json
│   ├── tsconfig.json
│   ├── astro.config.mjs
│   ├── tailwind.config.js
│   └── Dockerfile
│
├── docker-compose.yml
├── docker-compose.prod.yml
├── Makefile
├── .github/
│   └── workflows/
│       └── build-and-deploy.yml
└── README.md
```

## Features Implemented

### Authentication & Security
- ✅ JWT-based authentication (Access + Refresh tokens)
- ✅ OWASP-compliant password hashing (bcrypt)
- ✅ Token expiration and refresh
- ✅ Secure token storage
- ✅ First admin creation on startup
- ✅ Role-based access control (Admin vs Regular users)

### Comment Management
- ✅ CSV file upload for comments
- ✅ Comment CRUD operations
- ✅ Comment classification (TypeSafe + Mistral integration)
- ✅ Comment status tracking (pending, processing, completed, failed, waiting)
- ✅ Comment filtering, sorting, pagination

### Classification
- ✅ Multiple backend support (TypeSafe, Mistral, Combined)
- ✅ Category classification (hate, harassment, violence, self_harm, sexual, spam, illegal, safe)
- ✅ Severity levels (low, medium, high, critical)
- ✅ Confidence scores
- ✅ Harmful scores

### Dashboard
- ✅ Statistics overview
- ✅ Status distribution (pie chart ready)
- ✅ Category distribution (pie chart ready)
- ✅ Recent comments
- ✅ Date range filtering (1 month, 6 months, 1 year, all data - default 1 year)

### User Management
- ✅ User registration via invite tokens
- ✅ User profile management
- ✅ Admin user management
- ✅ Invite token generation and management
- ✅ Password reset functionality

### UI/UX
- ✅ Responsive design with Tailwind CSS
- ✅ Login/Register pages
- ✅ Comments list with filtering
- ✅ Comment detail view
- ✅ Upload CSV page
- ✅ Admin dashboard
- ✅ Classifications view
- ✅ Notifications system
- ✅ Searchable, sortable, filterable, paginated tables
- ✅ Multiple page sizes (5, 10, 15, 25)

## Tech Stack

### Backend
- **Framework**: FastAPI
- **Database**: PostgreSQL 18 (Alpine)
- **ORM**: SQLAlchemy 2.0 (Async)
- **Migration**: Alembic
- **Security**: JWT, bcrypt, OWASP guidelines
- **Validation**: Pydantic V2
- **Testing**: pytest, pytest-asyncio, httpx

### Frontend
- **Framework**: Astro with Next.js integration
- **Styling**: Tailwind CSS
- **State Management**: React Context API
- **HTTP Client**: Axios
- **TypeScript**: Full type safety

### Infrastructure
- **Containerization**: Docker
- **Orchestration**: Docker Compose
- **CI/CD**: GitHub Actions
- **Build**: Multi-stage Docker builds

## Environment Variables

### Backend (.env)
```bash
DATABASE_URL=postgresql+asyncpg://user:password@db:5432/comment_checker
JWT_SECRET=your-secret-key
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7
MISTRAL_API_KEY=your-mistral-api-key
SMTP_HOST=mailpit
SMTP_PORT=1025
SMTP_USER=
SMTP_PASSWORD=
EMAIL_FROM=noreply@comment-checker.local
FIRST_ADMIN_EMAIL=admin@localhost
FIRST_ADMIN_PASSWORD=admin
FIRST_ADMIN_NAME=Admin
CORS_ORIGINS=*
DEBUG=false
```

### Frontend (.env)
```bash
PUBLIC_API_URL=http://localhost:8000
NODE_ENV=production
```

## Quick Start

### Development
```bash
# Start all services
make dev

# Stop services
make down

# View logs
make logs

# Run database migrations
make migrate

# Run tests
make test
```

### Production
```bash
# Build production images
make build

# Start production services
make prod-up

# Stop production services
make prod-down
```

## API Endpoints

### Authentication
- `POST /auth/login` - Login with email/password
- `POST /auth/refresh` - Refresh access token
- `POST /auth/logout` - Logout and revoke refresh token
- `GET /auth/me` - Get current user info

### Users
- `GET /users` - List users (Admin only)
- `POST /users` - Create user (Admin only)
- `GET /users/{id}` - Get user
- `PUT /users/{id}` - Update user
- `DELETE /users/{id}` - Delete user (Admin only)

### Comments
- `GET /comments` - List comments
- `POST /comments` - Create comment
- `GET /comments/{id}` - Get comment
- `PUT /comments/{id}` - Update comment
- `DELETE /comments/{id}` - Delete comment
- `POST /comments/upload-csv` - Upload CSV file
- `POST /comments/{id}/classify` - Classify comment
- `POST /comments/{id}/reclassify` - Reclassify comment

### Classifications
- `GET /classifications` - List classifications
- `GET /classifications/{id}` - Get classification
- `GET /classifications/stats` - Get classification statistics

### Dashboard
- `GET /dashboard/stats` - Get dashboard statistics
- `GET /dashboard/status-distribution` - Get status distribution
- `GET /dashboard/category-distribution` - Get category distribution

### Invites
- `GET /invites` - List invite tokens (Admin only)
- `POST /invites` - Create invite token (Admin only)
- `GET /invites/{token}` - Get invite token info
- `POST /invites/{token}/use` - Use invite token to register
- `DELETE /invites/{token}` - Revoke invite token (Admin only)

### Password Reset
- `POST /password-reset/request` - Request password reset
- `POST /password-reset/confirm` - Confirm password reset

### Health
- `GET /health` - Health check endpoint

## Frontend Pages

- `/` - Dashboard
- `/login` - Login page
- `/register` - Registration page (requires invite token)
- `/comments` - Comments list
- `/comments/{id}` - Comment details
- `/upload` - CSV upload page
- `/classifications` - Classifications list
- `/invites` - Admin invite management
- `/reset-password` - Password reset page

## Security Considerations

1. **JWT Tokens**: Access tokens expire after 30 minutes, refresh tokens after 7 days
2. **Password Hashing**: Uses bcrypt with appropriate work factor
3. **Token Storage**: Refresh tokens stored in database, access tokens in memory
4. **CORS**: Configurable via CORS_ORIGINS environment variable
5. **Rate Limiting**: Can be added via FastAPI middleware
6. **Input Validation**: All inputs validated using Pydantic models
7. **SQL Injection**: Prevented via SQLAlchemy ORM
8. **XSS**: Prevented via proper escaping in frontend
9. **CSRF**: Not needed for API (JWT in Authorization header)
10. **OWASP Top 10**: Addressed injection, broken auth, sensitive data exposure, XML external entities, broken access control, security misconfiguration, XSS, insecure deserialization, insufficient logging, using components with known vulnerabilities

## Performance Considerations

1. **Database Indexes**: All query fields are indexed
2. **Pagination**: All list endpoints support pagination
3. **Text Search**: Uses PostgreSQL pg_trgm for efficient text search
4. **Caching**: Can be added via Redis or similar
5. **Connection Pooling**: SQLAlchemy async connection pooling

## Future Enhancements

1. **Social Media URL Ingestion**: Add support for fetching comments from social media URLs
2. **Real-time Updates**: Add WebSocket support for real-time classification updates
3. **Export**: Add CSV/Excel export for comments and classifications
4. **Audit Logging**: Add comprehensive audit logging
5. **Two-Factor Authentication**: Add 2FA support
6. **API Rate Limiting**: Implement rate limiting
7. **Email Verification**: Add email verification for user registration
8. **Advanced Filtering**: Add more advanced filtering options
9. **Bulk Operations**: Add bulk classification and deletion
10. **Webhooks**: Add webhook support for classification events
