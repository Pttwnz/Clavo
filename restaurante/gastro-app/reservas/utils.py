"""Utilidades compartidas (presentación y cálculos sin rutas HTTP)."""
import json
import re
from datetime import date, datetime

from models import get_db

# Margen mínimo entre reservas en la misma mesa (mismo día): 2 horas entre horas de entrada.
MARGEN_SOLAPAMIENTO_MESA_SEG = 2 * 3600


def estado_bloquea_ocupacion_mesa(estado: str | None) -> bool:
    """Reservas canceladas o finalizadas no impiden nuevas reservas en esa mesa."""
    e = (estado or "").strip() or "Pendiente"
    return e not in ("Cancelada", "Finalizada")


def _variantes_fecha_reserva(fecha: str) -> list[str]:
    """Cadenas equivalentes al mismo día que pueden aparecer en reservas.fecha (ISO o dd/mm/yyyy)."""
    s = (fecha or "").strip()
    if not s:
        return []
    out: list[str] = [s]
    if len(s) >= 10 and s[4:5] == "-" and s[7:8] == "-":
        try:
            d = date.fromisoformat(s[:10])
            out.append(f"{d.day:02d}/{d.month:02d}/{d.year}")
            out.append(f"{d.day}/{d.month}/{d.year}")
        except ValueError:
            pass
    else:
        for sep in ("/", "-"):
            if sep not in s:
                continue
            parts = s.replace(sep, "/").split("/")
            if len(parts) != 3:
                continue
            try:
                da, mo, ye = int(parts[0]), int(parts[1]), int(parts[2])
                if ye < 100:
                    ye += 2000
                d = date(ye, mo, da)
                out.append(d.isoformat())
                out.append(f"{d.day:02d}/{d.month:02d}/{d.year}")
                out.append(f"{d.day}/{d.month}/{d.year}")
            except ValueError:
                pass
            break
    return list(dict.fromkeys([x for x in out if x]))


def normalizar_nombre_mesa(s: str | None) -> str:
    """Clave estable para comparar nombres de mesa (plano vs reserva): espacios, mayúsculas."""
    if not s:
        return ""
    t = str(s).replace("\ufeff", "").replace("\u200b", "")
    return " ".join(t.split()).casefold()


def partes_mesa_ocupacion(mesa_valor: str | None) -> list[str]:
    """Partes físicas que comparten el mismo hueco horario (mesa suelta o varias unidas con «+»)."""
    s = (mesa_valor or "").strip()
    if not s:
        return []
    if "+" in s:
        parts = [p.strip() for p in re.split(r"\s*\+\s*", s) if p.strip()]
        if len(parts) > 1:
            return parts
    return [s]


def horas_ocupadas_para_mesa(occ: dict[str, list[str]], mesa: str) -> list[str]:
    """Horas bloqueadas para esa mesa según el mapa de ocupación (claves normalizadas)."""
    nk = normalizar_nombre_mesa(mesa)
    if not nk:
        return []
    if nk in occ:
        return list(occ[nk])
    horas: list[str] = []
    for k, v in occ.items():
        if normalizar_nombre_mesa(k) == nk:
            horas.extend(v)
    return horas


