import fitz
import re
import json
import os
import pandas as pd
from django.conf import settings
from uuid import uuid4

# --- your parsing helpers (same as before) ---
def parse_grading_system(text):
    ranges = []
    marks_line = None
    grade_line = None

    for line in text.splitlines():
        if line.strip().startswith("MARKS"):
            marks_line = line
        elif line.strip().startswith("GRADE") and not line.strip().startswith("GRADE POINT"):
            grade_line = line

    if not marks_line or not grade_line:
        return []

    marks_ranges = re.findall(r"(\d+\.?\d*)\s*to\s*(\d+\.?\d*)", marks_line)
    grades = grade_line.split(":")[1].split()

    for (low, high), grade in zip(marks_ranges, grades):
        ranges.append((float(low), float(high), grade))

    return ranges

def get_grade(total, grading_rules):
    for low, high, grade in grading_rules:
        if low <= total <= high:
            return grade
    return None

def extract_paper_mapping(doc):
    mapping = {}
    pattern = re.compile(r"([A-Z0-9]{3,})\s*[-–]\s*([A-Za-z0-9\s\(\)/&\.\-]+?)(?::|\n|$)")
    
    for page_num in range(min(5, len(doc))):
        page_text = doc[page_num].get_text()
        for code, name in pattern.findall(page_text):
            mapping[code.strip()] = name.strip()
    
    return mapping

def parse_student_block(block, grading_rules, paper_names):
    lines = [l.strip() for l in block.split("\n") if l.strip()]
    if not lines:
        return None

    header_line = lines[0]
    m = re.match(r"(\d{7})\s+([A-Z\s/]+?)\s+\|(.+?)\|\s*(Successful|Unsuccessful)", header_line)
    if not m:
        return None

    seat_no = m.group(1).strip()
    name = m.group(2).strip()
    result = m.group(4).strip()

    codes1 = re.findall(r'\|([A-Z0-9]{3,})\s', header_line)

    totals1 = []
    if len(lines) > 1:
        totals1 = [int(nums[-1]) for nums in [re.findall(r'\d+', seg) for seg in lines[1].split("|")[1:]] if nums]

    codes2, totals2 = [], []
    for i, line in enumerate(lines):
        if re.search(r"\(\d+\)\w+", line) or re.search(r'\|\s*[A-Z0-9]{3,}\s', line):
            codes2 = re.findall(r'\|([A-Z0-9]{3,})\s', line)
            if i + 1 < len(lines):
                totals2 = [int(nums[-1]) for nums in [re.findall(r'\d+', seg) for seg in lines[i+1].split("|")[1:]] if nums]
            break

    papers = []
    for c, t in zip(codes1, totals1):
        papers.append({
            "paper_code": c,
            "paper_name": paper_names.get(c, "Unknown"),
            "total": t,
            "grade": get_grade(t, grading_rules)
        })
    for c, t in zip(codes2, totals2):
        papers.append({
            "paper_code": c,
            "paper_name": paper_names.get(c, "Unknown"),
            "total": t,
            "grade": get_grade(t, grading_rules)
        })

    sgpi = None
    if result.lower() == "successful":
        for line in reversed(lines):
            m = re.search(r"\b(\d+\.\d+)\b\s+--", line)
            if m:
                sgpi = m.group(1)
                break

    return {
        "seat_no": seat_no,
        "name": name,
        "result": result,
        "sgpi": sgpi,
        "papers": papers
    }

# --- main handler ---
def extract_result(file=None):
    try:
        # Save uploaded file temporarily
        upload_dir = os.path.join(settings.MEDIA_ROOT, "uploads")
        os.makedirs(upload_dir, exist_ok=True)

        pdf_path = os.path.join(upload_dir, f"{uuid4()}.pdf")
        with open(pdf_path, "wb") as f:
            for chunk in file.chunks():
                f.write(chunk)

        # Output paths
        json_path = pdf_path.replace(".pdf", ".json")
        excel_path = pdf_path.replace(".pdf", ".xlsx")

        # Extract results
        with fitz.open(pdf_path) as doc:
            paper_names = extract_paper_mapping(doc)
            full_text = "\n".join(page.get_text() for page in doc)
            grading_rules = parse_grading_system(full_text)

        blocks = re.split(r"(?=\n\s*\d{7}\s)", full_text)
        results, rows = [], []

        for block in blocks:
            student_data = parse_student_block(block, grading_rules, paper_names)
            if student_data:
                results.append(student_data)

                row = {
                    "Seat No": student_data["seat_no"],
                    "Name": student_data["name"],
                    "Result": student_data["result"],
                    "SGPI": student_data["sgpi"]
                }
                for i, paper in enumerate(student_data["papers"], start=1):
                    row[f"Paper {i} Code"] = paper["paper_code"]
                    row[f"Paper {i} Name"] = paper["paper_name"]
                    row[f"Paper {i} Marks"] = paper["total"]
                    row[f"Paper {i} Grade"] = paper["grade"]
                rows.append(row)

        # Save JSON
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

        # Save Excel
        df = pd.DataFrame(rows)
        df.to_excel(excel_path, index=False)

        return results, json_path, excel_path

    except Exception as e:
        return {"error": str(e)}, 500
