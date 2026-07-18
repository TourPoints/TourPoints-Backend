-- =========================================================
-- TOURPOINTS - Esquema PostgreSQL (v3 - consolidado)
-- Requiere extensiones: pgcrypto (uuid), postgis
--
-- Decisiones tomadas en esta consolidación (revisar con el equipo):
--   1. movimientos_puntos usa FKs exclusivas (visita_id/compra_id/
--      reto_id/canje_id) + regla_id, forzadas con un CHECK de
--      "exactamente una referencia informada".
--   2. recompensas.poi_id (nullable) en vez de establecimiento_id
--      NOT NULL, para permitir recompensas no comerciales
--      (parqueadero público, entradas a un evento en una plaza).
--      Si el equipo confirma que TODA recompensa depende de un
--      aliado, cambiar a establecimiento_id NOT NULL.
--   3. poi_relaciones usa naming neutro (origen/destino) + un
--      flag es_jerarquica en tipos_relacion_poi, para no forzar
--      semántica de "padre/hijo" en relaciones simétricas como
--      CERCA_DE o RECOMENDADO_CON.
--   4. sesiones_reto SE RECUPERA: usuario_retos ya no tiene
--      UNIQUE(usuario_id, reto_id) simple, sino un índice único
--      parcial que solo impide dos intentos ACTIVOS a la vez.
--      Permite reintentar un reto conservando el historial de
--      intentos fallidos.
--   5. movimientos_puntos.tipo_movimiento pasa a ser una columna
--      GENERATED ALWAYS (derivada de las FK exclusivas) en vez de
--      un valor escrito por la aplicación, para eliminar el riesgo
--      de inconsistencia manteniendo la consulta/indexación fácil.
--   6. poi.nivel es nullable y NO se mantiene automáticamente en
--      este DDL: requiere un trigger sobre poi_relaciones (tipo
--      CONTIENE) que lo recalcule. Sin ese trigger se desincroniza;
--      avisar si se quiere el trigger.
--   7. recompensas.poi_id queda CONFIRMADO (no es asunción): el
--      POI es el núcleo del dominio, por eso las recompensas
--      cuelgan de poi, no de establecimientos.
--
-- Mejoras aplicadas en esta revisión (ver detalle en cada sección):
--   8. updated_at ahora se mantiene con trigger genérico
--      (fn_set_updated_at) en usuarios, poi y rachas_retos.
--   9. poi.nivel SE RECALCULA con trigger sobre poi_relaciones
--      (fn_actualizar_nivel_poi). Limitación conocida: recalcula
--      solo el destino directo, no propaga a nietos en cascada;
--      para grafos profundos se necesitaría una recursión explícita.
--  10. Índices agregados para lecturas frecuentes por poi_id/usuario_id
--      que antes no tenían soporte (comentarios, calificaciones,
--      establecimiento_usuarios).
--  11. ON DELETE CASCADE agregado en comentarios/calificaciones/favoritos
--      (dato social, se puede perder si el poi se borra físicamente),
--      pero NO en visitas/compras/establecimientos (alimentan el ledger
--      de movimientos_puntos: borrar un poi con historial ahí debe
--      fallar explícitamente, no arrastrar el borrado en cascada).
--  12. movimientos_puntos.reto_id renombrado a usuario_reto_id: el
--      nombre anterior sugería reto(id) cuando en realidad referencia
--      usuario_retos(id).
--  13. insignias ahora es un catálogo real (tabla insignias) en vez de
--      un código libre: hitos_racha.insignia_codigo (VARCHAR sin
--      validar) pasó a ser hitos_racha.insignia_id (FK).
--  14. hitos_racha.recompensa_id ahora tiene protección de stock:
--      hitos_racha_alcanzados.recompensa_otorgada (trigger
--      fn_otorgar_recompensa_hito) descuenta stock atómicamente si hay,
--      y si no, registra el logro igual sin premio físico (mismo
--      patrón "nunca bloquear" que ya usan retos/canjes).
--  15. poi_moderaciones agregada (migración de Alembic 5e0ac9f7b8ed,
--      2026-07-16): auditoría append-only de cada transición de estado
--      de un POI (quién, cuándo, de qué a qué, por qué). No estaba en
--      esta revisión original del DDL; se sincronizó acá después de
--      confirmar que la tabla real en Neon y el modelo ORM
--      (PoiModeracionLog) ya coincidían entre sí.
--
-- Pendiente de decisión con el equipo (NO aplicado en esta revisión):
--   - poi_estado_enum se reutiliza en establecimientos/promociones/
--     recompensas. Funciona, pero mezcla semánticas de ciclo de vida
--     distintas (ej. "RECHAZADO" no tiene un dueño claro de decisión
--     para una promoción). Separar en enums propios requiere definir
--     qué estados tiene sentido que tenga cada entidad -- decisión de
--     producto, no un fix mecánico.
--   - Roles/políticas RLS para exponer este schema vía PostgREST no
--     están definidos todavía: requiere confirmar el modelo de auth
--     (claims del JWT) antes de escribir políticas reales.
-- =========================================================

CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "postgis";

-- =========================================================
-- ENUMS
-- =========================================================

