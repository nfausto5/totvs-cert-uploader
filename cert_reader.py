import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from cryptography import x509
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import ExtensionOID, NameOID


@dataclass
class CertificateInfo:
    file_path: str
    razao_social: str
    cnpj_numeros: str
    cnpj_formatado: str
    emissor: str
    valido_de: datetime
    valido_ate: datetime
    dias_restantes: int
    expirado: bool


def format_cnpj(cnpj: str) -> str:
    digits = re.sub(r"\D", "", cnpj or "")
    if len(digits) == 14:
        return f"{digits[:2]}.{digits[2:5]}.{digits[5:8]}/{digits[8:12]}-{digits[12:14]}"
    return cnpj


def _extract_cnpj_from_cert(cert: x509.Certificate, cn_text: str) -> str:
    # 1. Try CN pattern "RAZAO SOCIAL:12345678000199"
    if ":" in cn_text:
        tail = cn_text.rsplit(":", 1)[1].strip()
        digits = re.sub(r"\D", "", tail)
        if len(digits) == 14:
            return digits

    # 2. Try ICP-Brasil OID 2.16.76.1.3.3 (Cadastro Nacional da Pessoa Juridica) in SAN OtherName
    try:
        san = cert.extensions.get_extension_for_oid(ExtensionOID.SUBJECT_ALTERNATIVE_NAME)
        for other_name in san.value.get_values_for_type(x509.OtherName):
            if other_name.type_id.dotted_string == "2.16.76.1.3.3":
                raw_bytes = other_name.value
                # DER UTF8String/PrintableString/OctetString usually ends with the 14 ASCII digits
                decoded = raw_bytes.decode("latin-1", errors="ignore")
                match = re.search(r"(\d{14})", decoded)
                if match:
                    return match.group(1)
    except Exception:
        pass

    # 3. Search any 14-digit sequence in Subject attributes
    for attr in cert.subject:
        val = str(attr.value)
        match = re.search(r"(?<!\d)(\d{14})(?!\d)", val)
        if match:
            return match.group(1)

    return ""


def read_pfx_certificate(file_path: str, password: str) -> CertificateInfo:
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"Arquivo não encontrado: {file_path}")

    pfx_bytes = path.read_bytes()
    pwd_bytes: Optional[bytes] = password.encode("utf-8") if password is not None else None

    try:
        private_key, cert, additional_certs = pkcs12.load_key_and_certificates(pfx_bytes, pwd_bytes)
    except ValueError as exc:
        msg = str(exc).lower()
        if "password" in msg or "mac" in msg or "decrypt" in msg or "pkcs12" in msg:
            raise ValueError("Senha do certificado incorreta ou arquivo .pfx/.p12 inválido.") from exc
        raise ValueError(f"Não foi possível ler o certificado: {exc}") from exc

    if cert is None:
        raise ValueError("O arquivo informado não contém um certificado X.509 válido.")

    cn_attrs = cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)
    cn_text = str(cn_attrs[0].value) if cn_attrs else "Desconhecido"

    if ":" in cn_text:
        razao_social = cn_text.rsplit(":", 1)[0].strip()
    else:
        razao_social = cn_text.strip()

    cnpj_numeros = _extract_cnpj_from_cert(cert, cn_text)
    cnpj_formatado = format_cnpj(cnpj_numeros)

    issuer_cn = cert.issuer.get_attributes_for_oid(NameOID.COMMON_NAME)
    emissor = str(issuer_cn[0].value) if issuer_cn else cert.issuer.rfc4514_string()

    valido_de = getattr(cert, "not_valid_before_utc", None) or cert.not_valid_before.replace(tzinfo=timezone.utc)
    valido_ate = getattr(cert, "not_valid_after_utc", None) or cert.not_valid_after.replace(tzinfo=timezone.utc)

    now = datetime.now(timezone.utc)
    dias_restantes = (valido_ate - now).days
    expirado = valido_ate < now

    return CertificateInfo(
        file_path=str(path.resolve()),
        razao_social=razao_social,
        cnpj_numeros=cnpj_numeros,
        cnpj_formatado=cnpj_formatado,
        emissor=emissor,
        valido_de=valido_de,
        valido_ate=valido_ate,
        dias_restantes=dias_restantes,
        expirado=expirado,
    )
