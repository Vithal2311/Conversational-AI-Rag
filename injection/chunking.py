from workflow_logging import logged_step
@logged_step
def split_into_chunks(text, chunk_size=200, overlap=40):
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than zero.")

    if not 0 <= overlap < chunk_size:
        raise ValueError("overlap must be between zero and chunk_size - 1.")

    words = text.split()
    chunks = []
    start = 0

    while start < len(words):
        end = start + chunk_size
        chunks.append(" ".join(words[start:end]))

        if end >= len(words):
            break

        start = end - overlap

    return chunks

