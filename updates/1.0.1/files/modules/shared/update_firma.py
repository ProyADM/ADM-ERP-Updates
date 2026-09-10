# modules/shared/update_firma.py
# ============================================================
# VERIFICACIÓN DE FIRMA DE LA CADENA DE ACTUALIZACIÓN (C5)
# ============================================================
# El canal de actualización (repo público ADM-ERP-Updates) publica:
#   - version.json            -> metadatos de la versión disponible
#   - updates/<v>/manifest.json -> hashes SHA-256 de los archivos del release
# y junto a cada uno un sidecar firmado "<archivo>.sig" (base64 de una línea).
#
# Este módulo contiene la clave PÚBLICA del operador (no es secreta) y la
# verificación Ed25519. El flujo en app.py es fail-closed: si falta el .sig
# o la firma no valida, NO se confía en el contenido (no hay actualización).
#
# La clave privada vive SOLO en la máquina del operador (fuera de repos):
#   C:\Users\<user>\.sidesys\update_signing_ed25519.key
# y las firmas se generan con scripts/sign_update.py --sign --repo ...
#
# Rotación de clave pública: se distribuye con un release firmado con la
# clave anterior (esta constante viaja dentro de los archivos actualizados).
# ============================================================

import base64
from functools import lru_cache

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

# Clave PÚBLICA de firma del canal de actualización (Ed25519, formato PEM).
# Generada con: python scripts/sign_update.py --gen-key
# Si se rota, esta constante se actualiza vía un release firmado con la clave anterior.
UPDATE_PUBLIC_KEY_PEM = """-----BEGIN PUBLIC KEY-----
MCowBQYDK2VwAyEAIsxHaHqMUsL28hcH2iIjOZ1sTer928Gv7BsuhOS95TM=
-----END PUBLIC KEY-----"""


@lru_cache(maxsize=1)
def _clave_publica():
    """Carga la clave pública PEM (cacheada). Error de formato = inválida."""
    try:
        return serialization.load_pem_public_key(
            UPDATE_PUBLIC_KEY_PEM.encode('utf-8')
        )
    except Exception:
        return None


def verificar_firma(contenido: bytes, sig_b64: str) -> bool:
    """Verifica la firma Ed25519 de 'contenido' contra el sidecar base64.

    Fail-closed: cualquier problema (clave inválida, .sig corrupto, firma
    inválida o contenido alterado) devuelve False.
    """
    if not isinstance(contenido, (bytes, bytearray)):
        return False
    clave = _clave_publica()
    if clave is None:
        return False
    if not sig_b64 or not isinstance(sig_b64, str):
        return False
    try:
        firma = base64.b64decode(sig_b64.strip(), validate=True)
        clave.verify(firma, bytes(contenido))
        return True
    except (InvalidSignature, ValueError, TypeError):
        return False


def verificar_archivo_firmado(path_contenido: str, path_sig: str) -> bool:
    """Helper para tests/uso puntual: verifica <archivo> contra <archivo>.sig."""
    try:
        with open(path_contenido, 'rb') as f:
            contenido = f.read()
        with open(path_sig, 'r', encoding='utf-8') as f:
            sig_b64 = f.read()
        return verificar_firma(contenido, sig_b64)
    except Exception:
        return False
