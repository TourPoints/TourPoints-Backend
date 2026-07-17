from datetime import datetime, timedelta, timezone
from hashlib import sha1
from typing import List, Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.exceptions import (
    ConflictError,
    DBError,
    InternalServiceError,
    PuntosInsuficientesError,
    RecordNotFoundError,
    SinStockError,
)
from app.models.canje import Canje
from app.models.gamificacion import Recompensa
from app.models.poi import Poi
from app.models.usuario import Usuario
from app.repositories.canje_repository import CanjeRepository
from app.repositories.movimiento_puntos_repository import MovimientoPuntosRepository
from app.repositories.puntos_repository import PuntosRepository
from app.repositories.recompensa_repository import RecompensaRepository
from app.schemas.gamificacion import (
    CanjeOut,
    CanjeValidacionOut,
    PaginatedCanjesResponse,
    RecompensaCreate,
    RecompensaOut,
    RecompensaUpdate,
)
from app.schemas.social import UsuarioMini
from app.utils.qr import generar_qr_canje

# Vigencia de un canje una vez emitido.
VIGENCIA_CANJE_DIAS = 30


def _to_out(recompensa: Recompensa) -> RecompensaOut:
    """Arma RecompensaOut calculando `disponible` (no vive en el ORM)."""
    # `disponible` no es una columna del ORM, asi que se inyecta aparte: si se
    # iterara RecompensaOut.model_fields el getattr(recompensa, "disponible")
    # lanzaria AttributeError (rompe la respuesta despues del commit).
    data = {
        "id": recompensa.id,
        "poi_id": recompensa.poi_id,
        "nombre": recompensa.nombre,
        "descripcion": recompensa.descripcion,
        "stock": recompensa.stock,
        "puntos": recompensa.puntos,
        "estado": recompensa.estado,
    }
    data["disponible"] = recompensa.stock > 0
    return RecompensaOut.model_validate(data)


