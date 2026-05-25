from datetime import datetime, timezone
from zoneinfo import ZoneInfo


ZONA_LOCAL = ZoneInfo("Europe/Madrid")


def ahora_utc_naive() -> datetime:
    """
    Devuelve la fecha actual en UTC sin información explícita de zona horaria.

    Se utiliza este formato para mantener coherencia con los campos DateTime
    de SQLAlchemy/MariaDB, evitando mezclar fechas locales y fechas UTC.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


def formatear_fecha_local(fecha: datetime | None, formato: str = "%d/%m/%Y %H:%M", valor_si_none: str = "-") -> str:
    """
    Convierte una fecha almacenada en UTC a la zona horaria local de España
    para mostrarla en la interfaz.
    """
    if not fecha:
        return valor_si_none

    if fecha.tzinfo is None:
        fecha = fecha.replace(tzinfo=timezone.utc)

    return fecha.astimezone(ZONA_LOCAL).strftime(formato)