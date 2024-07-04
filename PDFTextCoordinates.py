import fitz  # PyMuPDF
import pytesseract
from PIL import Image
import io
import argparse

def extract_text_with_coordinates(pdf_path):
    # Open the PDF file
    document = fitz.open(pdf_path)
    text_blocks = []

    # Iterate through each page
    for page_num in range(len(document)):
        page = document.load_page(page_num)
        # Extract text as blocks
        blocks = page.get_text("dict")["blocks"]

        # Calculate total text length
        total_text_length = sum(len(span["text"]) for block in blocks if 'lines' in block for line in block["lines"] for span in line["spans"])

        if total_text_length < 30:  # Check if text is empty or less than 30 characters
            print(f"Page {page_num+1}: Text is empty or less than 30 characters, performing OCR.")
            ocr_text_blocks = perform_ocr(page)
            text_blocks.extend(ocr_text_blocks)
        else:
            for block in blocks:
                if block['type'] == 0 and 'lines' in block:  # block type 0 means text
                    for line in block["lines"]:
                        for span in line["spans"]:
                            text = span["text"]
                            bbox = span["bbox"]  # Bounding box coordinates (x0, y0, x1, y1)
                            x, y = bbox[0], bbox[1]
                            text_blocks.append((x, y, text))
    return text_blocks

def perform_ocr(page):
    # Convert PDF page to image
    pix = page.get_pixmap()
    img = Image.open(io.BytesIO(pix.pil_tobytes(format="png")))

    # Perform OCR
    ocr_result = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
    text_blocks = []
    for i in range(len(ocr_result['level'])):
        text = ocr_result['text'][i]
        if text.strip():  # Only consider non-empty text
            x, y = ocr_result['left'][i], ocr_result['top'][i]
            text_blocks.append((x, y, text))
    return text_blocks

def search_and_filter(text_blocks, search_terms, x_threshold=30, y_threshold=30):
    results = []

    # Search for any of the terms
    search_positions = []
    for x, y, text in text_blocks:
        for term in search_terms:
            if term.lower() in text.lower():
                search_positions.append((x, y, text))
                break  # Stop checking other terms if one is found

    # Find nearby text below or at the same level as the search term
    for sx, sy, stext in search_positions:
        nearby_texts = []
        for x, y, text in text_blocks:
            if (sx, sy, stext) != (x, y, text) and y >= sy:  # Ensure the text is below or at the same level as the search term
                dx = abs(sx - x)
                dy = abs(sy - y)
                if dx <= x_threshold and dy <= y_threshold:
                    nearby_texts.append((x, y, text))
        # Only add to results if there's at least one nearby text
        if nearby_texts:
            results.extend([(sx, sy, stext, x, y, text) for x, y, text in nearby_texts])

    return results

def incremental_search(text_blocks, search_terms, x_increment=1, y_increment=3, max_iterations=100, required_results=3):
    search_positions = []

    # Identify positions of search terms
    for x, y, text in text_blocks:
        for term in search_terms:
            if term.lower() in text.lower():
                search_positions.append((x, y, text))
                break

    all_results = []

    # For each search position, incrementally search for nearby texts
    for sx, sy, stext in search_positions:
        iteration = 0
        x_threshold, y_threshold = 1, 1
        results = []

        while len(results) < required_results and iteration < max_iterations:
            results = search_and_filter(text_blocks, search_terms, x_threshold, y_threshold)
            results = [res for res in results if (res[0], res[1], res[2]) == (sx, sy, stext)]  # Filter results for the specific search position
            if len(results) >= required_results:
                break
            x_threshold += x_increment
            y_threshold += y_increment
            iteration += 1

        all_results.extend(results[:required_results])

    return all_results


def sort_results_by_y(results):
    # Sort results by the y value of the second element in each tuple
    ##Sorting Mechanism: The sorted function in Python sorts the results list. The key=lambda x: x[4] part tells the sorted function to use the fifth element (index 4, corresponding to y in the tuple) of each tuple as the sorting key.

    return sorted(results, key=lambda x: x[4])

def find_drawing_info(file_name):
    text_with_coordinates = extract_text_with_coordinates(file_name)

    # Individual search terms
    search_settings = [
        (["Job Number", "BDP JOB NUMBER", "Job No"], 1, 3, 1),
        (["Drawing Number", "BDP Drawing Number", "DRG NO", "Drawing No"], 1, 3, 1),
        (["Revision", "REVISION", "REV.", "Rev:"], 1, 3, 1),
        (["Project Name  ", "Project Title", "Project"], 1, 3, 1),
        (["Drawing Title  ", "Title"], 1, 3, 1)
    ]

    for search_terms, x_increment, y_increment, required_results in search_settings:
        print(f"---\nSearch Terms: {search_terms}")
        results = incremental_search(text_with_coordinates, search_terms, x_increment, y_increment, required_results=required_results)

        sorted_results = sort_results_by_y(results)
        for result in sorted_results:
            print(result)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Process a PDF to extract text and coordinates.')
    parser.add_argument('pdf_path', type=str, help='Path to the PDF file')
    args = parser.parse_args()
    find_drawing_info(args.pdf_path)