class RecompensasService:
    def __init__(self, db: Session):
        self.db = db
        self.recompensa_repo = RecompensaRepository(db)
        self.canje_repo = CanjeRepository(db)
        self.movimiento_repo = MovimientoPuntosRepository(db)
        self.puntos_repo = PuntosRepository(db)

    def crear(self, datos: RecompensaCreate) -> RecompensaOut:
        """Crea una recompensa en estado APROBADO (fijo, no viene del body).
        Si trae poi_id, valida que el POI exista."""
        if datos.poi_id is not None:
            poi = self.db.query(Poi).filter(Poi.id == datos.poi_id).first()
            if poi is None:
                raise RecordNotFoundError(f"POI with id {datos.poi_id} not found")

        recompensa = Recompensa(
            poi_id=datos.poi_id,
            nombre=datos.nombre,
            descripcion=datos.descripcion,
            stock=datos.stock,
            puntos=datos.puntos,
            estado="APROBADO",
        )
        self.recompensa_repo.crear(recompensa)
        self.db.commit()
        self.db.refresh(recompensa)
        return _to_out(recompensa)

    def actualizar(self, id: str, cambios: RecompensaUpdate) -> RecompensaOut:
        """PATCH parcial sobre la recompensa."""
        recompensa = self.recompensa_repo.obtener_por_id(id)
        if recompensa is None:
            raise RecordNotFoundError(f"Recompensa with id {id} not found")

        update_data = cambios.model_dump(exclude_unset=True)
        if update_data:
            self.recompensa_repo.actualizar(recompensa, update_data)
            self.db.commit()
            self.db.refresh(recompensa)
        return _to_out(recompensa)

    def listar(
        self,
        poi_id: Optional[str] = None,
        estado: Optional[str] = None,
        solo_aprobado: bool = True,
        limit: int = 100,
        offset: int = 0,
    ) -> List[RecompensaOut]:
        """Lista recompensas. `solo_aprobado=True` fuerza estado=APROBADO
        para usuarios comunes (ignora el param estado si vino)."""
        if solo_aprobado:
            estado = "APROBADO"
        recompensas = self.recompensa_repo.listar(
            poi_id=poi_id, estado=estado, limit=limit, offset=offset
        )
        return [_to_out(r) for r in recompensas]

    def obtener(self, id: str, solo_aprobado: bool = True) -> RecompensaOut:
        recompensa = self.recompensa_repo.obtener_por_id(id)
        if recompensa is None:
            raise RecordNotFoundError(f"Recompensa with id {id} not found")
        if solo_aprobado and recompensa.estado != "APROBADO":
            # Una recompensa no publicada "no existe" para el usuario comun.
            raise RecordNotFoundError(f"Recompensa with id {id} not found")
        return _to_out(recompensa)

    def canjear(self, usuario_id: str, recompensa_id: str) -> CanjeOut:
        """Canjea una recompensa y evita dejar la sesión en estado abortado."""
        try:
            return self._canjear(usuario_id, recompensa_id)
        except HTTPException:
            # Los errores de negocio ya tienen un código HTTP y no deben
            # convertirse en un 400 genérico.
            raise
        except Exception as exc:
            self.db.rollback()
            raise InternalServiceError(
                f"Error en el proceso de canje: {str(exc)}"
            ) from exc

    def _canjear(self, usuario_id: str, recompensa_id: str) -> CanjeOut:
        """Canjea una recompensa por puntos. Orden estricto (no reordenar):
        lock por usuario_id -> recompensa con lock -> validar saldo ->
        QR/expira -> insertar canje -> insertar movimiento negativo -> commit.
        """
        # 1) Advisory lock por usuario_id: serializa TODOS los canjes de ese
        #    usuario (cualquier recompensa) para que SELECT SUM + INSERT del
        #    movimiento negativo sean atomicos respecto del saldo. El stock
        #    no se lockea aca: ya lo protege el trigger.
        #
        # Nota: pg_advisory_xact_lock solo existe en PostgreSQL. Evitar ejecutar
        # la sentencia si la conexión no es Postgres (por ejemplo durante pruebas
        # con SQLite o entornos locales), para que no produzca un error 500.
        dialect = None
        try:
            bind = None
            try:
                bind = self.db.get_bind()
            except Exception:
                bind = getattr(self.db, "bind", None)

            if bind is not None and getattr(bind, "dialect", None) is not None:
                dialect = getattr(bind.dialect, "name", None)
        except Exception:
            dialect = None

        if dialect == "postgresql":
            try:
                # PostgreSQL recibe dos claves INTEGER (int4). Se usan los
                # primeros 64 bits del SHA-1 y se interpretan con signo para
                # no invocar por accidente una sobrecarga bigint inexistente.
                uid_hash = sha1(str(usuario_id).encode()).digest()
                key1 = int.from_bytes(uid_hash[:4], byteorder="big", signed=True)
                key2 = int.from_bytes(uid_hash[4:8], byteorder="big", signed=True)
                self.db.execute(
                    text("SELECT pg_advisory_xact_lock(:key1, :key2)"),
                    {"key1": key1, "key2": key2},
                )
            except Exception as exc:
                # Solo traducir a DBError si realmente falló la adquisición del
                # lock en Postgres — eso es indicativo de un problema real en
                # el servidor de BD.
                import logging

                logging.exception("Error intentando obtener advisory lock: %s", exc)
                raise DBError("Error acquiring advisory lock") from exc
        # Si no es Postgres, simplemente saltar el advisory lock (ej.: tests/local)

        # 2) Recompensa con lock de fila. Recien aca tenemos recompensa.puntos.
        recompensa = self.recompensa_repo.obtener_con_lock(recompensa_id)
        if recompensa is None:
            raise RecordNotFoundError(f"Recompensa with id {recompensa_id} not found")
        if recompensa.estado != "APROBADO":
            raise RecordNotFoundError(f"Recompensa with id {recompensa_id} not found")
        if recompensa.stock <= 0:
            raise SinStockError()

        # 3) Validar saldo contra la vista.
        saldo = self.puntos_repo.obtener_saldo(usuario_id)
        if saldo < recompensa.puntos:
            raise PuntosInsuficientesError()

        # 4) QR + vigencia. Un unico timestamp para que created_at y
        #    fecha_expira sean consistentes entre si (no confiar en el default
        #    de la columna ni en un flush a medias).
        ahora = datetime.utcnow()
        fecha_expira = ahora + timedelta(days=VIGENCIA_CANJE_DIAS)

        # 5) Insertar el canje. codigo_qr se genera ANTES del insert (es
        #    NOT NULL y UNIQUE, y el trigger corre BEFORE INSERT). El trigger
        #    descuenta stock; si esta agotado, RAISE EXCEPTION -> la
        #    transaccion queda abortada y hay que rollbackear primero.
        codigo_qr = generar_qr_canje()
        try:
            canje = self.canje_repo.crear(
                {
                    "usuario_id": usuario_id,
                    "recompensa_id": recompensa_id,
                    "origen": "PUNTOS",
                    "codigo_qr": codigo_qr,
                    "fecha_expira": fecha_expira,
                    "estado": "PENDIENTE",
                    "created_at": ahora,
                }
            )
        except SQLAlchemyError as exc:
            self.db.rollback()
            # El trigger falla con un mensaje que menciona "agotada".
            import logging
            logging.error(f"Stock agotado en canje: {exc}")
            raise SinStockError() from exc

        # 6) Movimiento negativo (tipo_movimiento es COMPUTado a partir de
        #    canje_id, no se setea a mano).
        self.movimiento_repo.crear(
            {
                "usuario_id": usuario_id,
                "canje_id": canje.id,
                "puntos": -recompensa.puntos,
            }
        )

        # 7) Commit.
        self.db.commit()
        self.db.refresh(canje)

        return CanjeOut(
            id=canje.id,
            recompensa=_to_out(recompensa),
            origen=canje.origen,
            codigo_qr=canje.codigo_qr,
            estado=canje.estado,
            fecha_expira=canje.fecha_expira,
            created_at=canje.created_at,
        )

    def listar_mis_canjes(self, usuario_id: str, skip: int, limit: int, page: int) -> PaginatedCanjesResponse:
        """Historial paginado de canjes del usuario autenticado, más reciente primero."""
        canjes = self.canje_repo.listar_por_usuario(usuario_id, skip=skip, limit=limit)
        total = self.canje_repo.contar_por_usuario(usuario_id)
        items = [self._canje_a_out(c) for c in canjes]
        return PaginatedCanjesResponse(items=items, total=total, page=page, page_size=limit)

    def obtener_canje(self, id: str, current_user: Usuario, is_admin: bool) -> CanjeValidacionOut:
        """Detalle de un canje. Solo el dueño o un ADMIN (ver nota sobre
        alcance de ESTABLECIMIENTO en get_admin_or_establecimiento_user)."""
        canje = self.canje_repo.obtener_por_id(id)
        if canje is None:
            raise RecordNotFoundError(f"Canje with id {id} not found")
        if not is_admin and str(canje.usuario_id) != str(current_user.id):
            # 404, no 403: no revelar que el canje existe si no es tuyo (mismo
            # criterio que GET /poi/{id} con un POI no publicado).
            raise RecordNotFoundError(f"Canje with id {id} not found")
        return self._canje_a_validacion_out(canje)

    def validar_qr(self, codigo_qr: str) -> CanjeValidacionOut:
        """Redime un canje presentado físicamente por su codigo_qr. Solo
        ADMIN/ESTABLECIMIENTO llegan aquí (autorización en el router).
        PENDIENTE -> REDIMIDO, o marca EXPIRADO de forma perezosa si ya venció."""
        canje = self.canje_repo.obtener_por_codigo_qr(codigo_qr)
        if canje is None:
            raise RecordNotFoundError("Código QR no encontrado")

        if canje.estado == "PENDIENTE" and canje.fecha_expira is not None:
            if datetime.now(timezone.utc) > canje.fecha_expira:
                self.canje_repo.actualizar(canje, {"estado": "EXPIRADO"})
                self.db.commit()
                raise ConflictError("Este código ya expiró")

        if canje.estado != "PENDIENTE":
            estado_legible = "redimido" if canje.estado == "REDIMIDO" else "expirado"
            raise ConflictError(f"Este código ya fue {estado_legible}")

        self.canje_repo.actualizar(
            canje, {"estado": "REDIMIDO", "fecha_redencion": datetime.now(timezone.utc)}
        )
        self.db.commit()
        self.db.refresh(canje)

        return self._canje_a_validacion_out(canje)

    def _canje_a_out(self, canje: Canje) -> CanjeOut:
        recompensa = self.recompensa_repo.obtener_por_id(str(canje.recompensa_id))
        return CanjeOut(
            id=canje.id,
            recompensa=_to_out(recompensa),
            origen=canje.origen,
            codigo_qr=canje.codigo_qr,
            estado=canje.estado,
            fecha_expira=canje.fecha_expira,
            created_at=canje.created_at,
        )

    def _canje_a_validacion_out(self, canje: Canje) -> CanjeValidacionOut:
        recompensa = self.recompensa_repo.obtener_por_id(str(canje.recompensa_id))
        usuario = self.db.query(Usuario).filter(Usuario.id == canje.usuario_id).first()
        return CanjeValidacionOut(
            id=canje.id,
            recompensa=_to_out(recompensa),
            usuario=UsuarioMini.model_validate(usuario),
            origen=canje.origen,
            estado=canje.estado,
            fecha_expira=canje.fecha_expira,
            fecha_redencion=canje.fecha_redencion,
            created_at=canje.created_at,
        )
