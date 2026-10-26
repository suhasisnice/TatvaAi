"""Test PKI (ALL SYNTHETIC): one CA and one signer per document issuer. Output: data/synthetic/pki/*.pem"""
import datetime as dt
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

SIGNERS = ["inst-a", "inst-b", "inst-c", "aicte-portal", "auth-ka", "auth-mh", "auth-tn", "ca-firm"]
OUT = Path(__file__).resolve().parents[1] / "data" / "synthetic" / "pki"


def _name(cn: str) -> x509.Name:
    return x509.Name([x509.NameAttribute(NameOID.ORGANIZATION_NAME, "PramaanAI Test PKI (Synthetic)"),
                      x509.NameAttribute(NameOID.COMMON_NAME, cn)])


def _cert(subject, issuer, pub, signing_key, ca: bool):
    now = dt.datetime(2026, 1, 1)
    b = (x509.CertificateBuilder().subject_name(subject).issuer_name(issuer).public_key(pub)
         .serial_number(x509.random_serial_number()).not_valid_before(now).not_valid_after(now + dt.timedelta(days=3650))
         .add_extension(x509.BasicConstraints(ca=ca, path_length=None), critical=True)
         .add_extension(x509.KeyUsage(digital_signature=not ca, content_commitment=not ca, key_cert_sign=ca, crl_sign=ca,
                                      key_encipherment=False, data_encipherment=False, key_agreement=False,
                                      encipher_only=False, decipher_only=False), critical=True))
    return b.sign(signing_key, hashes.SHA256())


def _write(path: Path, obj, key=False):
    if key:
        path.write_bytes(obj.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    else:
        path.write_bytes(obj.public_bytes(serialization.Encoding.PEM))


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    ca_key = rsa.generate_private_key(65537, 2048)
    ca = _cert(_name("PramaanAI Test CA (Synthetic)"), _name("PramaanAI Test CA (Synthetic)"), ca_key.public_key(), ca_key, True)
    _write(OUT / "ca.pem", ca)
    for s in SIGNERS:
        k = rsa.generate_private_key(65537, 2048)
        _write(OUT / f"{s}.key.pem", k, key=True)
        _write(OUT / f"{s}.cert.pem", _cert(_name(s), ca.subject, k.public_key(), ca_key, False))
    print(f"wrote CA + {len(SIGNERS)} signers to {OUT}")


if __name__ == "__main__":
    main()