CREATE TYPE usuario_estado_enum AS ENUM ('ACTIVO','SUSPENDIDO','ELIMINADO');
CREATE TYPE poi_estado_enum AS ENUM ('BORRADOR','PENDIENTE','APROBADO','RECHAZADO','INACTIVO');
CREATE TYPE visita_estado_enum AS ENUM ('PENDIENTE','VALIDADA','RECHAZADA');
CREATE TYPE metodo_validacion_enum AS ENUM ('GPS','QR','MIXTA');
CREATE TYPE compra_estado_enum AS ENUM ('REGISTRADA','CANCELADA','VALIDADA');
CREATE TYPE canje_estado_enum AS ENUM ('PENDIENTE','REDIMIDO','EXPIRADO');
CREATE TYPE canje_origen_enum AS ENUM ('PUNTOS','RETO');
CREATE TYPE moneda_enum AS ENUM ('COP','USD');
CREATE TYPE comentario_estado_enum AS ENUM ('PENDIENTE','APROBADO','RECHAZADO');
CREATE TYPE reto_tipo_enum AS ENUM ('VISITA','COMPRA','RECORRIDO');
CREATE TYPE reto_estado_enum AS ENUM ('BORRADOR','ACTIVO','FINALIZADO','CANCELADO');
CREATE TYPE reto_recurrencia_enum AS ENUM ('UNICA','DIARIA','SEMANAL','MENSUAL');
CREATE TYPE reto_modo_recompensa_enum AS ENUM ('GARANTIZADA','LIMITADA','SIN_RECOMPENSA');
CREATE TYPE tipo_movimiento_puntos_enum AS ENUM ('VISITA','COMPRA','RETO','CANJE');
CREATE TYPE conversacion_role_enum AS ENUM ('USER','ASSISTANT','SYSTEM');
CREATE TYPE poi_fuente_enum AS ENUM ('ADMIN','ESTABLECIMIENTO','USUARIO','IA');


-- =========================================================
-- FUNCIÓN GENÉRICA: mantiene updated_at al día en cualquier tabla
-- que la use (se declara antes de las tablas para poder engancharla
-- justo después de cada CREATE TABLE que la necesite).
-- =========================================================

CREATE OR REPLACE FUNCTION fn_set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;


-- =========================================================
-- MÓDULO 1. IDENTIDAD
-- =========================================================

CREATE TABLE roles (
    id              SMALLSERIAL PRIMARY KEY,
    nombre          VARCHAR(50) UNIQUE NOT NULL,
    descripcion     TEXT
);

CREATE TABLE usuarios (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rol_id          SMALLINT NOT NULL REFERENCES roles(id),
    nombre          VARCHAR(100) NOT NULL,
    apellido        VARCHAR(100),
    email           VARCHAR(150) UNIQUE NOT NULL,
    password_hash   TEXT NOT NULL,
    telefono        VARCHAR(20),
    foto_url        TEXT,
    estado          usuario_estado_enum NOT NULL DEFAULT 'ACTIVO',
    configuracion   JSONB NOT NULL DEFAULT '{}'::jsonb, -- idioma, tema, notificaciones
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at      TIMESTAMPTZ
);

CREATE TRIGGER trg_usuarios_updated_at
    BEFORE UPDATE ON usuarios
    FOR EACH ROW EXECUTE FUNCTION fn_set_updated_at();


-- =========================================================
-- MÓDULO 2. UBICACIÓN
-- =========================================================

CREATE TABLE paises (
    id              SMALLSERIAL PRIMARY KEY,
    nombre          VARCHAR(100) NOT NULL,
    codigo_iso      CHAR(2) UNIQUE NOT NULL
);

CREATE TABLE departamentos (
    id              SERIAL PRIMARY KEY,
    pais_id         SMALLINT NOT NULL REFERENCES paises(id),
    nombre          VARCHAR(100) NOT NULL,
    UNIQUE (pais_id, nombre)
);

CREATE TABLE ciudades (
    id              BIGSERIAL PRIMARY KEY,
    departamento_id INTEGER NOT NULL REFERENCES departamentos(id),
    nombre          VARCHAR(100) NOT NULL,
    UNIQUE (departamento_id, nombre)
);


-- =========================================================
-- MÓDULO 3. CATEGORÍAS
-- =========================================================

CREATE TABLE categorias_poi (
    id              SMALLSERIAL PRIMARY KEY,
    nombre          VARCHAR(80) NOT NULL,
    icono           TEXT,
    color           VARCHAR(20)
);


-- =========================================================
-- MÓDULO 4. POI (entidad principal)
-- =========================================================

CREATE TABLE poi (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    categoria_id            SMALLINT NOT NULL REFERENCES categorias_poi(id),
    ciudad_id               BIGINT NOT NULL REFERENCES ciudades(id),
    creado_por_usuario_id   UUID REFERENCES usuarios(id),
    fuente                  poi_fuente_enum NOT NULL DEFAULT 'ADMIN',
    nivel                   SMALLINT, -- profundidad en el grafo de poi_relaciones; requiere trigger para mantenerse sincronizado (ver nota inicial)
    nombre                  VARCHAR(200) NOT NULL,
    slug                    VARCHAR(200) UNIQUE NOT NULL,
    descripcion             TEXT,
    direccion               TEXT,
    ubicacion               GEOGRAPHY(Point,4326) NOT NULL,
    radio_validacion        SMALLINT NOT NULL DEFAULT 50, -- metros
    telefono                VARCHAR(30),
    correo                  VARCHAR(120),
    sitio_web               TEXT,
    horarios                JSONB NOT NULL DEFAULT '{}'::jsonb, -- {"lunes":["08:00","18:00"], ...}
    metadata                JSONB NOT NULL DEFAULT '{}'::jsonb, -- wifi, pet_friendly, parking, precio_promedio...
    estado                  poi_estado_enum NOT NULL DEFAULT 'BORRADOR',
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at              TIMESTAMPTZ
);

CREATE TRIGGER trg_poi_updated_at
    BEFORE UPDATE ON poi
    FOR EACH ROW EXECUTE FUNCTION fn_set_updated_at();

