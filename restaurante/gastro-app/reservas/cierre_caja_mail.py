"""Envío de informes de cierre de caja por SMTP (Gmail y similares)."""
from __future__ import annotations

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any


def _password_efectiva(cfg: dict[str, Any]) -> str:
    envp = (os.environ.get("CIERRE_CAJA_SMTP_PASSWORD") or "").strip()
    if envp:
        return envp
    return (cfg.get("smtp_password") or "").strip()


def smtp_config_valida(cfg: dict[str, Any]) -> bool:
    if not (cfg.get("email_destino") or "").strip():
        return False
    if not (cfg.get("smtp_usuario") or "").strip():
        return False
    if not _password_efectiva(cfg):
        return False
    if not (cfg.get("smtp_host") or "").strip():
        return False
    return True


def enviar_informe_cierre(
    cfg: dict[str, Any],
    *,
    asunto: str,
    cuerpo_texto: str,
    cuerpo_html: str | None = None,
) -> tuple[bool, str]:
    """
    Envía un correo a `email_destino` usando la cuenta SMTP configurada.
    Devuelve (ok, mensaje_error).
    """
    to_addr = (cfg.get("email_destino") or "").strip()
    if not to_addr:
        return False, "Falta el correo del destinatario (dueño)."

    host = (cfg.get("smtp_host") or "").strip()
    port = int(cfg.get("smtp_port") or 587)
    user = (cfg.get("smtp_usuario") or "").strip()
    password = _password_efectiva(cfg)
    use_tls = bool(int(cfg.get("smtp_tls") if cfg.get("smtp_tls") is not None else 1))

    if not host or not user or not password:
        return False, "Configura servidor SMTP, usuario y contraseña (o variable CIERRE_CAJA_SMTP_PASSWORD)."

    msg = MIMEMultipart("alternative")
    msg["Subject"] = asunto
    msg["From"] = user
    msg["To"] = to_addr
    msg.attach(MIMEText(cuerpo_texto, "plain", "utf-8"))
    if cuerpo_html:
        msg.attach(MIMEText(cuerpo_html, "html", "utf-8"))

    try:
        with smtplib.SMTP(host, port, timeout=30) as server:
            if use_tls:
                server.starttls()
            server.login(user, password)
            server.sendmail(user, [to_addr], msg.as_string())
    except smtplib.SMTPAuthenticationError as e:
        return False, f"Autenticación SMTP rechazada: {e}"
    except OSError as e:
        return False, f"No se pudo conectar al servidor de correo: {e}"
    except smtplib.SMTPException as e:
        return False, f"Error SMTP: {e}"
    except Exception as e:
        return False, str(e)

    return True, ""


def enviar_correo_externo(
    cfg: dict[str, Any],
    *,
    destinatarios: list[str],
    asunto: str,
    cuerpo_texto: str,
    cuerpo_html: str | None = None,
) -> tuple[bool, str]:
    """
    Envía un correo a una lista de destinatarios usando la misma cuenta SMTP que cierre de caja.
    `cfg` debe ser el dict de `get_config_cierre_caja` (host, usuario, contraseña, TLS).
    """
    to_addrs = [x.strip() for x in destinatarios if (x or "").strip()]
    if not to_addrs:
        return False, "No hay destinatarios."

    host = (cfg.get("smtp_host") or "").strip()
    port = int(cfg.get("smtp_port") or 587)
    user = (cfg.get("smtp_usuario") or "").strip()
    password = _password_efectiva(cfg)
    use_tls = bool(int(cfg.get("smtp_tls") if cfg.get("smtp_tls") is not None else 1))

    if not host or not user or not password:
        return False, "Configura servidor SMTP, usuario y contraseña (ajustes de cierre de caja o variable CIERRE_CAJA_SMTP_PASSWORD)."

    msg = MIMEMultipart("alternative")
    msg["Subject"] = asunto
    msg["From"] = user
    msg["To"] = ", ".join(to_addrs)
    msg.attach(MIMEText(cuerpo_texto, "plain", "utf-8"))
    if cuerpo_html:
        msg.attach(MIMEText(cuerpo_html, "html", "utf-8"))

    try:
        with smtplib.SMTP(host, port, timeout=30) as server:
            if use_tls:
                server.starttls()
            server.login(user, password)
            server.sendmail(user, to_addrs, msg.as_string())
    except smtplib.SMTPAuthenticationError as e:
        return False, f"Autenticación SMTP rechazada: {e}"
    except OSError as e:
        return False, f"No se pudo conectar al servidor de correo: {e}"
    except smtplib.SMTPException as e:
        return False, f"Error SMTP: {e}"
    except Exception as e:
        return False, str(e)

    return True, ""
