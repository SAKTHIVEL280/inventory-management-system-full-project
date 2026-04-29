"""Data masking helpers for sensitive fields in non-privileged views."""
from __future__ import annotations


class DataMasker:
    @staticmethod
    def mask_email(email: str | None) -> str | None:
        if not email:
            return email
        if "@" not in email:
            return "masked@example.com"
        user, domain = email.split("@", 1)
        safe_domain = domain.strip() or "example.com"
        if not user:
            return f"masked@{safe_domain}"
        if len(user) <= 2:
            masked_user = "xx"
        else:
            masked_user = f"{user[0]}{'x' * (len(user) - 2)}{user[-1]}"
        return f"{masked_user}@{safe_domain}"

    @staticmethod
    def mask_phone(phone: str | None) -> str | None:
        if not phone:
            return phone
        digits = "".join(ch for ch in phone if ch.isdigit())
        if not digits:
            return "000000"

        clipped = digits[-15:]
        if len(clipped) < 6:
            clipped = clipped.rjust(6, "0")
        masked = f"{'0' * (len(clipped) - 4)}{clipped[-4:]}"
        if phone.strip().startswith("+"):
            return f"+{masked}"
        return masked

    @staticmethod
    def mask_pan(pan: str | None) -> str | None:
        if not pan:
            return pan
        token = pan.strip().upper()
        if len(token) != 10:
            return token
        return f"{token[0]}XXX{token[4]}0000{token[-1]}"

    @staticmethod
    def mask_gstin(gstin: str | None) -> str | None:
        if not gstin:
            return gstin
        token = gstin.strip().upper()
        if len(token) != 15:
            return token
        state = token[:2]
        name = f"{token[2]}XXX{token[6]}"
        digits = "0000"
        entity_type = token[11]
        checksum = token[14]
        return f"{state}{name}{digits}{entity_type}1Z{checksum}"

    @staticmethod
    def mask_bank_account(account: str | None) -> str | None:
        if not account:
            return account
        token = account.strip()
        if len(token) <= 4:
            return "0" * max(4, len(token))
        return f"{'0' * (len(token) - 4)}{token[-4:]}"


def should_mask_sensitive_fields(role: str | None) -> bool:
    normalized_role = (role or "").strip().lower()
    return normalized_role not in {"admin", "accounts"}
