import os
import sys
from PIL import Image
from pillow_heif import register_heif_opener

# Register HEIC opener
register_heif_opener()

SOURCE_DIR = r"C:\Users\nican\Downloads\Mangata-3-001\Mangata"
DEST_DIR = r"C:\Users\nican\Downloads\Mangata-3-001\MangataJPG"

# Create destination if needed
if not os.path.exists(DEST_DIR):
    os.makedirs(DEST_DIR)
    print(f"Created directory: {DEST_DIR}")

# List files
try:
    files = os.listdir(SOURCE_DIR)
except Exception as e:
    print(f"Error accessing source directory: {e}")
    sys.exit(1)

print(f"Found {len(files)} files in source.")

count = 0
errors = 0

for filename in files:
    if filename.lower().endswith(".heic"):
        src_path = os.path.join(SOURCE_DIR, filename)
        name, _ = os.path.splitext(filename)
        dst_path = os.path.join(DEST_DIR, f"{name}.jpg")
        
        try:
            image = Image.open(src_path)
            # Convert to RGB (JPEG doesn't support RGBA)
            image = image.convert('RGB')
            image.save(dst_path, format="JPEG", quality=95)
            print(f"Converted: {filename} -> {os.path.basename(dst_path)}")
            count += 1
        except Exception as e:
            print(f"Error converting {filename}: {e}")
            errors += 1

print(f"\nFinished Conversion.")
print(f"Successfully converted: {count}")
print(f"Errors: {errors}")
