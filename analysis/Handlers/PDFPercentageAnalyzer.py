import PyPDF2
import pandas as pd
import re
import os
import json
from uuid import uuid4
from django.conf import settings


def normalize_name(name):
    """Normalize name by removing all spaces and special characters"""
    if not name:
        return ""
    
    name = name.upper().strip()
    name = name.replace(' ', '')
    name = re.sub(r'[^A-Z]', '', name)
    
    return name


def extract_text_from_pdf(pdf_path):
    """Extract text from PDF file"""
    text = ""
    try:
        with open(pdf_path, 'rb') as pdf_file:
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            num_pages = len(pdf_reader.pages)
            
            for page_num in range(num_pages):
                page = pdf_reader.pages[page_num]
                text += page.extract_text() or ""
                   
    except Exception as e:
        return f"An error occurred: {e}"
       
    return text


def parse_subject_structure(text):
    """Parse subject codes and max marks"""
    university_pattern = r'University\s+of\s+Mumbai'
    match = re.search(university_pattern, text, re.IGNORECASE)
    
    if not match:
        for alt in [r'OFFICE\s+REGISTER', r'CBCS.*Engineering']:
            alt_match = re.search(alt, text, re.IGNORECASE)
            if alt_match:
                start_pos = alt_match.start()
                break
        else:
            return {}
    else:
        start_pos = match.start()
    
    subject_section = text[start_pos:start_pos + 5000]
    
    total_marks_map = {}
    subject_order = []
    
    pattern = r'([A-Z0-9]{5,6}(?:\s+[A-Z]{2,3})?)(?:\s*[‐\-–]\s*)([^:]+?):\s+.*?(\d{2,3})/0'
    matches = re.findall(pattern, subject_section, re.MULTILINE)
    
    for subject_code, subject_name, max_marks in matches:
        subject_code = subject_code.strip()
        if subject_code not in total_marks_map:
            total_marks_map[subject_code] = int(max_marks)
            subject_order.append(subject_code)
    
    return {code: total_marks_map[code] for code in subject_order}


def extract_marks_from_cell(cell):
    """Extract marks from cell, handles AA, --, 7F, 10E, etc."""
    cell = cell.strip()
    
    match1 = re.match(r'^([A-Z0-9]+)\s+([A-Z0-9]+)\s+([A-Z0-9]+)$', cell)
    if match1:
        val3 = match1.group(3)
        num = re.search(r'(\d+)', val3)
        return int(num.group(1)) if num else 0
    
    match2 = re.match(r'^[‐\-–]+\s+([A-Z0-9]+)\s+([A-Z0-9]+)$', cell)
    if match2:
        val2 = match2.group(2)
        num = re.search(r'(\d+)', val2)
        return int(num.group(1)) if num else 0
    
    return None


def parse_students(text, num_subjects):
    """Parse students from PDF text"""
    students = []
    
    match = re.search(r'University\s+of\s+Mumbai', text, re.IGNORECASE)
    if match:
        text = text[match.start():]
    
    lines = text.split('\n')
    
    i = 0
    while i < len(lines):
        line = lines[i]
        student_match = re.search(r'(\d{7})\s+(/\s+)?([A-Z][A-Z\s]+?)\s+\|', line)
        
        if student_match:
            seat_no = student_match.group(1)
            name = student_match.group(3).strip()
            
            marks = []
            for j in range(i, min(i + 20, len(lines))):
                cells = lines[j].split('|')
                for cell in cells:
                    mark = extract_marks_from_cell(cell)
                    if mark is not None and len(marks) < num_subjects:
                        marks.append(mark)
                if len(marks) >= num_subjects:
                    break
            
            if len(marks) >= num_subjects:
                students.append({
                    'seat_no': seat_no,
                    'name': name,
                    'normalized_name': normalize_name(name),
                    'marks': marks[:num_subjects]
                })
        
        i += 1
    
    return students


def calculate_percentages_single(students, total_marks_map):
    """Calculate percentages for single PDF"""
    total_maximum_marks = sum(total_marks_map.values())
    results = []
    
    for student in students:
        name = student['name']
        marks = student['marks']
        total_obtained = sum(marks)
        percentage = (total_obtained / total_maximum_marks) * 100
        
        results.append({
            'Name': name,
            'Percentage': round(percentage, 2)
        })
    
    return results, total_maximum_marks


def calculate_percentages_multiple(students, total_marks_map):
    """Calculate percentages for multiple PDFs (returns dict with normalized names)"""
    total_maximum_marks = sum(total_marks_map.values())
    results = {}
    
    for student in students:
        normalized_name = student['normalized_name']
        original_name = student['name']
        marks = student['marks']
        total_obtained = sum(marks)
        percentage = (total_obtained / total_maximum_marks) * 100
        
        results[normalized_name] = {
            'original_name': original_name,
            'percentage': round(percentage, 2)
        }
    
    return results


def merge_results(sem1_data, sem2_data):
    """Merge SEM1 and SEM2 results with space-agnostic matching"""
    all_normalized_names = set(sem1_data.keys()) | set(sem2_data.keys())
    
    results = []
    
    for normalized_name in sorted(all_normalized_names):
        sem1_info = sem1_data.get(normalized_name)
        sem2_info = sem2_data.get(normalized_name)
        
        if sem1_info:
            display_name = sem1_info['original_name']
            sem1_percent = sem1_info['percentage']
        else:
            display_name = sem2_info['original_name'] if sem2_info else normalized_name
            sem1_percent = None
        
        sem2_percent = sem2_info['percentage'] if sem2_info else None
        
        if sem1_percent is not None and sem2_percent is not None:
            average = round((sem1_percent + sem2_percent) / 2, 2)
        else:
            average = None
        
        results.append({
            'Name': display_name,
            'Percentage Sem1': sem1_percent,
            'Percentage Sem2': sem2_percent,
            'Average': average
        })
    
    return results


