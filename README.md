# ID Card Generator - FastAPI Web Application

A lightweight web application that generates custom PDF ID cards by overlaying user details and photos on a template image. Perfect for badge generation, identity verification cards, or custom documentation.

## Features

- 🖼️ **Photo Upload**: Support for JPEG and PNG formats (up to 5 MB)
- 📝 **Form Input**: Collect name, date of birth, and address
- 🎨 **Smart Layout**: 
  - Left side: Photo, name, and DOB
  - Right side: Address with automatic text wrapping
- 📄 **PDF Generation**: Automatic PDF creation with embedded processed image
- ⚡ **Lightweight**: Optimized for Render's free tier (512 MB memory)
- 🔒 **Secure**: File type and size validation
- 🌐 **Mobile Friendly**: Responsive Bootstrap design

## Technology Stack

- **Backend**: FastAPI + Uvicorn
- **Image Processing**: Pillow (PIL)
- **PDF Generation**: ReportLab
- **Frontend**: HTML5 + Bootstrap 5
- **Deployment**: Render.com (free tier)

## Local Setup

### Prerequisites

- Python 3.11+
- pip or virtual environment manager

### Installation

1. **Clone or navigate to the project**
   ```bash
   cd waseem-aadhar
   ```

2. **Create virtual environment** (optional but recommended)
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate  # On macOS/Linux
   # or
   .venv\Scripts\activate  # On Windows
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the application**
   ```bash
   python main.py
   ```

   The app will start on `http://localhost:8000`

5. **Access the web form**
   - Open browser: http://localhost:8000
   - Fill in the form with:
     - Full Name
     - Date of Birth
     - Address
     - Photo file (JPEG or PNG)
   - Click "Generate ID Card PDF"
   - PDF will download automatically

## Project Structure

```
waseem-aadhar/
├── main.py                 # FastAPI application & image processing logic
├── requirements.txt        # Python dependencies
├── runtime.txt            # Python version for Render
├── render.yaml            # Render deployment configuration
├── .gitignore             # Git ignore rules
├── CardTemplate.jpeg      # Base template image for overlay
└── templates/
    └── index.html         # Web form UI
```

## Deployment on Render

### Step-by-Step Deployment

1. **Prepare GitHub Repository**
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git branch -M main
   git remote add origin https://github.com/YOUR_USERNAME/waseem-aadhar.git
   git push -u origin main
   ```

2. **Create Render Service**
   - Go to [render.com](https://render.com) and sign up/login
   - Click **"New +"** → **"Web Service"**
   - Connect your GitHub repository
   - Select the branch (main)

3. **Configure Service**
   - **Name**: `id-card-generator` (or your preference)
   - **Runtime**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`
   - **Plan**: Free tier (512 MB memory, ephemeral storage)

4. **Optional**: Use `render.yaml` for Infrastructure as Code
   - Render will automatically detect and use `render.yaml` during deployment
   - Ensures consistent deployment configuration

5. **Deploy**
   - Click **"Deploy"**
   - Wait for build and deployment to complete
   - Your app will be live at a URL like: `https://id-card-generator-xxxx.onrender.com`

### Important Notes for Render Free Tier

- **Ephemeral Filesystem**: All uploaded files are temporary (stored in memory)
- **Cold Start**: Service spins down after 15 minutes of inactivity (~30s cold start)
- **Memory**: 512 MB shared among app + dependencies (sufficient for this app)
- **No Background Jobs**: All processing is synchronous (ideal for this use case)
- **Data Persistence**: No permanent storage (by design - PDFs generated on-demand)

## API Endpoints

### GET `/`
Serves the HTML form for ID card generation.

```
Response: HTML form page
```

### POST `/generate`
Generates and returns PDF ID card.

**Parameters** (form data):
- `name` (text, required): User's full name (2-100 chars)
- `dob` (date, required): Date of birth (YYYY-MM-DD format)
- `address` (text, required): Complete address (5-300 chars)
- `photo` (file, required): Photo image (JPEG/PNG, max 5 MB)

**Response**: PDF file (application/pdf)

**Example with cURL**:
```bash
curl -X POST http://localhost:8000/generate \
  -F "name=John Doe" \
  -F "dob=1990-05-15" \
  -F "address=123 Main St, City, State 12345" \
  -F "photo=@photo.jpg" \
  --output id_card.pdf
```

### GET `/health`
Health check endpoint for monitoring (returns `{"status": "ok"}`).

## Customization

### Modify Template Layout

Edit the coordinate calculations in `main.py` function `process_card_image()`:
- **Left side width**: Adjust `left_ratio = 0.5` (50% default)
- **Photo size**: Modify `photo_height = int(template_height * 0.6)`
- **Text positions**: Change `text_y`, `dob_y`, `address_y` values

### Change Fonts

Modify `get_font()` function in `main.py`:
```python
font_names = [
    "/path/to/custom/font.ttf",  # Your custom font
    # ... fallback fonts
]
```

### Adjust File Size Limits

In `main.py`:
```python
MAX_FILE_SIZE = 5 * 1024 * 1024  # Change to desired size
```

## Troubleshooting

### "Template not found" error
- Ensure `CardTemplate.jpeg` is in the root project directory
- Check file naming (case-sensitive on Linux/macOS)

### "Only JPEG and PNG images are supported"
- Convert image to JPEG or PNG
- Check MIME type of uploaded file

### Memory issues on Render
- Reduce maximum file size limit
- Optimize CardTemplate.jpeg (reduce resolution)
- Implement image compression before overlay

### Cold start delays
- Expected behavior on Render free tier (happens after 15 min inactivity)
- Add `/health` endpoint check in monitoring
- Consider upgrading to paid tier for consistent performance

## Performance Considerations

- **Processing Time**: ~1-2 seconds per PDF (typical)
- **Memory Usage**: ~50-100 MB per request
- **Concurrent Users**: 1-3 on free tier (512 MB limit)
- **Image Size**: Recommend CardTemplate.jpeg < 2 MB

## License

MIT License - Feel free to use and modify this project.

## Support

For issues or questions:
1. Check the [Troubleshooting](#troubleshooting) section
2. Review FastAPI documentation: https://fastapi.tiangolo.com/
3. Check Render documentation: https://render.com/docs

---

**Ready to Deploy?** Push your code to GitHub and connect your repository to Render for automatic deployments! 🚀
