from io import BytesIO

from discord import File


def create_file_text(text: str, name: str = "file.txt") -> File:
    return File(fp=BytesIO(text.encode("utf-8")), filename=name)
