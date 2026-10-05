import os
from typing import Optional

from .csfloat import CSFloatProvider
from .skinport import SkinportProvider

KEYRING_SERVICE = "cs2_rewards"
KEYRING_USER = "csfloat_api_key"


def csfloat_api_key() -> Optional[str]:
    """Key aus der Umgebung/.env, sonst aus dem System-Keyring (falls installiert)."""
    key = os.environ.get("CSFLOAT_API_KEY")
    if key:
        return key
    try:
        import keyring
    except ImportError:
        return None
    try:
        return keyring.get_password(KEYRING_SERVICE, KEYRING_USER)
    except Exception:
        return None


def get_provider(name: str):
    if name == "skinport":
        return SkinportProvider()
    key = csfloat_api_key()
    if name == "csfloat":
        if not key:
            raise RuntimeError("Kein CSFloat-API-Key gefunden (CSFLOAT_API_KEY in .env oder System-Keyring).")
        return CSFloatProvider(key)
    # auto: CSFloat bevorzugt, Skinport als Ausweichlösung ohne Key
    return CSFloatProvider(key) if key else SkinportProvider()