-- Auditoría de moderación: cada transición de estado de un POI (enviar a
-- revisión, aprobar/rechazar/activar/inactivar por un ADMIN, o reintentar
-- tras un rechazo) queda registrada acá. Append-only, igual que
-- poi_relaciones — no se actualiza ni se borra una fila existente.
-- No estaba en el DDL original: se agregó vía la migración de Alembic
-- 5e0ac9f7b8ed (2026-07-16), fuera del diseño inicial documentado en este
-- archivo, y quedó sin reflejarse acá hasta ahora.
CREATE TABLE poi_moderaciones (
    id              BIGSERIAL PRIMARY KEY,
    poi_id          UUID NOT NULL REFERENCES poi(id) ON DELETE CASCADE,
    usuario_id      UUID NOT NULL REFERENCES usuarios(id),
    estado_anterior poi_estado_enum NOT NULL,
    estado_nuevo    poi_estado_enum NOT NULL,
    motivo          TEXT, -- opcional; solo se usa normalmente al rechazar
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_poi_moderaciones_poi ON poi_moderaciones (poi_id);


-- =========================================================
-- MÓDULO 5. POI_RELACIONES (grafo jerárquico / asociativo)
-- =========================================================

CREATE TABLE tipos_relacion_poi (
    id                  SMALLSERIAL PRIMARY KEY,
    nombre              VARCHAR(50) NOT NULL,      -- CONTIENE, PERTENECE_A, CERCA_DE, RUTA_INCLUYE, RECOMENDADO_CON
    descripcion         TEXT,
    es_jerarquica       BOOLEAN NOT NULL DEFAULT false, -- true: CONTIENE/PERTENECE_A. false: CERCA_DE/RECOMENDADO_CON
    es_bidireccional    BOOLEAN NOT NULL DEFAULT false, -- true: CERCA_DE/RECOMENDADO_CON (no importa quién es origen/destino)
    requiere_orden      BOOLEAN NOT NULL DEFAULT false  -- true: RUTA_INCLUYE (el campo orden de poi_relaciones es obligatorio)
);

CREATE TABLE poi_relaciones (
    id                  BIGSERIAL PRIMARY KEY,
    poi_origen_id       UUID NOT NULL REFERENCES poi(id),
    poi_destino_id      UUID NOT NULL REFERENCES poi(id),
    tipo_relacion_id    SMALLINT NOT NULL REFERENCES tipos_relacion_poi(id),
    orden               SMALLINT, -- posición dentro de una ruta o listado de contenidos; NULL si no aplica
    vigencia_inicio      TIMESTAMPTZ NOT NULL DEFAULT now(),
    vigencia_fin         TIMESTAMPTZ, -- NULL = sigue vigente; se cierra la fecha en vez de borrar la fila
    metadata            JSONB NOT NULL DEFAULT '{}'::jsonb,
    activo              BOOLEAN NOT NULL DEFAULT true, -- bandera rápida de filtro; la vigencia da el detalle histórico
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (poi_origen_id, poi_destino_id, tipo_relacion_id),
    CHECK (poi_origen_id <> poi_destino_id),
    CHECK (vigencia_fin IS NULL OR vigencia_fin > vigencia_inicio)
);

-- Recalcula poi.nivel del DESTINO cada vez que cambia una relación
-- jerárquica (CONTIENE/PERTENECE_A). nivel = MIN(nivel del/los
-- origen(es) activos, tratando NULL como 0) + 1; si no queda ninguna
-- relación jerárquica activa apuntando a este poi, nivel vuelve a NULL.
-- LIMITACIÓN CONOCIDA: solo recalcula el destino directo de la fila
-- que cambió, no cascada hacia descendientes más profundos (nietos).
-- Si se necesita esa propagación completa, conviene un job/recursión
-- explícita en vez de encadenar triggers.
CREATE OR REPLACE FUNCTION fn_actualizar_nivel_poi()
RETURNS TRIGGER AS $$
DECLARE
    v_destino_id  UUID;
    v_nuevo_nivel SMALLINT;
BEGIN
    v_destino_id := COALESCE(NEW.poi_destino_id, OLD.poi_destino_id);

    SELECT MIN(COALESCE(p_origen.nivel, 0)) + 1
    INTO v_nuevo_nivel
    FROM poi_relaciones pr
    JOIN tipos_relacion_poi t ON t.id = pr.tipo_relacion_id
    JOIN poi p_origen ON p_origen.id = pr.poi_origen_id
    WHERE pr.poi_destino_id = v_destino_id
      AND t.es_jerarquica
      AND pr.activo;

    UPDATE poi SET nivel = v_nuevo_nivel WHERE id = v_destino_id;

    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_actualizar_nivel_poi
    AFTER INSERT OR UPDATE OR DELETE ON poi_relaciones
    FOR EACH ROW EXECUTE FUNCTION fn_actualizar_nivel_poi();


-- =========================================================
-- MÓDULO 6-9. IMÁGENES, COMENTARIOS, CALIFICACIONES, FAVORITOS
-- =========================================================

CREATE TABLE imagenes_poi (
    id              BIGSERIAL PRIMARY KEY,
    poi_id          UUID NOT NULL REFERENCES poi(id) ON DELETE CASCADE,
    url             TEXT NOT NULL,
    orden           SMALLINT NOT NULL DEFAULT 0,
    principal       BOOLEAN NOT NULL DEFAULT false
);

CREATE TABLE comentarios (
    id              BIGSERIAL PRIMARY KEY,
    usuario_id      UUID NOT NULL REFERENCES usuarios(id),
    poi_id          UUID NOT NULL REFERENCES poi(id) ON DELETE CASCADE,
    contenido       TEXT NOT NULL,
    estado          comentario_estado_enum NOT NULL DEFAULT 'PENDIENTE',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE calificaciones (
    id              BIGSERIAL PRIMARY KEY,
    usuario_id      UUID NOT NULL REFERENCES usuarios(id),
    poi_id          UUID NOT NULL REFERENCES poi(id) ON DELETE CASCADE,
    calificacion    SMALLINT NOT NULL CHECK (calificacion BETWEEN 1 AND 5),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (usuario_id, poi_id)
);

CREATE TABLE favoritos (
    usuario_id      UUID NOT NULL REFERENCES usuarios(id),
    poi_id          UUID NOT NULL REFERENCES poi(id) ON DELETE CASCADE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (usuario_id, poi_id)
);


-- =========================================================
-- MÓDULO 10-13. COMERCIAL
-- =========================================================

-- Extensión 1:1 de poi. Solo información empresarial, sin duplicar
-- nombre/dirección/ubicación que ya vive en poi.
CREATE TABLE establecimientos (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    poi_id              UUID NOT NULL UNIQUE REFERENCES poi(id),
    nit                 VARCHAR(30) UNIQUE,
    razon_social        VARCHAR(200) NOT NULL,
    tipo_negocio        VARCHAR(80),
    fecha_afiliacion    DATE NOT NULL DEFAULT CURRENT_DATE,
    estado              poi_estado_enum NOT NULL DEFAULT 'PENDIENTE',
    metadata            JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE establecimiento_usuarios (
    establecimiento_id UUID NOT NULL REFERENCES establecimientos(id) ON DELETE CASCADE,
    usuario_id          UUID NOT NULL REFERENCES usuarios(id),
    cargo               VARCHAR(80),
    PRIMARY KEY (establecimiento_id, usuario_id)
);

CREATE TABLE compras (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    usuario_id          UUID NOT NULL REFERENCES usuarios(id),
    establecimiento_id  UUID NOT NULL REFERENCES establecimientos(id),
    valor               NUMERIC(12,2) NOT NULL CHECK (valor > 0),
    moneda              moneda_enum NOT NULL DEFAULT 'COP',
    codigo_transaccion  VARCHAR(60) UNIQUE,
    estado              compra_estado_enum NOT NULL DEFAULT 'REGISTRADA',
    cancelada_por       UUID REFERENCES usuarios(id),
    fecha_cancelacion   TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (
        (estado = 'CANCELADA' AND cancelada_por IS NOT NULL AND fecha_cancelacion IS NOT NULL)
        OR (estado <> 'CANCELADA' AND cancelada_por IS NULL AND fecha_cancelacion IS NULL)
    )
);

CREATE TABLE promociones (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    establecimiento_id  UUID NOT NULL REFERENCES establecimientos(id),
    titulo              VARCHAR(200) NOT NULL,
    descripcion         TEXT,
    inicio              TIMESTAMPTZ NOT NULL,
    fin                 TIMESTAMPTZ NOT NULL,
    estado              poi_estado_enum NOT NULL DEFAULT 'PENDIENTE',
    CHECK (fin > inicio)
);


-- =========================================================
-- MÓDULO 14. VISITAS
-- =========================================================

CREATE TABLE visitas (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    usuario_id          UUID NOT NULL REFERENCES usuarios(id),
    poi_id              UUID NOT NULL REFERENCES poi(id),
    ubicacion_usuario   GEOGRAPHY(Point,4326),
    precision_metros    NUMERIC(6,2),
    distancia_metros    NUMERIC(8,2),
    metodo_validacion   metodo_validacion_enum NOT NULL,
    estado              visita_estado_enum NOT NULL DEFAULT 'PENDIENTE',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);


-- =========================================================
-- MÓDULO 15-18. GAMIFICACIÓN
-- =========================================================

CREATE TABLE reglas_puntos (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nombre          VARCHAR(200) NOT NULL,
    prioridad       SMALLINT NOT NULL DEFAULT 0,
    configuracion   JSONB NOT NULL, -- {"evento":"VISITA","categoria":"Museo","puntos":120}
    vigencia_inicio TIMESTAMPTZ,
    vigencia_fin    TIMESTAMPTZ,
    activo          BOOLEAN NOT NULL DEFAULT true,
    CHECK (vigencia_fin IS NULL OR vigencia_inicio IS NULL OR vigencia_fin > vigencia_inicio)
);

-- recompensas se declara antes de retos/canjes porque ambos la referencian
CREATE TABLE recompensas (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    poi_id          UUID REFERENCES poi(id), -- nullable: no toda recompensa depende de un aliado comercial
    nombre          VARCHAR(200) NOT NULL,
    descripcion     TEXT,
    stock           INTEGER NOT NULL DEFAULT 0 CHECK (stock >= 0),
    puntos          INTEGER NOT NULL CHECK (puntos > 0),
    estado          poi_estado_enum NOT NULL DEFAULT 'BORRADOR'
);

CREATE TABLE retos (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nombre              VARCHAR(200) NOT NULL,
    descripcion         TEXT,
    tipo                reto_tipo_enum NOT NULL,
    recurrencia         reto_recurrencia_enum NOT NULL DEFAULT 'UNICA',
    cantidad_requerida  SMALLINT NOT NULL CHECK (cantidad_requerida > 0),
    recompensa_id       UUID REFERENCES recompensas(id),
    modo_recompensa     reto_modo_recompensa_enum NOT NULL DEFAULT 'SIN_RECOMPENSA',
    -- Quién lo creó: siempre un usuario (admin normalmente). Si lo
    -- propone un establecimiento aliado, establecimiento_id queda
    -- lleno y el reto nace en estado BORRADOR hasta que un admin lo
    -- apruebe (lo pasa a ACTIVO) o lo rechace (CANCELADO).
    creado_por_usuario_id   UUID REFERENCES usuarios(id),
    establecimiento_id      UUID REFERENCES establecimientos(id), -- NULL = reto general del admin
    -- Si recurrencia = UNICA: inicio/fin son las fechas exactas del reto.
    -- Si es DIARIA/SEMANAL/MENSUAL: inicio/fin son la VENTANA DE VIGENCIA
    -- durante la cual el reto se sigue repitiendo (fin puede ser NULL =
    -- indefinido). El ciclo puntual de cada usuario vive en usuario_retos.
    inicio              TIMESTAMPTZ NOT NULL,
    fin                 TIMESTAMPTZ,
    estado              reto_estado_enum NOT NULL DEFAULT 'BORRADOR',
    configuracion       JSONB NOT NULL DEFAULT '{}'::jsonb, -- POIs/categorías involucradas, orden de recorrido
    CHECK (fin IS NULL OR fin > inicio),
    CHECK (
        (modo_recompensa = 'SIN_RECOMPENSA' AND recompensa_id IS NULL)
        OR (modo_recompensa IN ('GARANTIZADA','LIMITADA') AND recompensa_id IS NOT NULL)
    )
);

-- Cada fila es un INTENTO dentro de un PERIODO específico. Para un reto
-- UNICA, el periodo coincide con retos.inicio/fin. Para uno recurrente
-- (DIARIA/SEMANAL/MENSUAL), el backend calcula periodo_inicio/periodo_fin
-- al inscribir al usuario (ej. date_trunc('week', now()) para SEMANAL),
-- así cada ciclo es una fila nueva sin tocar la tabla `retos`.
CREATE TABLE usuario_retos (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    usuario_id          UUID NOT NULL REFERENCES usuarios(id),
    reto_id             UUID NOT NULL REFERENCES retos(id),
    periodo_inicio      TIMESTAMPTZ NOT NULL,
    periodo_fin         TIMESTAMPTZ,
    numero_intento      SMALLINT NOT NULL DEFAULT 1, -- reintentos DENTRO del mismo periodo
    progreso            JSONB NOT NULL DEFAULT '{"completados": [], "cantidad": 0}'::jsonb,
    porcentaje          SMALLINT NOT NULL DEFAULT 0 CHECK (porcentaje BETWEEN 0 AND 100),
    fecha_completado    TIMESTAMPTZ,
    estado              reto_estado_enum NOT NULL DEFAULT 'ACTIVO',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (periodo_fin IS NULL OR periodo_fin > periodo_inicio),
    UNIQUE (usuario_id, reto_id, periodo_inicio, numero_intento)
);

-- Solo un intento ACTIVO por usuario+reto+periodo a la vez.
-- (antes era por usuario+reto; ahora un reto SEMANAL permite un ACTIVO
-- en la semana actual Y otro ya cerrado de la semana pasada conviviendo).
CREATE UNIQUE INDEX idx_usuario_retos_intento_activo
    ON usuario_retos (usuario_id, reto_id, periodo_inicio)
    WHERE estado = 'ACTIVO';

-- Sesión de tracking en vivo para retos de tipo RECORRIDO. El tracking
-- GPS punto-a-punto vive en Redis mientras la sesión está EN_CURSO;
-- aquí solo se persiste el marco (inicio/fin/estado) del intento.
CREATE TABLE sesiones_reto (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    usuario_reto_id     UUID NOT NULL REFERENCES usuario_retos(id) ON DELETE CASCADE,
    inicio              TIMESTAMPTZ NOT NULL DEFAULT now(),
    fin                 TIMESTAMPTZ,
    estado              reto_estado_enum NOT NULL DEFAULT 'ACTIVO',
    CHECK (fin IS NULL OR fin > inicio)
);

-- Racha de un usuario en un reto RECURRENTE (DIARIA/SEMANAL/MENSUAL).
-- Vive aparte de usuario_retos porque una racha cruza varios periodos:
-- no tiene sentido guardarla en una fila que representa un solo ciclo.
--
-- Reingreso obligatorio: como el usuario debe volver a unirse cada
-- periodo (no hay job automático que lo inscriba), el backend solo
-- actualiza esta tabla en dos momentos:
--   1) cuando el usuario se une a un nuevo periodo: compara
--      periodo_inicio contra ultimo_periodo_inicio. Si son ciclos
--      consecutivos (ej. exactamente 7 días después para SEMANAL),
--      la racha se mantiene "en juego"; si hay un hueco (se saltó una
--      semana), racha_actual se resetea a 0 ANTES de sumar el nuevo intento.
--   2) cuando ese periodo llega a FINALIZADO: racha_actual += 1,
--      racha_maxima = GREATEST(racha_maxima, racha_actual).
CREATE TABLE rachas_retos (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    usuario_id              UUID NOT NULL REFERENCES usuarios(id),
    reto_id                 UUID NOT NULL REFERENCES retos(id),
    racha_actual            SMALLINT NOT NULL DEFAULT 0,
    racha_maxima            SMALLINT NOT NULL DEFAULT 0,
    ultimo_periodo_inicio   TIMESTAMPTZ,
    ultimo_periodo_completado BOOLEAN NOT NULL DEFAULT false, -- ASUNCION: distingue "participó" de "completó" el último ciclo visto
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (usuario_id, reto_id),
    CHECK (racha_actual >= 0 AND racha_maxima >= racha_actual)
);

CREATE TRIGGER trg_rachas_retos_updated_at
    BEFORE UPDATE ON rachas_retos
    FOR EACH ROW EXECUTE FUNCTION fn_set_updated_at();

-- Catálogo de insignias/badges otorgables. Se declara antes de
-- hitos_racha porque este último ya no guarda un código libre sin
-- validar, sino una FK real a este catálogo.
CREATE TABLE insignias (
    id              SMALLSERIAL PRIMARY KEY,
    codigo          VARCHAR(60) UNIQUE NOT NULL,
    nombre          VARCHAR(200) NOT NULL,
    descripcion     TEXT,
    icono           TEXT
);

-- Catálogo de "premios por racha": al llegar a racha_requerida veces
-- seguidas en un reto, se desbloquea un beneficio. Un mismo hito puede
-- otorgar puntos extra, una recompensa exclusiva, una insignia, o
-- combinación de las tres (todas nullable: usa las que necesites).
CREATE TABLE hitos_racha (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    reto_id             UUID NOT NULL REFERENCES retos(id), -- a qué reto aplica esta escalera de hitos
    racha_requerida     SMALLINT NOT NULL CHECK (racha_requerida > 0),
    nombre              VARCHAR(200) NOT NULL, -- ej. "Racha de fuego"
    puntos_bonus        INTEGER NOT NULL DEFAULT 0 CHECK (puntos_bonus >= 0),
    recompensa_id       UUID REFERENCES recompensas(id), -- recompensa exclusiva desbloqueada en este hito
    insignia_id         SMALLINT REFERENCES insignias(id), -- insignia exclusiva desbloqueada en este hito
    UNIQUE (reto_id, racha_requerida)
);

-- Log de cada vez que un usuario alcanza un hito. Sin UNIQUE por
-- usuario+hito a propósito: si la racha se rompe y vuelve a llegar a 5,
-- el hito se vuelve a otorgar (ajusta con un UNIQUE si prefieres que
-- cada hito solo se gane una vez en la vida).
CREATE TABLE hitos_racha_alcanzados (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    usuario_id          UUID NOT NULL REFERENCES usuarios(id),
    hito_id             UUID NOT NULL REFERENCES hitos_racha(id),
    usuario_reto_id     UUID NOT NULL REFERENCES usuario_retos(id), -- el período cuya finalización disparó el hito
    -- ASUNCION: si hitos_racha.recompensa_id tiene stock cuando se
    -- alcanza el hito, se descuenta aquí mismo (ver trigger debajo) y
    -- queda true. Si no hay stock (o el hito no tiene recompensa_id),
    -- el logro se registra igual (nunca se bloquea) y queda false --
    -- el usuario se queda con la insignia/puntos_bonus pero sin el
    -- premio físico. La app usa esta columna para decidir qué mostrar.
    recompensa_otorgada BOOLEAN NOT NULL DEFAULT false,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Mismo patrón atómico (FOR UPDATE) que fn_reservar_o_bloquear_reto /
-- fn_descontar_stock_canje: nunca bloquea el INSERT por falta de stock,
-- solo decide si esta ocurrencia puntual se lleva el premio físico.
CREATE OR REPLACE FUNCTION fn_otorgar_recompensa_hito()
RETURNS TRIGGER AS $$
DECLARE
    v_recompensa_id UUID;
    v_stock         INTEGER;
BEGIN
    SELECT recompensa_id INTO v_recompensa_id
    FROM hitos_racha WHERE id = NEW.hito_id;

    IF v_recompensa_id IS NULL THEN
        NEW.recompensa_otorgada := false;
        RETURN NEW;
    END IF;

    SELECT stock INTO v_stock FROM recompensas WHERE id = v_recompensa_id FOR UPDATE;

    IF v_stock IS NOT NULL AND v_stock > 0 THEN
        UPDATE recompensas SET stock = stock - 1 WHERE id = v_recompensa_id;
        NEW.recompensa_otorgada := true;
    ELSE
        NEW.recompensa_otorgada := false;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_otorgar_recompensa_hito
    BEFORE INSERT ON hitos_racha_alcanzados
    FOR EACH ROW EXECUTE FUNCTION fn_otorgar_recompensa_hito();


-- =========================================================
-- CANJES (declarada antes de movimientos_puntos, que la referencia)
-- =========================================================

CREATE TABLE canjes (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    usuario_id          UUID NOT NULL REFERENCES usuarios(id),
    recompensa_id       UUID NOT NULL REFERENCES recompensas(id),
    origen              canje_origen_enum NOT NULL DEFAULT 'PUNTOS',
    usuario_reto_id     UUID REFERENCES usuario_retos(id), -- qué intento de reto lo otorgó, si origen = RETO
    codigo_qr           TEXT UNIQUE NOT NULL,
    fecha_expira        TIMESTAMPTZ,
    fecha_redencion     TIMESTAMPTZ,
    estado              canje_estado_enum NOT NULL DEFAULT 'PENDIENTE',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (
        (origen = 'RETO' AND usuario_reto_id IS NOT NULL)
        OR (origen = 'PUNTOS' AND usuario_reto_id IS NULL)
    )
);


-- =========================================================
-- MÓDULO 16. MOVIMIENTOS DE PUNTOS (FKs exclusivas + regla)
-- =========================================================

CREATE TABLE movimientos_puntos (
    id                  BIGSERIAL PRIMARY KEY,
    usuario_id          UUID NOT NULL REFERENCES usuarios(id),
    regla_id            UUID REFERENCES reglas_puntos(id), -- qué regla generó el movimiento (trazabilidad)
    visita_id           UUID REFERENCES visitas(id),
    compra_id           UUID REFERENCES compras(id),
    usuario_reto_id     UUID REFERENCES usuario_retos(id), -- referencia al intento del usuario, no al reto genérico
    canje_id            UUID REFERENCES canjes(id),
    -- Derivada de las FK, no escribible directamente: elimina el riesgo
    -- de inconsistencia entre "tipo declarado" y "FK realmente llena"
    -- que existía al guardar tipo_movimiento como columna independiente.
    tipo_movimiento     tipo_movimiento_puntos_enum GENERATED ALWAYS AS (
        CASE
            WHEN visita_id IS NOT NULL THEN 'VISITA'::tipo_movimiento_puntos_enum
            WHEN compra_id IS NOT NULL THEN 'COMPRA'::tipo_movimiento_puntos_enum
            WHEN usuario_reto_id IS NOT NULL THEN 'RETO'::tipo_movimiento_puntos_enum
            WHEN canje_id  IS NOT NULL THEN 'CANJE'::tipo_movimiento_puntos_enum
        END
    ) STORED,
    puntos              INTEGER NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- Exactamente una de las cuatro referencias debe estar informada.
    CHECK (num_nonnulls(visita_id, compra_id, usuario_reto_id, canje_id) = 1)
);
-- Saldo NUNCA se guarda: se calcula con SUM(puntos) o se materializa en una vista.


-- =========================================================
-- DISPONIBILIDAD POR STOCK (triggers) -- según modo_recompensa
-- =========================================================

-- 1) Al INSCRIBIRSE (INSERT en usuario_retos):
--    - GARANTIZADA: reserva 1 unidad de stock DE INMEDIATO. Si no hay
--      stock, bloquea la inscripción (nadie invierte esfuerzo en un
--      premio que ya no existe).
--    - LIMITADA: no reserva ni bloquea nada al inscribirse -- el
--      riesgo de que se agote se resuelve al completar (ver el
--      trigger de canjes más abajo).
--    - SIN_RECOMPENSA: no aplica (recompensa_id es NULL).
CREATE OR REPLACE FUNCTION fn_reservar_o_bloquear_reto()
RETURNS TRIGGER AS $$
DECLARE
    v_recompensa_id UUID;
    v_modo          reto_modo_recompensa_enum;
    v_stock         INTEGER;
BEGIN
    SELECT recompensa_id, modo_recompensa INTO v_recompensa_id, v_modo
    FROM retos WHERE id = NEW.reto_id;

    IF v_modo = 'GARANTIZADA' THEN
        SELECT stock INTO v_stock FROM recompensas WHERE id = v_recompensa_id FOR UPDATE;
        IF v_stock IS NULL OR v_stock <= 0 THEN
            RAISE EXCEPTION 'Reto % está agotado (modo GARANTIZADA sin stock para reservar)', NEW.reto_id;
        END IF;
        UPDATE recompensas SET stock = stock - 1 WHERE id = v_recompensa_id;
    END IF;
    -- LIMITADA y SIN_RECOMPENSA: sin acción al inscribirse.

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_reservar_o_bloquear_reto
    BEFORE INSERT ON usuario_retos
    FOR EACH ROW EXECUTE FUNCTION fn_reservar_o_bloquear_reto();

-- 2) Si un intento GARANTIZADA se cancela/expira sin completarse, la
--    unidad reservada se devuelve al stock -- si no, se perdería para
--    siempre cada vez que alguien se inscribe y abandona.
CREATE OR REPLACE FUNCTION fn_liberar_reserva_si_no_completa()
RETURNS TRIGGER AS $$
DECLARE
    v_recompensa_id UUID;
    v_modo          reto_modo_recompensa_enum;