def ocupacion_mesas_por_fecha(
    db,
    fecha: str,
    excluir_reserva_id: int | None = None,
) -> dict[str, list[str]]:
    """
    mesa -> lista de horas ('HH:MM') que bloquean la mesa ese día
    (excluye canceladas/finalizadas; opcionalmente excluye una reserva al editar).
    """
    rel: dict[str, set[str]] = {}
    if "mesa_uniones" in [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]:
        try:
            from reservas.salon_helpers import get_esquema_activo_id

            eid = get_esquema_activo_id(db)
            if eid is not None:
                ur = db.execute(
                    """
                    SELECT nombre, componentes_json, activa
                    FROM mesa_uniones
                    WHERE activa = 1 AND esquema_id = ?
                    """,
                    (eid,),
                ).fetchall()
            else:
                ur = []
            for u in ur:
                un = normalizar_nombre_mesa(u["nombre"] or "")
                if not un:
                    continue
                raw = u["componentes_json"] or "[]"
                nombres: list[str] = []
                ids: list[int] = []
                try:
                    v = json.loads(raw)
                    if isinstance(v, dict):
                        ids = []
                        for x in v.get("ids") or []:
                            try:
                                vi = int(x)
                                if vi > 0:
                                    ids.append(vi)
                            except (TypeError, ValueError):
                                continue
                        nombres = [str(x).strip() for x in (v.get("nombres") or []) if str(x).strip()]
                    elif isinstance(v, list):
                        nombres = [str(x).strip() for x in v if str(x).strip()]
                except Exception:
                    nombres = []
                    ids = []
                if not nombres and ids and eid is not None:
                    qs = ",".join("?" * len(ids))
                    rows_m = db.execute(
                        f"""
                        SELECT nombre FROM objetos_salon
                        WHERE esquema_id = ?
                          AND id IN ({qs})
                          AND (
                            LOWER(TRIM(COALESCE(tipo,''))) IN ('mesa', 'mesa_redonda', 'mesa_cuadrada')
                            OR TRIM(COALESCE(tipo,'')) = ''
                          )
                        """,
                        tuple([eid] + ids),
                    ).fetchall()
                    nombres = [
                        str(r["nombre"] or "").strip()
                        for r in rows_m
                        if str(r["nombre"] or "").strip()
                    ]
                for n in nombres:
                    cn = normalizar_nombre_mesa(n)
                    if not cn:
                        continue
                    rel.setdefault(un, set()).add(cn)
                    rel.setdefault(cn, set()).add(un)
        except Exception:
            rel = {}

    vars_f = _variantes_fecha_reserva(fecha)
    if not vars_f:
        return {}
    ph = ",".join("?" * len(vars_f))
    rows = db.execute(
        f"""
        SELECT id, mesa, hora, estado
        FROM reservas
        WHERE fecha IN ({ph})
        """,
        tuple(vars_f),
    ).fetchall()
    out: dict[str, list[str]] = {}
    for r in rows:
        if excluir_reserva_id is not None and r["id"] == excluir_reserva_id:
            continue
        if not estado_bloquea_ocupacion_mesa(r["estado"]):
            continue
        mesa_raw = (r["mesa"] or "").strip()
        hora = r["hora"]
        if not mesa_raw or not hora:
            continue
        for mesa in partes_mesa_ocupacion(mesa_raw):
            nk = normalizar_nombre_mesa(mesa)
            if not nk:
                continue
            out.setdefault(nk, []).append(hora)
            for alias in rel.get(nk, set()):
                out.setdefault(alias, []).append(hora)
    return out


def mesa_tiene_conflicto_horario(
    db,
    fecha: str,
    mesa: str,
    hora: str,
    excluir_reserva_id: int | None = None,
    margin_seg: int | None = None,
) -> bool:
    """True si no se puede reservar esa mesa (o grupo «M1 + M2») a esa hora por solapamiento."""
    mesa_raw = (mesa or "").strip()
    if not mesa_raw or not hora:
        return False
    occ = ocupacion_mesas_por_fecha(db, fecha, excluir_reserva_id=excluir_reserva_id)
    for part in partes_mesa_ocupacion(mesa_raw):
        horas = horas_ocupadas_para_mesa(occ, part)
        if hay_solapamiento_mesa_hora(hora, horas, margin_seg=margin_seg):
            return True
    return False


def ahora_madrid():
    """Hora actual en zona Europe/Madrid.

    En Windows, ``zoneinfo`` requiere el paquete PyPI ``tzdata``; si no está
    disponible o falla la zona, se usa la hora local del sistema.
    """
    try:
        from zoneinfo import ZoneInfo

        return datetime.now(ZoneInfo("Europe/Madrid"))
    except Exception:
        return datetime.now()


