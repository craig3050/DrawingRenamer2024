import pymupdf  # PyMuPDF

def extract_bottom_right_text(pdf_path):
    # Open the PDF file
    xmargin = 10000
    ymargin = 10000
    document = pymupdf.open(pdf_path)

    page = document[0]
    rect = page.rect
    # Define the bottom-right rectangle area
    bottom_right_rect = pymupdf.Rect(
        rect.width - xmargin, rect.height - ymargin,  # x0, y0 (bottom-left corner of rect)
        rect.width, rect.height                     # x1, y1 (top-right corner of rect)
    )
    # Extract text from the defined rectangle
    text = page.get_text("text", clip=bottom_right_rect)
    print(f" {text.strip()}")  # For debugging


def main():
    pdf_path = 'Test_S.pdf'
    extract_bottom_right_text(pdf_path)

if __name__ == "__main__":
    main()
