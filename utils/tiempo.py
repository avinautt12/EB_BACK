from datetime import datetime
from zoneinfo import ZoneInfo

TZ_MX = ZoneInfo('America/Mexico_City')

def ahora_mx() -> datetime:
    """Datetime actual en zona horaria de Ciudad de México (UTC-6, sin DST desde 2023)."""
    return datetime.now(TZ_MX)

def ahora_str(fmt: str = '%d/%m/%Y %H:%M') -> str:
    return ahora_mx().strftime(fmt)
