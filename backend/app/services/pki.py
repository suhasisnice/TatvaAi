"""Throwaway test PKI for the synthetic demo documents.

One root CA ("TatvaAI Test Root CA (Synthetic)") issues a signing
certificate per signer name ("Karnataka Fire Department", an institution's
Trust, ...). The backend trusts only this root. Keys are generated on demand
and cached under backend/data/pki (gitignored). Nothing here is valid
outside the prototype; real DSCs come from licensed Indian CAs.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import re

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from pyhanko.keys import load_cert_from_pemder, load_private_key_from_pemder
from pyhanko.sign import signers
from pyhanko_certvalidator.registry import SimpleCertificateStore

PKI_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "pki"
ROOT_CERT = PKI_DIR / "root.pem"
ROOT_KEY = PKI_DIR / "root.key"
ROOT_NAME = "TatvaAI Test Root CA (Synthetic)"
_NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _name(common_name: str) -> x509.Name:
    return x509.Name([
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "TatvaAI Test PKI (Synthetic)"),
        x509.NameAttribute(NameOID.COMMON_NAME, common_name),
    ])


def _write_key(path: Path, key) -> None:
    path.write_bytes(key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))


def ensure_root() -> None:
    if ROOT_CERT.exists() and ROOT_KEY.exists():
        return
    PKI_DIR.mkdir(parents=True, exist_ok=True)
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = _name(ROOT_NAME)
    cert = (
        x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(_NOW).not_valid_after(_NOW + timedelta(days=3650))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .add_extension(x509.KeyUsage(digital_signature=False, content_commitment=False, key_encipherment=False,
                                     data_encipherment=False, key_agreement=False, key_cert_sign=True,
                                     crl_sign=True, encipher_only=False, decipher_only=False), critical=True)
        .sign(key, hashes.SHA256())
    )
    _write_key(ROOT_KEY, key)
    ROOT_CERT.write_bytes(cert.public_bytes(serialization.Encoding.PEM))


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def get_signer(signer_name: str) -> signers.SimpleSigner:
    """Signing certificate for `signer_name`, issued by the test root (created once, then cached)."""
    ensure_root()
    base = PKI_DIR / _slug(signer_name)
    cert_path, key_path = base.with_suffix(".pem"), base.with_suffix(".key")
    if not (cert_path.exists() and key_path.exists()):
        root_cert = x509.load_pem_x509_certificate(ROOT_CERT.read_bytes())
        root_key = serialization.load_pem_private_key(ROOT_KEY.read_bytes(), password=None)
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cert = (
            x509.CertificateBuilder().subject_name(_name(signer_name)).issuer_name(root_cert.subject)
            .public_key(key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(_NOW).not_valid_after(_NOW + timedelta(days=3650))
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .add_extension(x509.KeyUsage(digital_signature=True, content_commitment=True, key_encipherment=False,
                                         data_encipherment=False, key_agreement=False, key_cert_sign=False,
                                         crl_sign=False, encipher_only=False, decipher_only=False), critical=True)
            .sign(root_key, hashes.SHA256())
        )
        _write_key(key_path, key)
        cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    return signers.SimpleSigner(
        signing_cert=load_cert_from_pemder(str(cert_path)),
        signing_key=load_private_key_from_pemder(str(key_path), passphrase=None),
        cert_registry=SimpleCertificateStore.from_certs([load_cert_from_pemder(str(ROOT_CERT))]),
    )