BEGIN
    IF OLD.estado = 'ACTIVO' AND NEW.estado = 'CANCELADO' THEN
        SELECT recompensa_id, modo_recompensa INTO v_recompensa_id, v_modo
        FROM retos WHERE id = NEW.reto_id;

        IF v_modo = 'GARANTIZADA' AND v_recompensa_id IS NOT NULL THEN
            UPDATE recompensas SET stock = stock + 1 WHERE id = v_recompensa_id;
        END IF;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_liberar_reserva_si_no_completa
    AFTER UPDATE ON usuario_retos
    FOR EACH ROW
    WHEN (OLD.estado IS DISTINCT FROM NEW.estado)
    EXECUTE FUNCTION fn_liberar_reserva_si_no_completa();

-- 3) Job periódico (cron externo o pg_cron) que expira intentos vencidos.
--    Esto es lo que dispara la liberación de reserva del trigger de
--    arriba para retos GARANTIZADA que nadie completó a tiempo.
--    Sugerencia de programación: correr cada hora.
--    Ejemplo con pg_cron (si la extensión está disponible):
--      SELECT cron.schedule('expirar_retos', '0 * * * *', 'SELECT fn_expirar_retos_vencidos();');
CREATE OR REPLACE FUNCTION fn_expirar_retos_vencidos()
RETURNS INTEGER AS $$
DECLARE
    v_count INTEGER;
