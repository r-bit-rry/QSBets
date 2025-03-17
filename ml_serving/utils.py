from datetime import datetime
import os
from pydantic import BaseModel


class SummaryResponse(BaseModel):
    date: str
    source: str
    summary: dict
    relevant_symbol: str


def dump_failed_text(text: str):
    """
    Dump the failed text to a file in the debug_dumps folder.

    Args:
        text: The text to dump
    """
    if not os.path.exists(".debug_dumps"):
        os.makedirs(".debug_dumps")

    date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f".debug_dumps/{date_str}.txt"

    with open(filename, "w") as file:
        file.write(text)

