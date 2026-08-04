import re
import sys

import pdfplumber


PDF_PATH = "/Users/mani/Desktop/CompanyWise HR contact (1) (1).pdf"


def main() -> None:
    emails = []
    with pdfplumber.open(PDF_PATH) as pdf:
        print(f"pages {len(pdf.pages)}")
        for page_no, page in enumerate(pdf.pages, 1):
            text = page.extract_text() or ""
            for match in re.finditer(
                r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text
            ):
                snippet = text[max(0, match.start() - 160) : match.end() + 160]
                snippet = " | ".join(line.strip() for line in snippet.splitlines() if line.strip())
                emails.append((len(emails) + 1, page_no, match.group(0), snippet))

    print(f"emails {len(emails)}")
    start = int(sys.argv[1]) if len(sys.argv) > 1 else 501
    end = int(sys.argv[2]) if len(sys.argv) > 2 else start + 9
    for sno, page_no, email, snippet in emails[start - 1 : end]:
        print(f"{sno}|p{page_no}|{email}|{snippet}")


if __name__ == "__main__":
    main()