BEGIN
    UPDATE usuario_retos
    SET estado = 'CANCELADO'
    WHERE estado = 'ACTIVO'
      AND periodo_fin IS NOT NULL
      AND periodo_fin < now();
    GET DIAGNOSTICS v_count = ROW_COUNT;
    RETURN v_count;
END;
$$ LANGUAGE plpgsql;

-- 4) Todo canje descuenta stock de forma atómica -- EXCEPTO los que
--    vienen de un reto GARANTIZADA, porque esa unidad ya se reservó
--    al inscribirse (descontarla otra vez sería duplicar el gasto).
--    Para LIMITADA sí se valida/descuenta aquí: si ya no hay stock
--    cuando el usuario completa, el INSERT del canje falla -- es
--    responsabilidad de la aplicación revisar `retos_disponibilidad`
--    antes de intentar generarlo, y si no hay stock, omitir el canje
--    y entregar solo los puntos (no bloquear la finalización del reto).
CREATE OR REPLACE FUNCTION fn_descontar_stock_canje()
RETURNS TRIGGER AS $$
DECLARE
    v_stock INTEGER;
    v_modo  reto_modo_recompensa_enum;
BEGIN
    IF NEW.origen = 'RETO' THEN
        SELECT r.modo_recompensa INTO v_modo
        FROM usuario_retos ur JOIN retos r ON r.id = ur.reto_id
        WHERE ur.id = NEW.usuario_reto_id;

        IF v_modo = 'GARANTIZADA' THEN
            RETURN NEW; -- ya reservado al inscribirse, no descontar de nuevo
        END IF;
    END IF;

    SELECT stock INTO v_stock FROM recompensas WHERE id = NEW.recompensa_id FOR UPDATE;
    IF v_stock IS NULL OR v_stock <= 0 THEN
        RAISE EXCEPTION 'Recompensa % agotada; no se puede generar el canje', NEW.recompensa_id;
    END IF;
    UPDATE recompensas SET stock = stock - 1 WHERE id = NEW.recompensa_id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_descontar_stock_canje
    BEFORE INSERT ON canjes
    FOR EACH ROW EXECUTE FUNCTION fn_descontar_stock_canje();

