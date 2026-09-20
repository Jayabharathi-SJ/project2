from typing import Dict, List


LEGAL_SOURCES: List[Dict[str, str]] = [
    {
        "title": "Consumer Guide: Five Key Highlights of the Hire-Purchase (Amendment) Act 2026",
        "source_type": "official_consumer_guide",
        "authority": "Bank Negara Malaysia",
        "file_name": "HP Consumer Guide_EN_2026.pdf",
        "description": (
            "Official consumer guidance covering EIR, reducing balance method, "
            "fixed and variable rates, maximum EIR limits, and the implementation "
            "of the Hire-Purchase (Amendment) Act 2026."
        ),
    }
]


def get_legal_sources() -> List[Dict[str, str]]:
    """
    Return the registered legal and regulatory source metadata.
    """

    return LEGAL_SOURCES.copy()