def calcular_horas_semana(empleado_id):
    """Estima jornadas en la semana actual a partir de registros de fichaje (pares entrada/salida)."""
    db = get_db()

    fichajes = db.execute(
        """
        SELECT COUNT(*)
        FROM fichajes
        WHERE empleado_id = ?
        AND fecha >= date('now','weekday 1','-7 days')
        """,
        (empleado_id,),
    ).fetchone()[0]

    db.close()

    # cada entrada + salida = 1 jornada
    horas = fichajes / 2

    return horas


def color_estado(estado):
    """Devuelve la clase Bootstrap de color según el estado textual de la reserva."""
    colores = {
        "Pendiente": "warning",
        "Confirmada": "primary",
        "Llegó": "success",
        "Finalizada": "dark",
        "Cancelada": "danger",
    }
    return colores.get(estado, "secondary")


def tiempo_en_mesa(hora_llegada):
    """Calcula tiempo transcurrido desde `hora_llegada` (ISO) hasta ahora como HH:MM."""
    try:
        if not hora_llegada:
            return ""
        llegada = datetime.fromisoformat(hora_llegada)
        ahora = datetime.now()
        diferencia = ahora - llegada
        minutos = int(diferencia.total_seconds() / 60)
        horas = minutos // 60
        minutos = minutos % 60
        return f"{horas:02d}:{minutos:02d}"
    except Exception:
        return ""


def hora_texto_a_minutos(hora) -> int | None:
    """Convierte 'HH:MM', 'HH:MM:SS', ISO/datetime o variantes a minutos desde medianoche."""
    if hora is None:
        return None
    s = str(hora).strip()
    if not s:
        return None
    if "T" in s:
        s = s.split("T", 1)[-1]
    elif " " in s and ":" in s:
        tail = s.split()[-1]
        if ":" in tail and len(tail) <= 12:
            s = tail
    parts = s.replace(".", ":").split(":")
    try:
        hh = int(parts[0])
        mm = int(parts[1]) if len(parts) > 1 else 0
        return hh * 60 + mm
    except (ValueError, IndexError):
        return None


def hay_solapamiento_mesa_hora(
    hora_nueva: str,
    horas_ocupadas: list[str],
    margin_seg: int | None = None,
) -> bool:
    """
    True si hora_nueva está a menos de `margin_seg` segundos de alguna hora de la lista
    (mismo día; HH:MM / ISO, coherente con `hora_texto_a_minutos`).
    """
    if margin_seg is None:
        margin_seg = MARGEN_SOLAPAMIENTO_MESA_SEG
    mn = hora_texto_a_minutos(hora_nueva)
    if mn is None:
        return False
    for h in horas_ocupadas:
        if not h:
            continue
        mo = hora_texto_a_minutos(h)
        if mo is None:
            continue
        diff_sec = abs(mn - mo) * 60
        if diff_sec < margin_seg:
            return True
    return False


def minutos_en_turno_visualizar(minutos: int | None, turno: str) -> bool:
    """Rangos alineados con las pestañas de /visualizar (mañana 06–12:59, etc.)."""
    if minutos is None:
        return False
    if turno == "manana":
        return 6 * 60 <= minutos <= 12 * 60 + 59
    if turno == "mediodia":
        return 13 * 60 <= minutos <= 17 * 60 + 59
    if turno == "noche":
        return 18 * 60 <= minutos <= 23 * 60 + 59
    return False


def turno_de_hora(hora):
    """Clasifica una hora (texto, ISO o datetime) en turno mañana, mediodía o noche."""
    m = hora_texto_a_minutos(hora)
    if m is None:
        return "noche"
    h = m // 60
    if h < 13:
        return "manana"
    if h < 18:
        return "mediodia"
    return "noche"


def actualizar_saldo_horas():
    """Hook reservado para recalcular saldo de horas tras fichar (sin efecto por ahora)."""
    pass
