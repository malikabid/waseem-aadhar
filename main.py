"""
FastAPI ID Card Generator Application
Generates PDF ID cards by overlaying user details and photo on a template image.
"""

import os
import io
import logging
import random
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.templating import Jinja2Templates
from fastapi.requests import Request
from fastapi.staticfiles import StaticFiles
from PIL import Image, ImageDraw, ImageFont
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader

# Configuration
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB
TEMPLATE_PATH = Path(__file__).parent / "CardTemplate.jpeg"
PLACEHOLDER_PATH = Path(__file__).parent / "placeholder-man.webp"
ALLOWED_FORMATS = {"image/jpeg", "image/png", "image/webp"}

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI app setup
app = FastAPI(
    title="ID Card Generator",
    description="Generate custom ID cards with photo and personal details",
    version="1.0.0"
)

# Setup templates
templates_dir = Path(__file__).parent / "templates"
if not templates_dir.exists():
    templates_dir.mkdir(parents=True, exist_ok=True)

templates = Jinja2Templates(directory=str(templates_dir))

# Mount static files for offline capability
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


# Routes
@app.get("/", tags=["Form"])
async def get_form(request: Request):
    """Serve the main form page."""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint for Render monitoring."""
    return {"status": "ok"}


def generate_aadhar_number() -> str:
    """
    Generate a random 12-digit Aadhar number in XXXX XXXX XXXX format.
    
    Returns:
        Aadhar number as string in format: XXXX XXXX XXXX
    """
    aadhar = ''.join([str(random.randint(0, 9)) for _ in range(12)])
    return f"{aadhar[:4]} {aadhar[4:8]} {aadhar[8:12]}"


@app.post("/generate", tags=["Generate"])
async def generate_id_card(
    name: str = Form(..., min_length=2, max_length=100),
    dob: str = Form(...),
    gender: str = Form(...),
    address: str = Form(..., min_length=5, max_length=300),
    output_format: str = Form("png"),
    photo: Optional[UploadFile] = File(None)
) -> StreamingResponse:
    """
    Generate ID card PDF from user details and photo.
    
    Args:
        name: Full name of the person
        dob: Date of birth (YYYY-MM-DD format)
        gender: Gender (Male/Female/Other)
        address: Complete address
        photo: Uploaded photo file (optional, uses placeholder if not provided)
        
    Returns:
        PDF file as streaming response
    """
    try:
        # Handle photo - use placeholder if not provided
        if photo and photo.filename:
            # Validate file size
            photo_content = await photo.read()
            if len(photo_content) > MAX_FILE_SIZE:
                raise HTTPException(
                    status_code=400,
                    detail="File size exceeds maximum allowed size of 5 MB"
                )
            
            # Validate file type
            if photo.content_type not in ALLOWED_FORMATS:
                raise HTTPException(
                    status_code=400,
                    detail="Only JPEG, PNG, and WEBP images are supported"
                )
        else:
            # Use placeholder image
            if not PLACEHOLDER_PATH.exists():
                raise FileNotFoundError(f"Placeholder image not found at {PLACEHOLDER_PATH}")
            with open(PLACEHOLDER_PATH, "rb") as f:
                photo_content = f.read()
        
        # Generate random Aadhar number
        aadhar_number = generate_aadhar_number()
        
        # Process the image
        card_image = process_card_image(
            photo_content=photo_content,
            name=name,
            dob=dob,
            gender=gender,
            address=address,
            aadhar_number=aadhar_number
        )
        
        # Generate PDF or PNG
        output_format = output_format.lower().strip()
        if output_format == "pdf":
            file_bytes = create_pdf(card_image)
            media_type = "application/pdf"
            ext = "pdf"
        else:
            img_buf = io.BytesIO()
            card_image.convert("RGB").save(img_buf, format="PNG")
            file_bytes = img_buf.getvalue()
            media_type = "image/png"
            ext = "png"

        filename = f"id_card_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{ext}"
        return StreamingResponse(
            iter([file_bytes]),
            media_type=media_type,
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating ID card: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to generate ID card. Please try again."
        )


def process_card_image(
    photo_content: bytes,
    name: str,
    dob: str,
    gender: str,
    address: str,
    aadhar_number: str
) -> Image.Image:
    """
    Process the card template to create an ID card matching reference design.
    
    Layout:
    - LEFT HALF: Photo rectangle + Name/DOB/Gender on right of photo
    - RIGHT HALF: ADDRESS section
    
    Args:
        photo_content: Raw photo file content
        name: Full name
        dob: Date of birth
        gender: Gender
        address: Address
        aadhar_number: Aadhar number in format XXXX XXXX XXXX
        
    Returns:
        PIL Image object with overlay
    """
    
    # ==========================================
    # LAYOUT CONFIGURATION
    # All coordinates are absolute pixel positions based on the 672x294 px template.
    # Text and aadhar positions are fully independent of photo size.
    # ==========================================

    TEXT_FONT_SIZE = 14
    LINE_SPACING   = 5
    LINE_HEIGHT    = TEXT_FONT_SIZE + LINE_SPACING  # 19 px per line

    # Photo slot — top-left anchor + max bounding box (aspect ratio always preserved)
    PHOTO_SLOT_X = 35
    PHOTO_SLOT_Y = 90
    PHOTO_MAX_W  = 100   # Hard cap: photo width will never exceed this
    PHOTO_MAX_H  = 100   # Hard cap: photo height will never exceed this

    # Left text block (Name / DOB / Gender) — fixed, never moves with photo
    TEXT_X = 160
    TEXT_Y = 95

    # Aadhar number row — fixed Y near bottom of content area, both sides
    AADHAR_LEFT_X  = 145
    AADHAR_RIGHT_X = 430
    AADHAR_Y       = 195

    # Right side address block — fixed position
    ADDRESS_X = 386
    ADDRESS_Y = 95

    # ==========================================

    try:
        if not TEMPLATE_PATH.exists():
            raise FileNotFoundError(f"Card template not found at {TEMPLATE_PATH}")

        template = Image.open(TEMPLATE_PATH).convert("RGBA")
        logger.info(f"Template size: {template.size}")

        photo = Image.open(io.BytesIO(photo_content)).convert("RGB")
        logger.info(f"Photo size: {photo.size}")

        draw = ImageDraw.Draw(template)
        template_width, template_height = template.size

        # ===== PHOTO — scale to fit within PHOTO_MAX_W x PHOTO_MAX_H, preserve aspect ratio =====
        photo_aspect = photo.width / photo.height
        if photo_aspect >= 1:  # landscape or square — width is the limiting dimension
            resized_w = PHOTO_MAX_W
            resized_h = int(PHOTO_MAX_W / photo_aspect)
        else:                  # portrait — height is the limiting dimension
            resized_h = PHOTO_MAX_H
            resized_w = int(PHOTO_MAX_H * photo_aspect)
        logger.info(f"Photo resized to {resized_w}x{resized_h} (max {PHOTO_MAX_W}x{PHOTO_MAX_H})")
        photo_resized = photo.resize((resized_w, resized_h), Image.Resampling.LANCZOS)
        template.paste(photo_resized, (PHOTO_SLOT_X, PHOTO_SLOT_Y))

        text_font = get_font(size=TEXT_FONT_SIZE, bold=False)

        # ===== LEFT TEXT BLOCK — absolute coords, independent of photo =====
        draw.text((TEXT_X, TEXT_Y),                  name[:30],                    font=text_font, fill=(0, 0, 0, 255))
        draw.text((TEXT_X, TEXT_Y + LINE_HEIGHT),     f"DOB: {format_date_dob(dob)}", font=text_font, fill=(0, 0, 0, 255))
        draw.text((TEXT_X, TEXT_Y + LINE_HEIGHT * 2), f"Gender: {gender}",          font=text_font, fill=(0, 0, 0, 255))

        # ===== AADHAR NUMBER — fixed row, both sides =====
        draw.text((AADHAR_LEFT_X,  AADHAR_Y), aadhar_number, font=text_font, fill=(0, 0, 0, 255))
        draw.text((AADHAR_RIGHT_X, AADHAR_Y), aadhar_number, font=text_font, fill=(0, 0, 0, 255))

        # ===== RIGHT SIDE ADDRESS — fixed position =====
        address_parts = [part.strip() for part in address.split(",") if part.strip()]

        label_prefix = "ADDRESS : "
        prefix_bbox  = draw.textbbox((0, 0), label_prefix, font=text_font)
        prefix_width = prefix_bbox[2] - prefix_bbox[0]
        indent_x     = ADDRESS_X + prefix_width
        indent_width = template_width - indent_x - 20

        if address_parts:
            first_suffix = address_parts[0] + ("," if len(address_parts) > 1 else "")
            draw.text((ADDRESS_X, ADDRESS_Y), label_prefix + first_suffix, font=text_font, fill=(0, 0, 0, 255))
            addr_y = ADDRESS_Y + LINE_HEIGHT
            for part in address_parts[1:]:
                draw_wrapped_text(
                    draw=draw, text=part, x=indent_x, y=addr_y,
                    font=text_font, fill=(0, 0, 0, 255),
                    max_width=indent_width, line_spacing=LINE_SPACING
                )
                addr_y += LINE_HEIGHT
        else:
            draw.text((ADDRESS_X, ADDRESS_Y), label_prefix, font=text_font, fill=(0, 0, 0, 255))

        return template.convert("RGB")

    except Exception as e:
        logger.error(f"Error processing card image: {str(e)}", exc_info=True)
        raise


def draw_wrapped_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    x: float,
    y: float,
    font: ImageFont.FreeTypeFont,
    fill: tuple,
    max_width: float,
    line_spacing: int = 6
) -> None:
    """
    Draw text with word wrapping on image.
    
    Args:
        draw: ImageDraw object
        text: Text to draw
        x: X coordinate
        y: Y coordinate
        font: Font to use
        fill: Color (RGBA tuple)
        max_width: Maximum width before wrapping
        line_spacing: Space between lines in pixels
    """
    words = text.split()
    lines = []
    current_line = []
    
    for word in words:
        test_line = " ".join(current_line + [word])
        bbox = draw.textbbox((0, 0), test_line, font=font)
        line_width = bbox[2] - bbox[0]
        
        if line_width <= max_width:
            current_line.append(word)
        else:
            if current_line:
                lines.append(" ".join(current_line))
            current_line = [word]
    
    if current_line:
        lines.append(" ".join(current_line))
    
    # Draw all lines
    current_y = y
    for line in lines:
        draw.text((x, current_y), line, font=font, fill=fill)
        current_y += font.size + line_spacing


_FONT_CDN_BASE = "https://cdn.jsdelivr.net/npm/dejavu-fonts-ttf@2.37.3/ttf"
_FONT_FILES = {
    "regular": "DejaVuSans.ttf",
    "bold": "DejaVuSans-Bold.ttf",
}


def _ensure_font(font_filename: str, dest_dir: Path) -> Path | None:
    """
    Ensure a font file exists locally; download from CDN if missing.

    Args:
        font_filename: TTF filename (e.g. 'DejaVuSans.ttf')
        dest_dir: Directory to save the font

    Returns:
        Path to the font file, or None if unavailable
    """
    dest_path = dest_dir / font_filename
    if dest_path.exists():
        return dest_path

    # Try to download from jsDelivr CDN
    url = f"{_FONT_CDN_BASE}/{font_filename}"
    try:
        dest_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Downloading font from CDN: {url}")
        urllib.request.urlretrieve(url, str(dest_path))
        logger.info(f"Font saved to {dest_path}")
        return dest_path
    except Exception as e:
        logger.warning(f"Could not download font {font_filename} from CDN: {e}")
        return None


def get_font(size: int = 20, bold: bool = False) -> ImageFont.FreeTypeFont:
    """
    Get a TrueType font (DejaVu Sans).
    Checks bundled fonts first; falls back to CDN download, then system fonts.

    Args:
        size: Font size
        bold: Whether to use bold variant

    Returns:
        PIL Font object
    """
    font_filename = _FONT_FILES["bold"] if bold else _FONT_FILES["regular"]
    bundled_font_dir = Path(__file__).parent / "static" / "fonts"

    # 1. Try bundled font (or download from CDN into bundle dir)
    font_path = _ensure_font(font_filename, bundled_font_dir)
    if font_path:
        try:
            return ImageFont.truetype(str(font_path), size=size)
        except Exception as e:
            logger.warning(f"Failed to load bundled font {font_path}: {e}")

    # 2. Try system fonts
    system_fonts = [
        f"/usr/share/fonts/truetype/dejavu/{font_filename}",   # Linux (Render)
        f"/System/Library/Fonts/Supplemental/Arial{'Bold' if bold else ''}.ttf",  # macOS
        "/Library/Fonts/Arial.ttf",                             # macOS alternate
        "C:\\Windows\\Fonts\\arial.ttf",                        # Windows
    ]
    for path in system_fonts:
        try:
            if os.path.exists(path):
                return ImageFont.truetype(path, size=size)
        except Exception:
            continue

    # 3. Last resort: PIL default (bitmap) font
    logger.warning("Could not load TrueType font, using PIL default")
    return ImageFont.load_default()


def format_date(date_str: str) -> str:
    """
    Format date string from YYYY-MM-DD to readable format.
    
    Args:
        date_str: Date in YYYY-MM-DD format
        
    Returns:
        Formatted date string (e.g., "15 Feb 2001")
    """
    try:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        return date_obj.strftime("%d %b %Y")
    except ValueError as e:
        logger.error(f"Error formatting date: {str(e)}")
        return date_str


def format_date_dob(date_str: str) -> str:
    """
    Format date string from YYYY-MM-DD to dd/mm/yyyy format.
    
    Args:
        date_str: Date in YYYY-MM-DD format
        
    Returns:
        Formatted date string (e.g., "15/02/2001")
    """
    try:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        return date_obj.strftime("%d/%m/%Y")
    except ValueError as e:
        logger.error(f"Error formatting date: {str(e)}")
        return date_str


def create_pdf(image: Image.Image) -> bytes:
    """
    Create PDF from PIL Image.
    
    Args:
        image: PIL Image object
        
    Returns:
        PDF file content as bytes
    """
    try:
        # Convert image to RGB if necessary
        if image.mode != "RGB":
            image = image.convert("RGB")
        
        # Create PDF
        pdf_buffer = io.BytesIO()
        c = canvas.Canvas(pdf_buffer, pagesize=letter)
        
        # Get image dimensions
        img_width, img_height = image.size
        
        # Calculate scaling to fit on letter size page (8.5 x 11 inches)
        page_width, page_height = letter
        max_width = page_width - 0.5 * inch
        max_height = page_height - 0.5 * inch
        
        # Calculate aspect ratio
        aspect_ratio = img_width / img_height
        
        # Determine final dimensions
        if aspect_ratio > (max_width / max_height):
            # Width is limiting factor
            final_width = max_width
            final_height = max_width / aspect_ratio
        else:
            # Height is limiting factor
            final_height = max_height
            final_width = max_height * aspect_ratio
        
        # Center image on page
        x = (page_width - final_width) / 2
        y = (page_height - final_height) / 2
        
        # Save image to bytes buffer
        img_bytes = io.BytesIO()
        image.save(img_bytes, format="PNG")
        img_bytes.seek(0)
        
        # Use ImageReader to handle the image
        img_reader = ImageReader(img_bytes)
        c.drawImage(
            img_reader,
            x,
            y,
            width=final_width,
            height=final_height,
            preserveAspectRatio=True
        )
        
        c.save()
        pdf_buffer.seek(0)
        
        return pdf_buffer.getvalue()
        
    except Exception as e:
        logger.error(f"Error creating PDF: {str(e)}", exc_info=True)
        raise


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8000)),
        log_level="info"
    )
