"""Main PDF parser: reads a competition PDF and returns structured data."""

import re
import pdfplumber
from importer.format_a import parse_rows as parse_a_rows
from importer.format_bf import parse_rows as parse_bf_rows


def detect_group(text):
    """Detect gender and group from page text.
    Returns (gender, group_name) or (None, None).
    """
    m = re.match(r'(男子|女子)([A-F])组', text.strip())
    if m:
        gender = '男' if m.group(1) == '男子' else '女'
        return gender, m.group(2)
    return None, None


def get_format_type(group_name):
    if group_name == 'A':
        return 'A'
    elif group_name == 'F':
        return 'F'
    else:
        return 'BtoE'


def is_header_row(row):
    """Check if this row is a header/sub-header row (not data)."""
    if not row:
        return True
    first = (row[0] or '').strip()
    return first in ('排名', '', '成绩') or first is None


def parse_pdf(pdf_path):
    """Parse a competition PDF file.

    Returns a list of group results.
    """
    groups = []
    current_gender = None
    current_group = None
    current_header = None
    current_rows = []

    def flush():
        nonlocal current_rows
        if current_gender is not None and current_rows and current_header is not None:
            groups.append(_build_group(
                current_gender, current_group, current_header, current_rows
            ))
        current_rows = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ''
            first_line = text.split('\n')[0].strip() if text else ''

            gender, group_name = detect_group(first_line)

            if gender and group_name:
                # New group detected
                if gender != current_gender or group_name != current_group:
                    flush()
                    current_gender = gender
                    current_group = group_name
                    current_header = None
                # Same group continuing on new page - just keep accumulating

            # Extract tables from this page
            tables = page.extract_tables()
            for table in tables:
                if not table:
                    continue
                for row in table:
                    first_cell = (row[0] or '').strip() if row else ''

                    if first_cell == '排名':
                        # Header row - capture (first time or repeated)
                        if current_header is None:
                            current_header = row
                        continue

                    if is_header_row(row):
                        continue

                    if current_header is None:
                        continue

                    current_rows.append(row)

    # Flush last group
    flush()

    return groups


def _build_group(gender, group_name, header_row, data_rows):
    fmt = get_format_type(group_name)

    if fmt == 'A':
        records = parse_a_rows(data_rows, header_row)
    else:
        records = parse_bf_rows(data_rows, header_row)

    return {
        'gender': gender,
        'group_name': group_name,
        'format_type': fmt,
        'records': records,
    }
