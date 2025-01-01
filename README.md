# Video Downloader

A web application for downloading videos from YouTube and Instagram. Built with Flask and modern web technologies.

## Features

- Download videos from YouTube and Instagram
- Select video quality
- Multiple video download support
- Progress tracking
- Modern, responsive UI

## Local Development

1. Clone the repository:
```bash
git clone <your-repo-url>
cd video-downloader
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Run the application:
```bash
python app.py
```

The application will be available at `http://localhost:5000`

## Deployment

### Prerequisites

- Python 3.9+
- Git
- Heroku CLI (for Heroku deployment)

### Deploying to Heroku

1. Create a Heroku account at https://signup.heroku.com/

2. Install Heroku CLI and login:
```bash
heroku login
```

3. Create a new Heroku app:
```bash
heroku create your-app-name
```

4. Push to Heroku:
```bash
git push heroku main
```

5. Ensure at least one instance is running:
```bash
heroku ps:scale web=1
```

### Environment Variables

Set the following environment variables in your deployment:

- `SECRET_KEY`: A secret key for Flask sessions
- `DOWNLOAD_FOLDER`: Path to store downloaded videos temporarily

### Security Notes

- The application uses temporary storage for downloads
- Files are cleaned up after download
- Rate limiting is recommended for production use
- Consider implementing user authentication for public deployment

## License

MIT License - See LICENSE file for details
