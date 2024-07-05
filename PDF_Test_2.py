import fitz  # PyMuPDF
import pytesseract
from PIL import Image
import io
import argparse
import re


def rotate_coordinates(x, y, rotation, page_width, page_height):
    if rotation == 90:
        return page_height - y, x
    elif rotation == 180:
        return page_width - x, page_height - y
    elif rotation == 270:
        return y, page_width - x
    else:
        return x, y


def extract_text_with_coordinates(pdf_path):
    # Open the PDF file
    document = fitz.open(pdf_path)
    text_blocks = []

    # Iterate through each page
    for page_num in range(len(document)):
        page = document.load_page(page_num)
        rotation = page.rotation
        page_width, page_height = page.rect.width, page.rect.height
        # Extract text as blocks
        blocks = page.get_text("dict")["blocks"]

        # Calculate total text length
        total_text_length = sum(
            len(span["text"]) for block in blocks if 'lines' in block for line in block["lines"] for span in
            line["spans"])

        if total_text_length < 30:  # Check if text is empty or less than 30 characters
            print(f"Page {page_num + 1}: Text is empty or less than 30 characters, performing OCR.")
            ocr_text_blocks = perform_ocr(page, rotation, page_width, page_height)
            text_blocks.extend(ocr_text_blocks)
        else:
            for block in blocks:
                if block['type'] == 0 and 'lines' in block:  # block type 0 means text
                    for line in block["lines"]:
                        for span in line["spans"]:
                            text = span["text"]
                            bbox = span["bbox"]  # Bounding box coordinates (x0, y0, x1, y1)
                            x, y = rotate_coordinates(bbox[0], bbox[1], rotation, page_width, page_height)
                            text_blocks.append([x, y, text])
    return text_blocks


def perform_ocr(page, rotation, page_width, page_height):
    # Convert PDF page to image
    pix = page.get_pixmap()
    img = Image.open(io.BytesIO(pix.pil_tobytes(format="png")))

    # Perform OCR
    ocr_result = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
    text_blocks = []
    for i in range(len(ocr_result['level'])):
        text = ocr_result['text'][i]
        if text.strip():  # Only consider non-empty text
            x, y = rotate_coordinates(ocr_result['left'][i], ocr_result['top'][i], rotation, page_width, page_height)
            text_blocks.append([x, y, text])
    return text_blocks


def search_and_filter(text_blocks, search_terms, x_threshold=30, y_threshold=30):
    results = []

    # Search for any of the terms
    search_positions = []
    for x, y, text in text_blocks:
        for term in search_terms:
            if term.lower() in text.lower():
                search_positions.append([x, y, text])
                break  # Stop checking other terms if one is found

    # Find nearby text below or at the same level as the search term
    for sx, sy, stext in search_positions:
        nearby_texts = []
        for x, y, text in text_blocks:
            if [sx, sy, stext] != [x, y, text] and y >= sy:  # Ensure the text is below or at the same level as the search term
                dx = abs(sx - x)
                dy = abs(sy - y)
                if dx <= x_threshold and dy <= y_threshold:
                    nearby_texts.append([x, y, text])
        # Only add to results if there's at least one nearby text
        if nearby_texts:
            results.extend([[sx, sy, stext, x, y, text] for x, y, text in nearby_texts])

    return results


def incremental_search(text_blocks, search_terms, x_increment=1, y_increment=3, max_iterations=100, required_results=3):
    search_positions = []

    # Identify positions of search terms
    for x, y, text in text_blocks:
        for term in search_terms:
            if term.lower() in text.lower():
                search_positions.append([x, y, text])
                break

    all_results = []

    # For each search position, incrementally search for nearby texts
    for sx, sy, stext in search_positions:
        iteration = 0
        x_threshold, y_threshold = 1, 1
        results = []

        while len(results) < required_results and iteration < max_iterations:
            results = search_and_filter(text_blocks, search_terms, x_threshold, y_threshold)
            results = [res for res in results if [res[0], res[1], res[2]] == [sx, sy, stext]]  # Filter results for the specific search position
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
    return sorted(results, key=lambda x: x[4], reverse=False)


def find_revision(text_with_coordinates):
    search_terms = ["Revision", "REVISION", "REV.", "Rev:"]
    results = incremental_search(text_with_coordinates, search_terms, 1, 1, required_results=8)
    sorted_results = sort_results_by_y(results)
    regex_pattern = r'\b[A-Z]{1,2}\d{0,2}\b'  # Updated regex pattern to match only 1-3 characters

    # Apply regex to find the first valid match
    for result in sorted_results:
        text_to_match = result[5]
        if len(text_to_match) <= 3:  # Disregard any strings longer than 3 characters
            match = re.match(regex_pattern, text_to_match)
            if match:
                return [result]  # Return the matching list
    return []  # Return an empty list if no match is found


def find_drawing_number(text_with_coordinates):
    search_terms = ["Drawing Number", "BDP Drawing Number", "DRG NO", "Drawing No", "No."]
    results = incremental_search(text_with_coordinates, search_terms, 1, 3, required_results=3)

    for item in results:
        print(item)

    # Sort results by Y-coordinate first
    sorted_results = sort_results_by_y(results)
    regex_pattern = r'\b(?:[A-Z0-9]+[-/])+(?:\([0-9]+\))?[A-Z0-9_]+(?:[-/][A-Z0-9]+)*\b'  # Example regex pattern for drawing numbers

    for item in sorted_results:
        print(item)

    # Apply regex to find the first valid match
    for result in sorted_results:
        text_to_match = result[5]
        match = re.match(regex_pattern, text_to_match)
        if match:
            return [result]  # Return the matching list
    return []  # Return an empty list if no match is found



if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Process a PDF to extract text and coordinates.')
    parser.add_argument('pdf_path', type=str, help='Path to the PDF file')
    args = parser.parse_args()

    text_with_coordinates = extract_text_with_coordinates(args.pdf_path)
    revision = find_revision(text_with_coordinates)
    for item in revision:
        print(item)
    drawing_number = find_drawing_number(text_with_coordinates)
    for item in drawing_number:
        print(item)
    #print(revision[0][5])
    # for item in text_with_coordinates:
    #     print(item[2])
