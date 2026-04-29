import sqlite3
from config import DATABASE


def get_db():

    conn = sqlite3.connect(DATABASE)

    conn.row_factory = sqlite3.Row

    return conn


def init_db():

    db = get_db()

    # -------------------------
    # TABLA RESERVAS
    # -------------------------

    db.execute("""
        CREATE TABLE IF NOT EXISTS reservas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT,
            telefono TEXT,
            personas INTEGER,
            fecha TEXT,
            hora TEXT,
            notas TEXT,
            mesa TEXT,
            estado TEXT DEFAULT 'Pendiente',
            hora_llegada TEXT
        )
    """)

    # -------------------------
    # TABLA MESAS
    # -------------------------

    db.execute("""
        CREATE TABLE IF NOT EXISTS mesas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT,
            x INTEGER,
            y INTEGER,
            capacidad INTEGER
        )
    """)

    # -------------------------
    # TABLA EMPLEADOS
    # -------------------------

    db.execute("""
        CREATE TABLE IF NOT EXISTS empleados (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT,
            dni TEXT,
            telefono TEXT,
            puesto TEXT,
            pin_hash TEXT
        )
    """)

    # -------------------------
    # TABLA FICHAJES
    # -------------------------

    db.execute("""
        CREATE TABLE IF NOT EXISTS fichajes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            empleado_id INTEGER,
            fecha TEXT,
            hora TEXT,
            tipo TEXT
        )
    """)

    # -------------------------
    # TABLA ADMIN
    # -------------------------

    db.execute("""
        CREATE TABLE IF NOT EXISTS admin (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pin_hash TEXT
        )
    """)

    # -------------------------
    # TABLA HORARIOS
    # -------------------------

    db.execute("""
        CREATE TABLE IF NOT EXISTS horarios (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            empleado_id INTEGER NOT NULL,

            fecha TEXT NOT NULL,

            hora_inicio TEXT NOT NULL,

            hora_fin TEXT NOT NULL,

            turno TEXT,

            horas REAL,

            estado TEXT DEFAULT 'Programado',

            creado_en TEXT DEFAULT CURRENT_TIMESTAMP

        )
    """)

    # -------------------------
    # SOLICITUDES (RRHH empleado)
    # -------------------------

    db.execute("""
        CREATE TABLE IF NOT EXISTS solicitudes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            empleado_id INTEGER NOT NULL,
            tipo TEXT,
            fecha_inicio TEXT,
            fecha_fin TEXT,
            estado TEXT DEFAULT 'Pendiente',
            fecha_solicitud TEXT,
            comentario TEXT
        )
    """)

    # -------------------------
    # MENSAJES RRHH (chat con IA / historial)
    # -------------------------

    db.execute("""
        CREATE TABLE IF NOT EXISTS mensajes_rrhh (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            empleado_id INTEGER NOT NULL,
            mensaje TEXT NOT NULL,
            respuesta_ia TEXT,
            creado_en TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # -------------------------
    # ESCANDALLOS — ingredientes y platos
    # -------------------------

    db.execute("""
        CREATE TABLE IF NOT EXISTS ingredientes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            unidad TEXT NOT NULL DEFAULT 'kg',
            coste_unitario REAL NOT NULL DEFAULT 0
        )
    """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS platos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            descripcion TEXT,
            precio_venta REAL,
            creado_en TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS plato_ingredientes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plato_id INTEGER NOT NULL,
            ingrediente_id INTEGER NOT NULL,
            cantidad REAL NOT NULL
        )
    """)

    db.commit()

    try:
        from reservas.salon_helpers import ensure_salon_tables, seed_salon_if_empty

        ensure_salon_tables(db)
        seed_salon_if_empty(db)
    except Exception as ex:
        print("Aviso init salón:", ex)

    try:
        from reservas.empresa_config import ensure_config_empresa_table

        ensure_config_empresa_table(db)
    except Exception as ex:
        print("Aviso init empresa:", ex)

    try:
        from reservas.jornada_schema import ensure_jornada_tables

        ensure_jornada_tables(db)
    except Exception as ex:
        print("Aviso init jornada:", ex)

    try:
        from reservas.stock_schema import ensure_stock_schema

        ensure_stock_schema(db)
    except Exception as ex:
        print("Aviso init inventario:", ex)

    try:
        from reservas.tablet_schema import ensure_tablet_schema

        ensure_tablet_schema(db)
    except Exception as ex:
        print("Aviso init modo tablet:", ex)

    try:
        from reservas.tablet_config_schema import ensure_tablet_config

        ensure_tablet_config(db)
    except Exception as ex:
        print("Aviso init config tablet:", ex)

    try:
        from reservas.preregistro_schema import ensure_preregistro_tables

        ensure_preregistro_tables(db)
    except Exception as ex:
        print("Aviso init preregistros tablet:", ex)

    try:
        from reservas.horarios_entregas_schema import ensure_horarios_entregas_table

        ensure_horarios_entregas_table(db)
    except Exception as ex:
        print("Aviso init horarios PDF entregas:", ex)

    try:
        from reservas.empleados_schema import ensure_empleados_rrhh_columns

        ensure_empleados_rrhh_columns(db)
    except Exception as ex:
        print("Aviso init empleados RRHH:", ex)

    try:
        from reservas.rrhh_peticiones_schema import ensure_rrhh_peticiones_schema

        ensure_rrhh_peticiones_schema(db)
    except Exception as ex:
        print("Aviso init peticiones RRHH:", ex)

    try:
        from reservas.cierre_caja_schema import ensure_cierre_caja_tables

        ensure_cierre_caja_tables(db)
    except Exception as ex:
        print("Aviso init cierre caja:", ex)

    try:
        from reservas.proveedores_schema import ensure_proveedores_table

        ensure_proveedores_table(db)
    except Exception as ex:
        print("Aviso init proveedores:", ex)

    try:
        from reservas.calendario_admin_schema import ensure_calendario_admin_tables

        ensure_calendario_admin_tables(db)
    except Exception as ex:
        print("Aviso init calendario admin:", ex)

    try:
        from reservas.clientes_schema import ensure_clientes_schema, migrate_reservas_cliente_links

        ensure_clientes_schema(db)
        migrate_reservas_cliente_links(db)
    except Exception as ex:
        print("Aviso init clientes:", ex)

    try:
        from reservas.web_reservas_schema import ensure_web_reservas_tables

        ensure_web_reservas_tables(db)
    except Exception as ex:
        print("Aviso init reservas web:", ex)

    db.close()