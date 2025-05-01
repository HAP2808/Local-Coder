import os
from PIL import Image, ImageDraw, ImageFont

def create_icon():
    """Create a simple icon for LocalCoder application"""
    # Image sizes for the icon
    sizes = [16, 32, 48, 64, 128, 256]
    
    # Create base image (largest size first)
    size = max(sizes)
    image = Image.new("RGBA", (size, size), color=(0, 120, 215, 255))  # Windows blue
    
    # Create draw object
    draw = ImageDraw.Draw(image)
    
    # Load font or use default
    try:
        font_size = int(size * 0.5)
        font = ImageFont.truetype("arial.ttf", font_size)
    except Exception:
        font = ImageFont.load_default()
    
    # Draw text
    text = "LC"
    
    # Calculate text size - different methods based on PIL version
    try:
        # For newer PIL versions
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
    except AttributeError:
        # For older PIL versions
        try:
            text_width, text_height = draw.textsize(text, font=font)
        except AttributeError:
            # Fallback
            text_width = int(size * 0.5)
            text_height = int(size * 0.5)
    
    # Center text
    x = (size - text_width) // 2
    y = (size - text_height) // 2
    
    # Draw the text
    draw.text((x, y), text, fill=(255, 255, 255, 255), font=font)
    
    # Save as ICO
    try:
        # Try to save with multiple sizes
        images = []
        for s in sizes:
            if s != size:
                # Resize for each required dimension
                img_resized = image.resize((s, s), Image.LANCZOS if hasattr(Image, 'LANCZOS') else Image.ANTIALIAS)
                images.append(img_resized)
        
        # Save with all sizes
        image.save("icon.ico", format="ICO", sizes=[(s, s) for s in sizes])
        print("Icon created: icon.ico")
    except Exception as e:
        # Fallback to simple save
        print(f"Error creating multi-size icon: {e}")
        image.save("icon.ico", format="ICO")
        print("Created simple icon: icon.ico")

if __name__ == "__main__":
    create_icon() 