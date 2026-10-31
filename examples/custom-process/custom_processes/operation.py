"""Ordinary Python processing code; no API or job-manager dependencies."""


def text_statistics(text: str) -> dict[str, int]:
    """Count Unicode characters and whitespace-separated words."""
    return {"characters": len(text), "words": len(text.split())}
