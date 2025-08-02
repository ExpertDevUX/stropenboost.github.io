# Overview

StrophenBoost is a professional live streaming platform built with Flask that provides real-time video broadcasting capabilities. The system supports RTMP ingest for broadcasters and delivers streams in multiple formats (HLS and DASH) to viewers. It features a complete broadcasting ecosystem with user management, stream analytics, real-time chat, embeddable players, and a comprehensive dashboard for content creators.

# User Preferences

Preferred communication style: Simple, everyday language.

# Recent Changes

- **Complete Deployment Automation (2025-08-02)**: Created comprehensive `install.sh` script with automated SSL certificate setup via Let's Encrypt DNS verification, complete system configuration, and production-ready deployment
- **Professional Streaming Software Integration (2025-08-02)**: Added comprehensive streaming setup guide with detailed instructions for OBS Studio, vMix, XSplit, and mobile apps, including RTMP connection testing and stream key generation
- **Enhanced RTMP Server Implementation (2025-08-02)**: Fixed RTMP server protocol handling for professional streaming software compatibility, improved error handling, and proper FFmpeg integration
- **Real-time Chat System with AI Bot Integration (2025-08-02)**: Implemented comprehensive live chat with WebSocket support, chat management interface, Gemini AI bot for moderation and user support, and real-time messaging capabilities
- **Comprehensive Admin Settings System (2025-08-02)**: Implemented complete admin panel with password management, third-party integrations, social footer links, streaming configurations, and low latency settings
- **Multi-Protocol Stream Server Selection (2025-08-02)**: Added advanced server switching with HLS, DASH, and WebRTC options, quality selectors, and real-time connection indicators
- **Enhanced Stream View Page (2025-08-02)**: Completely redesigned stream view with broadcaster avatar, comprehensive stream information, hashtags system, and real-time editing capabilities
- **Profile System Implementation**: Added complete user profile functionality with avatar upload, personal information editing, security settings, and broadcaster-specific features
- **Management Actions Fixed**: Implemented working backend routes and JavaScript handlers for User Management and Content Management actions
- **Contact Page Enhancement**: Completely redesigned with beautiful gradient hero section, enhanced forms, FAQ section, and animated social icons
- **Dark Mode Enhancements**: Improved dark mode visibility for all pages, forms, tables, and components with proper GitHub icon white border styling
- **Management Pages**: Added User Management and Content Management pages with comprehensive admin functionality
- **Footer Enhancement**: Added functional pages for About, Documentation, Privacy Policy, and Contact with comprehensive content and working navigation
- **Expert Dev UX Attribution**: Added proper copyright attribution to Expert Dev UX with GitHub profile link in footer
- **Social Media Polish**: Enhanced social media icons with brand-specific colored backgrounds, circular borders, and smooth animations
- **Live Streaming Improvements**: Enhanced video player with theme compatibility, proper error handling, and FFmpeg integration

# System Architecture

## Backend Architecture
- **Flask Application Framework**: Core web application using Flask with SQLAlchemy for database operations
- **Real-time Communication**: Flask-SocketIO enables WebSocket connections for live chat and real-time analytics
- **RTMP Server**: Custom Python-based RTMP server handles live stream ingestion from broadcasting software
- **FFmpeg Processing**: FFmpeg manager transcodes incoming RTMP streams into web-compatible formats (HLS/DASH)
- **Stream Management**: Dedicated streaming service monitors active streams and collects performance analytics

## Database Design
- **SQLAlchemy ORM**: Uses SQLAlchemy with declarative base for database modeling
- **User Management**: Supports both regular users and broadcasters with role-based access
- **Stream Models**: Comprehensive stream tracking including analytics, chat messages, and embed settings
- **RTMP Key System**: Secure key generation and management for stream authentication

## Frontend Architecture
- **Server-side Rendering**: Traditional Flask template rendering with Jinja2
- **Bootstrap 5 UI**: Responsive design framework for consistent styling
- **Video.js Player**: Professional video player supporting multiple streaming protocols
- **Real-time Updates**: JavaScript Socket.IO client for live features like chat and viewer counts
- **Modular JavaScript**: Separate JS files for dashboard, streaming, chat, and embed functionality

## Authentication & Security
- **Session-based Authentication**: Flask sessions with secure secret key management
- **Password Hashing**: Werkzeug security for password protection
- **Stream Key Validation**: Secure stream key generation and validation system
- **CORS Configuration**: Properly configured for embed functionality across domains

## Stream Processing Pipeline
- **RTMP Ingestion**: Custom RTMP server accepts streams from OBS/broadcasting software
- **Multi-format Output**: FFmpeg converts streams to both HLS and DASH formats
- **File Management**: Organized output directory structure for stream segments
- **Quality Control**: Automatic quality detection and bandwidth monitoring

## Deployment Architecture
- **Automated Installation**: Complete deployment script with SSL certificate automation
- **Production Server**: Nginx reverse proxy with SSL termination and security headers
- **Process Management**: Supervisor handles application and RTMP server processes
- **Database**: PostgreSQL with automated setup and user creation
- **Security**: UFW firewall configuration with proper port management
- **SSL Certificates**: Let's Encrypt with DNS verification via Cloudflare API
- **Monitoring**: Comprehensive logging and service health monitoring

## External Dependencies

- **FFmpeg**: Video processing and transcoding engine for stream format conversion
- **Video.js**: HTML5 video player library with adaptive streaming support
- **Bootstrap 5**: CSS framework for responsive UI components
- **Font Awesome**: Icon library for user interface elements
- **Socket.IO**: Real-time bidirectional communication library
- **SQLite/PostgreSQL**: Database backend (configurable via DATABASE_URL environment variable)
- **Flask Extensions**: 
  - Flask-SQLAlchemy for database ORM
  - Flask-SocketIO for WebSocket support
  - Flask-CORS for cross-origin resource sharing
  - Flask-Login for user session management