def analyze_single_pdf(file):
        """
        Analyze a single PDF.
        Returns: results, json_url, excel_url
        """
        # Step 1: Save uploaded PDF
        upload_dir_name = "uploads"
        upload_dir = os.path.join(settings.MEDIA_ROOT, upload_dir_name)
        os.makedirs(upload_dir, exist_ok=True)

        file_id = uuid4()
        pdf_path = os.path.join(upload_dir, f"{file_id}.pdf")
        with open(pdf_path, "wb") as f:
            for chunk in file.chunks():
                f.write(chunk)

        # Step 2: Extract text
        extracted_text = extract_text_from_pdf(pdf_path)
        if "error" in extracted_text.lower():
            raise ValueError(f"PDF extraction error: {extracted_text}")

        # Step 3: Parse subjects
        total_marks_map = parse_subject_structure(extracted_text)
        if not total_marks_map:
            raise ValueError("Could not parse subjects from PDF.")

        num_subjects = len(total_marks_map)

        # Step 4: Parse students
        students = parse_students(extracted_text, num_subjects)
        if not students:
            raise ValueError("No student data found in PDF.")

        # Step 5: Calculate percentages
        results, _ = calculate_percentages_single(students, total_marks_map)

        # Step 6: Save Excel
        excel_path = os.path.join(upload_dir, f"{file_id}.xlsx")
        df = pd.DataFrame(results)
        try:
            with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='Results', index=False)
                subject_df = pd.DataFrame([
                    {'Subject Code': code, 'Maximum Marks': marks} 
                    for code, marks in total_marks_map.items()
                ])
                subject_df.to_excel(writer, sheet_name='Subject Structure', index=False)
        except Exception as e:
            raise ValueError(f"Excel generation error: {e}")

        # Step 7: Save JSON
        json_path = os.path.join(upload_dir, f"{file_id}.json")
        with open(json_path, "w", encoding="utf-8") as jf:
            json.dump(results, jf, indent=2)

        # Step 8: Return URLs
        json_url = os.path.join(settings.MEDIA_URL, upload_dir_name, f"{file_id}.json").replace("\\", "/")
        excel_url = os.path.join(settings.MEDIA_URL, upload_dir_name, f"{file_id}.xlsx").replace("\\", "/")

        return results, json_url, excel_url

def analyze_multiple_pdfs(sem1_file, sem2_file):
        """
        Analyze multiple PDFs (SEM1 and SEM2).
        Returns: results, json_url, excel_url
        """
        # Step 1: Save uploaded PDFs
        upload_dir_name = "uploads"
        upload_dir = os.path.join(settings.MEDIA_ROOT, upload_dir_name)
        os.makedirs(upload_dir, exist_ok=True)

        file_id = uuid4()
        
        # Save SEM1
        sem1_pdf_path = os.path.join(upload_dir, f"{file_id}_sem1.pdf")
        with open(sem1_pdf_path, "wb") as f:
            for chunk in sem1_file.chunks():
                f.write(chunk)
        
        # Save SEM2
        sem2_pdf_path = os.path.join(upload_dir, f"{file_id}_sem2.pdf")
        with open(sem2_pdf_path, "wb") as f:
            for chunk in sem2_file.chunks():
                f.write(chunk)

        # Step 2: Process SEM1
        sem1_text = extract_text_from_pdf(sem1_pdf_path)
        if "error" in sem1_text.lower():
            raise ValueError(f"SEM1 PDF extraction error: {sem1_text}")

        sem1_marks_map = parse_subject_structure(sem1_text)
        if not sem1_marks_map:
            raise ValueError("Could not parse subjects from SEM1 PDF.")

        sem1_students = parse_students(sem1_text, len(sem1_marks_map))
        if not sem1_students:
            raise ValueError("No student data found in SEM1 PDF.")

        sem1_data = calculate_percentages_multiple(sem1_students, sem1_marks_map)

        # Step 3: Process SEM2
        sem2_text = extract_text_from_pdf(sem2_pdf_path)
        if "error" in sem2_text.lower():
            raise ValueError(f"SEM2 PDF extraction error: {sem2_text}")

        sem2_marks_map = parse_subject_structure(sem2_text)
        if not sem2_marks_map:
            raise ValueError("Could not parse subjects from SEM2 PDF.")

        sem2_students = parse_students(sem2_text, len(sem2_marks_map))
        if not sem2_students:
            raise ValueError("No student data found in SEM2 PDF.")

        sem2_data = calculate_percentages_multiple(sem2_students, sem2_marks_map)

        # Step 4: Merge results
        merged_results = merge_results(sem1_data, sem2_data)

        # Step 5: Save Excel
        excel_path = os.path.join(upload_dir, f"{file_id}_merged.xlsx")
        df = pd.DataFrame(merged_results)
        try:
            with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='Merged Results', index=False)
        except Exception as e:
            raise ValueError(f"Excel generation error: {e}")

        # Step 6: Save JSON
        json_path = os.path.join(upload_dir, f"{file_id}_merged.json")
        with open(json_path, "w", encoding="utf-8") as jf:
            json.dump(merged_results, jf, indent=2)

        # Step 7: Return URLs
        json_url = os.path.join(settings.MEDIA_URL, upload_dir_name, f"{file_id}_merged.json").replace("\\", "/")
        excel_url = os.path.join(settings.MEDIA_URL, upload_dir_name, f"{file_id}_merged.xlsx").replace("\\", "/")

        return merged_results, json_url, excel_url
