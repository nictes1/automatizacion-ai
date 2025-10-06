# Google Calendar Credentials

This directory contains the OAuth 2.0 credentials for Google Calendar integration.

## Setup Instructions

1. Download your OAuth 2.0 credentials JSON from Google Cloud Console
2. Save it as: `google_oauth_credentials.json` in this directory
3. The file will be automatically mounted in Docker containers

## Expected JSON Structure

The downloaded JSON should look like this:

```json
{
  "web": {
    "client_id": "YOUR_CLIENT_ID.apps.googleusercontent.com",
    "project_id": "pulpo",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
    "client_secret": "YOUR_CLIENT_SECRET",
    "redirect_uris": ["http://localhost:8005/config/calendar/callback"]
  }
}
```

**Note:** This file is excluded from git via `.gitignore` to protect your credentials.
