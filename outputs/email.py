import os
import smtplib
from email.message import EmailMessage
from pathlib import Path
from typing import Iterable


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _split_emails(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _build_subject() -> str:
    prefix = _env("EMAIL_SUBJECT_PREFIX", "[Daily Trends]")
    date_label = _env("EMAIL_SUBJECT_DATE")
    if date_label:
        return f"{prefix} {date_label}"
    return f"{prefix} AI Daily Digest"


def _validate_config() -> tuple[dict, str | None]:
    config = {
        "enabled": False,
        "smtp_host": _env("SMTP_HOST"),
        "smtp_port": _env("SMTP_PORT", "587"),
        "smtp_username": _env("SMTP_USERNAME"),
        "smtp_password": _env("SMTP_PASSWORD"),
        "email_from": _env("EMAIL_FROM"),
        "email_to": _split_emails(_env("EMAIL_TO")),
        "smtp_use_tls": _env_bool("SMTP_USE_TLS", True),
        "smtp_use_ssl": _env_bool("SMTP_USE_SSL", False),
        "attach_markdown": _env_bool("EMAIL_ATTACH_MARKDOWN", True),
    }

    configured_values = [
        config["smtp_host"],
        config["smtp_username"],
        config["smtp_password"],
        config["email_from"],
        *config["email_to"],
    ]
    if not any(configured_values):
        config["enabled"] = False
        return config, None

    config["enabled"] = True

    missing: list[str] = []
    for key in ("smtp_host", "smtp_username", "smtp_password", "email_from"):
        if not config[key]:
            missing.append(key)
    if not config["email_to"]:
        missing.append("email_to")

    if missing:
        return config, f"Email skipped: missing config {', '.join(missing)}"
    return config, None


def _build_message(
    markdown_content: str,
    attachment_paths: Iterable[Path],
    config: dict,
) -> EmailMessage:
    message = EmailMessage()
    message["Subject"] = _build_subject()
    message["From"] = config["email_from"]
    message["To"] = ", ".join(config["email_to"])
    message.set_content(markdown_content)

    for path in attachment_paths:
        if not path.exists():
            continue
        message.add_attachment(
            path.read_bytes(),
            maintype="text",
            subtype="markdown",
            filename=path.name,
        )

    return message


def send_markdown_email(markdown_path: Path) -> str | None:
    config, config_error = _validate_config()
    if config_error:
        return config_error
    if not config["enabled"]:
        return None

    if not markdown_path.exists():
        return f"Email skipped: report file not found at {markdown_path}"

    markdown_content = markdown_path.read_text(encoding="utf-8")
    attachment_paths = [markdown_path] if config["attach_markdown"] else []
    message = _build_message(markdown_content, attachment_paths, config)

    timeout = int(_env("SMTP_TIMEOUT_SECONDS", "30"))
    smtp_port = int(config["smtp_port"])
    if config["smtp_use_ssl"]:
        with smtplib.SMTP_SSL(config["smtp_host"], smtp_port, timeout=timeout) as server:
            server.login(config["smtp_username"], config["smtp_password"])
            server.send_message(message)
    else:
        with smtplib.SMTP(config["smtp_host"], smtp_port, timeout=timeout) as server:
            if config["smtp_use_tls"]:
                server.starttls()
            server.login(config["smtp_username"], config["smtp_password"])
            server.send_message(message)

    return f"Email sent to {', '.join(config['email_to'])}"
