import fitz  # PyMuPDF
import pytesseract
from PIL import Image
import io
import argparse
import re


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
        total_text_length = sum(
            len(span["text"]) for block in blocks if 'lines' in block for line in block["lines"] for span in
            line["spans"])

        if total_text_length < 30:  # Check if text is empty or less than 30 characters
            print(f"Page {page_num + 1}: Text is empty or less than 30 characters, performing OCR.")
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
            if (sx, sy, stext) != (
            x, y, text) and y >= sy:  # Ensure the text is below or at the same level as the search term
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
            results = [res for res in results if
                       (res[0], res[1], res[2]) == (sx, sy, stext)]  # Filter results for the specific search position
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


def find_job_number(text_with_coordinates):
    search_terms = ["Job Number", "BDP JOB NUMBER", "Job No"]
    results = incremental_search(text_with_coordinates, search_terms, 1, 3, required_results=3)
    # Sort results by Y-coordinate first
    sorted_results = sort_results_by_y(results)
    regex_pattern = r'\b[A-Z]\d{5,7}\b'  # Example regex pattern for drawing numbers
    # Apply regex to find the first valid match
    for result in sorted_results:
        if re.match(regex_pattern, result[5]):
            return [result]  # Return as a list containing the matching tuple
    return []  # Return an empty list if no match is found


def find_drawing_number(text_with_coordinates):
    search_terms = ["Drawing Number", "BDP Drawing Number", "DRG NO", "Drawing No"]
    results = incremental_search(text_with_coordinates, search_terms, 1, 3, required_results=3)
    # Sort results by Y-coordinate first
    sorted_results = sort_results_by_y(results)
    regex_pattern = r'\b(?:[A-Z0-9]+[-/])+(?:\([0-9]+\))?[A-Z0-9_]+(?:[-/][A-Z0-9]+)*\b'  # Example regex pattern for drawing numbers
    # Apply regex to find the first valid match
    for result in sorted_results:
        if re.match(regex_pattern, result[5]):
            return [result]  # Return as a list containing the matching tuple
    return []  # Return an empty list if no match is found


def find_revision(text_with_coordinates):
    search_terms = ["Revision", "REVISION", "REV.", "Rev:"]
    results = incremental_search(text_with_coordinates, search_terms, 1, 1, required_results=3)
    # Sort results by Y-coordinate first
    sorted_results = sort_results_by_y(results)
    # Define the regex pattern to match "P01", "T01", "AF", "C1", "A" etc.
    regex_pattern = r'\b[A-Z][0-9]{1,2}\b|\b[A-Z]{1,2}\b|\b[0-9][A-Z]{1,2}\b'  # Match 1-3 characters with specific patterns
    # Apply regex to find the first valid match
    for result in sorted_results:
        if re.match(regex_pattern, result[5]):
            return [result]  # Return as a list containing the matching tuple
    return []  # Return an empty list if no match is found


def find_project_name(text_with_coordinates):
    search_terms = ["Project Name", "Project Title", "Project"]
    results = incremental_search(text_with_coordinates, search_terms, 1, 3, required_results=1)
    regex_pattern = r'\b.+\b'  # Example regex pattern for project names
    filtered_results = [result for result in results if re.search(regex_pattern, result[5])]
    sorted_results = sort_results_by_y(filtered_results)
    return sorted_results


def find_drawing_title(text_with_coordinates):
    primary_search_term = "Drawing Title"
    secondary_search_term = "Title"

    # Perform the incremental search for "Drawing Title" first
    primary_results = incremental_search(text_with_coordinates, [primary_search_term], 1, 3, required_results=3)

    # If no primary results are found, perform the incremental search for "Title"
    if not primary_results:
        secondary_results = incremental_search(text_with_coordinates, [secondary_search_term], 1, 3, required_results=3)

        # Filter out any results where "Title" is not the first word
        secondary_results = [result for result in secondary_results if
                             result[5].strip().startswith(secondary_search_term)]
    else:
        secondary_results = []

    # Combine primary and secondary results
    results = primary_results + secondary_results

    # Sort the results by Y-coordinate (assuming sort_results_by_y is defined)
    sorted_results = sort_results_by_y(results)

    # Concatenate the first two sorted values and return
    if len(sorted_results) >= 2:
        concatenated_title = sorted_results[0][5] + " " + sorted_results[1][5]
    elif len(sorted_results) == 1:
        concatenated_title = sorted_results[0][5]
    else:
        concatenated_title = ""

    return [concatenated_title]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Process a PDF to extract text and coordinates.')
    parser.add_argument('pdf_path', type=str, help='Path to the PDF file')
    args = parser.parse_args()

    text_with_coordinates = extract_text_with_coordinates(args.pdf_path)

    job_number_results = find_job_number(text_with_coordinates)
    drawing_number_results = find_drawing_number(text_with_coordinates)
    revision_results = find_revision(text_with_coordinates)
    project_name_results = find_project_name(text_with_coordinates)
    drawing_title_results = find_drawing_title(text_with_coordinates)

    print(job_number_results[0])
    # print(drawing_number_results)
    # print(revision_results)
    # print(project_name_results)
    # print(drawing_title_results)
    # all_results = job_number_results + drawing_number_results + revision_results + project_name_results + drawing_title_results
    #
    # for result in all_results:
    #     print(result)
