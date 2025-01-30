# Video Downloader & Trimmer

A web application that allows users to download videos from YouTube and Instagram, as well as trim and compress local videos.

## Features

- Download videos from YouTube and Instagram
- Trim videos to specific durations (max 15 seconds)
- Compress videos to target file sizes
- Bulk video processing
- Real-time progress tracking
- Support for multiple video formats
- Modern, responsive UI

## Requirements

- Python 3.8+
- FFmpeg
- Chrome/Firefox for the best experience

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/video-downloader-trimmer.git
cd video-downloader-trimmer
```

2. Create a virtual environment and activate it:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install the required packages:
```bash
pip install -r requirements.txt
```

4. Install FFmpeg:
- On macOS: `brew install ffmpeg`
- On Ubuntu/Debian: `sudo apt-get install ffmpeg`
- On Windows: Download from [FFmpeg website](https://ffmpeg.org/download.html)

## Usage

1. Start the server:
```bash
python app.py
```

2. Open your browser and navigate to `http://localhost:5000`

3. Use the application:
   - To download videos: Paste video URLs in the download tab
   - To trim/compress videos: Upload videos in the trim tab

## Development

The project structure is organized as follows:

```
.
├── app.py              # Main Flask application
├── requirements.txt    # Python dependencies
├── static/            # Static files (CSS, downloads, uploads)
├── templates/         # HTML templates
│   └── index.html    # Main application template
└── README.md         # This file
```

## Contributing

1. Fork the repository
2. Create a new branch for your feature
3. Commit your changes
4. Push to your branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.
