"""Generate a simple native dish/link icon for the Windows executable."""
from pathlib import Path
from PIL import Image, ImageDraw


def main():
    output = Path(__file__).resolve().parents[1] / "build"
    output.mkdir(exist_ok=True)
    image = Image.new("RGBA", (256, 256), (15, 23, 42, 255))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((8, 8, 248, 248), radius=45, fill=(15, 23, 42), outline=(71, 85, 105), width=5)
    draw.line((77, 115, 144, 193), fill=(226, 232, 240), width=14)
    draw.line((131, 165, 131, 210), fill=(226, 232, 240), width=12)
    draw.line((90, 210, 173, 210), fill=(226, 232, 240), width=12)
    draw.arc((36, 39, 174, 174), start=45, end=145, fill=(56, 189, 248), width=22)
    draw.line((108, 134, 176, 70), fill=(56, 189, 248), width=9)
    draw.ellipse((165, 57, 186, 78), fill=(167, 139, 250))
    draw.arc((146, 35, 210, 100), start=270, end=360, fill=(167, 139, 250), width=8)
    draw.arc((146, 13, 233, 100), start=270, end=360, fill=(167, 139, 250), width=8)
    image.save(output / "jockstrap.ico", sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])


if __name__ == "__main__":
    main()
