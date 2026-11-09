"""Extract shared document headers before word-based chunking."""
from workflow_logging import logged_step

from datetime import datetime


@logged_step
def extract_document_metadata(text):
    lines = text.lstrip("\ufeff").splitlines()
    if not lines:
        raise ValueError("Document is empty.")

    fields = {}
    for line in lines[1:3]:
        for part in line.split("|"):
            label, separator, value = part.partition(":")
            if separator:
                fields[label.strip()] = value.strip()

    required = ("Document ID", "Version", "Effective date", "Owner", "Audience")
    for label in required:
        if not fields.get(label):
            raise ValueError(f"Missing document header: {label}")

    return {
        "document_id": fields["Document ID"],
        "title": lines[0].strip(),
        "version": fields["Version"],
        "effective_date": datetime.strptime(
            fields["Effective date"], "%d %B %Y"
        ).date().isoformat(),
        "owner": fields["Owner"],
        "audience": fields["Audience"],
    }
