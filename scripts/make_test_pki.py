"""Deterministic TEST PKI (synthetic CA + signer certs) for DSC-signing synthetic PDFs.

Keys come from a seeded prime generator so repeated runs give byte-identical certs and signatures.
TEST ONLY: small deterministic keys are not secure and chain to a CA no real system trusts.
Usage: python scripts/make_test_pki.py [outdir] [--force]
"""
import random
import sys
from datetime import datetime
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

SIGNERS = [
    "inst-a", "inst-b", "inst-c",
    "auth-karnataka", "auth-maharashtra", "auth-tamilnadu",
    "ca-firm", "aicte-portal",
]
_SMALL = [p for p in range(3, 2000, 2) if all(p % q for q in range(3, int(p ** 0.5) + 1, 2))]


def _is_prime(n: int, rng: random.Random, rounds: int = 24) -> bool:
    if any(n % p == 0 for p in _SMALL):
        return False
    d, s = n - 1, 0
    while d % 2 == 0:
        d, s = d // 2, s + 1
    for _ in range(rounds):
        x = pow(rng.randrange(2, n - 2), d, n)
        if x in (1, n - 1):
            continue
        for _ in range(s - 1):
            x = pow(x, 2, n)
            if x == n - 1:
                break
        else:
            return False
    return True


def _prime(rng: random.Random, bits: int) -> int:
    while True:
        n = rng.getrandbits(bits) | (1 << (bits - 1)) | (1 << (bits - 2)) | 1
        if _is_prime(n, rng):
            return n


def det_rsa_key(seed: str, bits: int = 2048) -> rsa.RSAPrivateKey:
    rng, e = random.Random(seed), 65537
    while True:
        p, q = _prime(rng, bits // 2), _prime(rng, bits // 2)
        if p == q:
            continue
        if p < q:
            p, q = q, p
        phi = (p - 1) * (q - 1)
        try:
            d = pow(e, -1, phi)
        except ValueError:
            continue
        return rsa.RSAPrivateNumbers(
            p, q, d, d % (p - 1), d % (q - 1), pow(q, -1, p), rsa.RSAPublicNumbers(e, p * q)
        ).private_key()


def _name(cn: str) -> x509.Name:
    return x509.Name([
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "PramaanAI Test PKI (Synthetic)"),
        x509.NameAttribute(NameOID.COMMON_NAME, cn),
    ])


def _pem_key(k) -> bytes:
    return k.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())


def ensure_pki(outdir: Path, force: bool = False) -> Path:
    outdir.mkdir(parents=True, exist_ok=True)
    if not force and (outdir / "ca.pem").exists() and all((outdir / f"{s}.pem").exists() for s in SIGNERS):
        return outdir
    ca_key = det_rsa_key("pramaan-test-ca")
    ca_subject = _name("PramaanAI Test Root CA (Synthetic)")
    ca_cert = (
        x509.CertificateBuilder().subject_name(ca_subject).issuer_name(ca_subject)
        .public_key(ca_key.public_key()).serial_number(1000)
        .not_valid_before(datetime(2020, 1, 1)).not_valid_after(datetime(2040, 1, 1))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .add_extension(x509.KeyUsage(True, False, False, False, False, True, True, False, False), critical=True)
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(ca_key.public_key()), critical=False)
        .sign(ca_key, hashes.SHA256())
    )
    (outdir / "ca.pem").write_bytes(ca_cert.public_bytes(serialization.Encoding.PEM))
    for i, s in enumerate(SIGNERS):
        k = det_rsa_key(f"pramaan-test-{s}")
        cert = (
            x509.CertificateBuilder().subject_name(_name(f"DSC {s} (Synthetic)")).issuer_name(ca_subject)
            .public_key(k.public_key()).serial_number(2000 + i)
            .not_valid_before(datetime(2025, 1, 1)).not_valid_after(datetime(2030, 1, 1))
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .add_extension(x509.KeyUsage(True, True, False, False, False, False, False, False, False), critical=True)
            .add_extension(x509.SubjectKeyIdentifier.from_public_key(k.public_key()), critical=False)
            .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()), critical=False)
            .sign(ca_key, hashes.SHA256())
        )
        (outdir / f"{s}.key.pem").write_bytes(_pem_key(k))
        (outdir / f"{s}.pem").write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    return outdir


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    out = ensure_pki(Path(args[0]) if args else Path("data/synthetic/pki"), "--force" in sys.argv)
    print("PKI ready:", out)
