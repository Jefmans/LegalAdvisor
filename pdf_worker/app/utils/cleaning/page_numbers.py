import re

def is_arabic_number(s):
    return re.fullmatch(r"\s*\d{1,4}\s*", s) is not None

def is_roman_number(s):
    return re.fullmatch(r"\s*[ivxlcdmIVXLCDM]{1,7}\s*", s) is not None

def roman_to_int(s):
    roman_map = {'I': 1, 'V': 5, 'X': 10, 'L': 50, 'C': 100, 'D': 500, 'M': 1000}
    s = s.upper()
    result = 0
    prev_value = 0
    for char in reversed(s):
        value = roman_map.get(char, 0)
        if value < prev_value:
            result -= value
        else:
            result += value
            prev_value = value
    return result if result > 0 else None

def detect_page_numbers(pages_text, n=3, min_sequence_len=2):
    candidates = []  # list of dicts: {"index": int, "line": str, "pos": "top"/"bottom", "value": int}
    
    for idx, lines in enumerate(pages_text):
        top_lines = lines[:n]
        bottom_lines = lines[-n:] if len(lines) >= n else lines

        for pos, group in [('top', top_lines), ('bottom', bottom_lines)]:
            for line in group:
                stripped = line.strip()
                if is_arabic_number(stripped):
                    value = int(stripped)
                elif is_roman_number(stripped):
                    value = roman_to_int(stripped)
                    if value is None:
                        continue
                else:
                    continue

                candidates.append({
                    "index": idx,
                    "line": line,
                    "pos": pos,
                    "value": value
                })

    # Group by position ("top" or "bottom")
    sequences = []
    for pos in ['top', 'bottom']:
        group = [c for c in candidates if c["pos"] == pos]
        group.sort(key=lambda x: x["index"])

        temp_seq = []
        for i, entry in enumerate(group):
            if not temp_seq:
                temp_seq.append(entry)
            else:
                prev = temp_seq[-1]
                # Allow gaps, but ensure ordering
                if entry["index"] > prev["index"] and entry["value"] > prev["value"]:
                    temp_seq.append(entry)
                elif len(temp_seq) >= min_sequence_len:
                    sequences.append(temp_seq)
                    temp_seq = [entry]
                else:
                    temp_seq = [entry]
        if len(temp_seq) >= min_sequence_len:
            sequences.append(temp_seq)

    return sequences


def remove_page_numbers(pages_text, sequences, n=3):
    cleaned = []
    skip_lines_per_page = {}  # page_index -> list of lines to remove

    for seq in sequences:
        for item in seq:
            page = item["index"]
            line = item["line"].strip()
            skip_lines_per_page.setdefault(page, []).append(line)

    for i, lines in enumerate(pages_text):
        to_remove = skip_lines_per_page.get(i, [])
        cleaned_lines = [line for line in lines if line.strip() not in to_remove]
        cleaned.append("\n".join(cleaned_lines))

    return cleaned