-- Vista de lectura: para que el frontend pueda mostrar "agotado" en
-- la lista de retos sin tener que hacer el JOIN manualmente cada vez.
CREATE VIEW retos_disponibilidad AS
SELECT
    r.*,
    rec.stock AS stock_recompensa,
    CASE
        WHEN r.modo_recompensa = 'SIN_RECOMPENSA' THEN true
        WHEN r.modo_recompensa = 'LIMITADA' THEN true -- siempre se puede intentar; el riesgo se resuelve al completar
        ELSE COALESCE(rec.stock, 0) > 0                -- GARANTIZADA: solo disponible si hay para reservar
    END AS disponible
FROM retos r
LEFT JOIN recompensas rec ON rec.id = r.recompensa_id;


-- =========================================================
-- MÓDULO 21. IA
-- =========================================================

CREATE TABLE conversaciones_ia (
    id              BIGSERIAL PRIMARY KEY,
    session_id      UUID NOT NULL,
    usuario_id      UUID NOT NULL REFERENCES usuarios(id),
    role            conversacion_role_enum NOT NULL,
    contenido       TEXT NOT NULL,
    modelo          VARCHAR(80),
    tokens          INTEGER,
    temperatura     NUMERIC(3,2),
    latencia_ms     INTEGER,
    costo_usd       NUMERIC(10,6),
    finish_reason   VARCHAR(40),
    metadata        JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);


-- =========================================================
-- ÍNDICES
-- =========================================================

-- Geoespaciales
CREATE INDEX idx_poi_ubicacion ON poi USING GIST (ubicacion);
CREATE INDEX idx_visitas_ubicacion ON visitas USING GIST (ubicacion_usuario);

-- JSONB
CREATE INDEX idx_poi_metadata ON poi USING GIN (metadata);
CREATE INDEX idx_poi_horarios ON poi USING GIN (horarios);
CREATE INDEX idx_usuarios_configuracion ON usuarios USING GIN (configuracion);
CREATE INDEX idx_retos_configuracion ON retos USING GIN (configuracion);
CREATE INDEX idx_usuario_retos_progreso ON usuario_retos USING GIN (progreso);
CREATE INDEX idx_reglas_puntos_configuracion ON reglas_puntos USING GIN (configuracion);

-- BTREE
CREATE INDEX idx_usuarios_email ON usuarios (email);
CREATE INDEX idx_poi_slug ON poi (slug);
CREATE INDEX idx_poi_created_at ON poi (created_at);
CREATE INDEX idx_poi_categoria ON poi (categoria_id);
CREATE INDEX idx_poi_ciudad ON poi (ciudad_id);

-- Social: lecturas por poi_id que la UNIQUE(usuario_id, poi_id) de
-- calificaciones no cubre (esa indexa por usuario_id primero).
CREATE INDEX idx_comentarios_poi ON comentarios (poi_id);
CREATE INDEX idx_comentarios_usuario ON comentarios (usuario_id);
CREATE INDEX idx_calificaciones_poi ON calificaciones (poi_id);

-- Retos y relaciones
CREATE INDEX idx_retos_tipo_estado ON retos (tipo, estado);
CREATE INDEX idx_retos_recurrencia ON retos (recurrencia) WHERE estado = 'ACTIVO';
CREATE INDEX idx_retos_establecimiento ON retos (establecimiento_id) WHERE establecimiento_id IS NOT NULL;
CREATE INDEX idx_usuario_retos_periodo ON usuario_retos (reto_id, periodo_inicio);
CREATE INDEX idx_rachas_retos_usuario ON rachas_retos (usuario_id, reto_id);
CREATE INDEX idx_hitos_racha_reto ON hitos_racha (reto_id);
CREATE INDEX idx_hitos_racha_alcanzados_usuario ON hitos_racha_alcanzados (usuario_id, hito_id);
CREATE INDEX idx_poi_relaciones_origen ON poi_relaciones (poi_origen_id);
CREATE INDEX idx_poi_relaciones_destino ON poi_relaciones (poi_destino_id);
CREATE INDEX idx_poi_relaciones_activo ON poi_relaciones (activo) WHERE activo = true;
CREATE INDEX idx_sesiones_reto_usuario_reto ON sesiones_reto (usuario_reto_id);
CREATE INDEX idx_poi_fuente ON poi (fuente);
CREATE INDEX idx_movimientos_puntos_tipo ON movimientos_puntos (tipo_movimiento);

-- Movimientos de puntos
CREATE INDEX idx_movimientos_puntos_usuario ON movimientos_puntos (usuario_id);

-- Compras / establecimientos
CREATE INDEX idx_compras_establecimiento ON compras (establecimiento_id);
CREATE INDEX idx_compras_usuario ON compras (usuario_id);
-- "qué establecimientos administra este usuario" (reverso de la PK compuesta)
CREATE INDEX idx_establecimiento_usuarios_usuario ON establecimiento_usuarios (usuario_id);
CREATE INDEX idx_canjes_usuario_reto ON canjes (usuario_reto_id) WHERE usuario_reto_id IS NOT NULL;
CREATE INDEX idx_canjes_origen ON canjes (origen);

-- Conversaciones IA: acceso típico es "toda la sesión, en orden"
CREATE INDEX idx_conversaciones_ia_session ON conversaciones_ia (session_id, created_at);


CREATE VIEW saldo_puntos_usuario AS
SELECT usuario_id, SUM(puntos) AS saldo
FROM movimientos_puntos
GROUP BY usuario_id;

-- Sugerencia: si el volumen crece, convertir a MATERIALIZED VIEW
-- con REFRESH periódico (o vía trigger) en vez de vista simple.
