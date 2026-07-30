from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, DBError, RecordNotFoundError
from app.models.enums import PoiEstado
from app.models.gamificacion import ReglaPuntos
from app.models.movimiento_puntos import MovimientoPuntos
from app.models.poi import Poi
from app.models.usuario import Usuario
from app.repositories.comercial_repository import ComercialRepository
from app.repositories.movimiento_puntos_repository import MovimientoPuntosRepository
from app.schemas.comercial import (
    CompraCreate,
    CompraOut,
    EstablecimientoCreate,
    EstablecimientoMeItem,
    EstablecimientoOut,
    PaginatedEstablecimientosResponse,
    PaginatedPromocionesResponse,
    PromocionCreate,
    PromocionOut,
)

# Igual que POI: PENDIENTE es donde nace todo establecimiento/promoción
# (reutilizan poi_estado_enum). BORRADOR no aplica a estas dos entidades.
VALID_MODERATION_TRANSITIONS = {
    PoiEstado.PENDIENTE: {PoiEstado.APROBADO, PoiEstado.RECHAZADO},
    PoiEstado.APROBADO: {PoiEstado.INACTIVO},
    PoiEstado.INACTIVO: {PoiEstado.APROBADO},
}

# Si reglas_puntos no tiene una regla evento=COMPRA con "puntos_por_1000"
# propio, se usa esta proporción por defecto (1 punto por cada 1000 unidades
# de moneda gastadas — coincide con el ejemplo de doc/endpoints_api.md:
# valor=45000 -> puntos_otorgados=45).
PUNTOS_COMPRA_POR_1000_DEFECTO = 1


class ComercialService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = ComercialRepository(db)
        self.movimiento_repo = MovimientoPuntosRepository(db)

    # --- Establecimientos ---

    def _ensure_staff_or_admin(self, establecimiento_id: str, current_user: Usuario, is_admin: bool) -> None:
        if is_admin:
            return
        if not self.repository.es_staff(establecimiento_id, str(current_user.id)):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="No tienes permisos sobre este establecimiento"
            )

    def crear_establecimiento(
        self, datos: EstablecimientoCreate, current_user: Usuario, is_admin: bool
    ) -> EstablecimientoOut:
        try:
            poi = self.db.query(Poi).filter(Poi.id == datos.poi_id).first()
            if poi is None:
                raise RecordNotFoundError(f"Poi with id {datos.poi_id} not found")
            if not is_admin and str(poi.creado_por_usuario_id) != str(current_user.id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN, detail="El POI debe ser tuyo para registrar un negocio"
                )
            if poi.estado != PoiEstado.APROBADO:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="El POI debe estar APROBADO antes de registrar un establecimiento",
                )
            if self.repository.get_establecimiento_by_poi(str(datos.poi_id)) is not None:
                raise ConflictError("Este POI ya tiene un establecimiento registrado")

            establecimiento = self.repository.crear_establecimiento(
                {
                    "poi_id": datos.poi_id,
                    "nit": datos.nit,
                    "razon_social": datos.razon_social,
                    "tipo_negocio": datos.tipo_negocio,
                }
            )
            self.repository.agregar_staff(str(establecimiento.id), str(current_user.id), "dueño")
            self.db.commit()
            self.db.refresh(establecimiento)
            return EstablecimientoOut.model_validate(establecimiento)
        except HTTPException:
            raise
        except Exception as exc:
            self.db.rollback()
            raise DBError(f"Establecimiento creation failed: {str(exc)}") from exc

    def listar_mis_establecimientos(
        self, usuario_id: str, skip: int, limit: int, page: int
    ) -> PaginatedEstablecimientosResponse:
        rows = self.repository.list_mis_establecimientos(usuario_id, skip=skip, limit=limit)
        total = self.repository.count_mis_establecimientos(usuario_id)
        items = [
            EstablecimientoMeItem(
                id=e.id,
                poi_id=e.poi_id,
                nit=e.nit,
                razon_social=e.razon_social,
                tipo_negocio=e.tipo_negocio,
                fecha_afiliacion=e.fecha_afiliacion,
                estado=e.estado,
                cargo=cargo,
            )
            for e, cargo in rows
        ]
        return PaginatedEstablecimientosResponse(items=items, total=total, page=page, page_size=limit)

    def moderar_establecimiento(self, establecimiento_id: str, estado: str) -> EstablecimientoOut:
        establecimiento = self.repository.get_establecimiento(establecimiento_id)
        if establecimiento is None:
            raise RecordNotFoundError(f"Establecimiento with id {establecimiento_id} not found")

        try:
            estado_nuevo = PoiEstado(estado)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Estado inválido: {estado}")

        estado_actual = PoiEstado(establecimiento.estado)
        permitidos = VALID_MODERATION_TRANSITIONS.get(estado_actual, set())
        if estado_nuevo not in permitidos:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Transición inválida: {estado_actual.value} -> {estado_nuevo.value}",
            )

        establecimiento = self.repository.actualizar_estado_establecimiento(establecimiento, estado_nuevo.value)
        return EstablecimientoOut.model_validate(establecimiento)

    # --- Compras ---

    def registrar_compra(
        self, establecimiento_id: str, datos: CompraCreate, current_user: Usuario, is_admin: bool
    ) -> CompraOut:
        try:
            establecimiento = self.repository.get_establecimiento(establecimiento_id)
            if establecimiento is None:
                raise RecordNotFoundError(f"Establecimiento with id {establecimiento_id} not found")
            self._ensure_staff_or_admin(establecimiento_id, current_user, is_admin)

            if establecimiento.estado != PoiEstado.APROBADO:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="El establecimiento no está APROBADO",
                )

            cliente = self.db.query(Usuario).filter(Usuario.id == datos.usuario_id).first()
            if cliente is None or cliente.deleted_at is not None:
                raise RecordNotFoundError(f"Usuario with id {datos.usuario_id} not found")

            compra = self.repository.crear_compra(
                {
                    "usuario_id": datos.usuario_id,
                    "establecimiento_id": establecimiento_id,
                    "valor": datos.valor,
                    "moneda": datos.moneda.value,
                    "codigo_transaccion": datos.codigo_transaccion,
                }
            )

            puntos, regla_id = self._puntos_para_compra(datos.valor)
            self.movimiento_repo.crear(
                {
                    "usuario_id": datos.usuario_id,
                    "compra_id": compra.id,
                    "regla_id": regla_id,
                    "puntos": puntos,
                }
            )
            self.db.commit()
            self.db.refresh(compra)

            return CompraOut(
                id=compra.id,
                establecimiento_id=compra.establecimiento_id,
                usuario_id=compra.usuario_id,
                valor=compra.valor,
                moneda=compra.moneda,
                codigo_transaccion=compra.codigo_transaccion,
                estado=compra.estado,
                puntos_otorgados=puntos,
                created_at=compra.created_at,
            )
        except HTTPException:
            raise
        except Exception as exc:
            self.db.rollback()
            raise DBError(f"Compra creation failed: {str(exc)}") from exc

    def cancelar_compra(self, compra_id: str, current_user: Usuario, is_admin: bool) -> CompraOut:
        try:
            compra = self.repository.get_compra(compra_id)
            if compra is None:
                raise RecordNotFoundError(f"Compra with id {compra_id} not found")
            self._ensure_staff_or_admin(str(compra.establecimiento_id), current_user, is_admin)

            if compra.estado == "CANCELADA":
                raise ConflictError("Esta compra ya está cancelada")

            # Revierte los puntos otorgados por la compra original con un
            # movimiento negativo compensatorio — el ledger es append-only,
            # nunca se edita/borra la fila original (ver doc/logica_negocio.md).
            movimiento_original = (
                self.db.query(MovimientoPuntos).filter(MovimientoPuntos.compra_id == compra.id).first()
            )
            if movimiento_original is not None and movimiento_original.puntos > 0:
                self.movimiento_repo.crear(
                    {
                        "usuario_id": compra.usuario_id,
                        "compra_id": compra.id,
                        "regla_id": movimiento_original.regla_id,
                        "puntos": -movimiento_original.puntos,
                    }
                )

            compra = self.repository.cancelar_compra(compra, str(current_user.id))
            self.db.commit()
            self.db.refresh(compra)

            return CompraOut(
                id=compra.id,
                establecimiento_id=compra.establecimiento_id,
                usuario_id=compra.usuario_id,
                valor=compra.valor,
                moneda=compra.moneda,
                codigo_transaccion=compra.codigo_transaccion,
                estado=compra.estado,
                puntos_otorgados=0,
                created_at=compra.created_at,
            )
        except HTTPException:
            raise
        except Exception as exc:
            self.db.rollback()
            raise DBError(f"Compra cancel failed: {str(exc)}") from exc

    def _puntos_para_compra(self, valor: Decimal) -> "tuple[int, Optional[UUID]]":
        ahora = datetime.now(timezone.utc)
        reglas = (
            self.db.query(ReglaPuntos)
            .filter(
                ReglaPuntos.activo.is_(True),
                ReglaPuntos.configuracion["evento"].astext == "COMPRA",
                or_(ReglaPuntos.vigencia_inicio.is_(None), ReglaPuntos.vigencia_inicio <= ahora),
                or_(ReglaPuntos.vigencia_fin.is_(None), ReglaPuntos.vigencia_fin > ahora),
            )
            .order_by(ReglaPuntos.prioridad.desc())
            .all()
        )
        for regla in reglas:
            configuracion = regla.configuracion or {}
            ratio = configuracion.get("puntos_por_1000")
            if isinstance(ratio, (int, float)) and not isinstance(ratio, bool) and ratio > 0:
                return int(valor / 1000 * ratio), regla.id
        return int(valor / 1000 * PUNTOS_COMPRA_POR_1000_DEFECTO), None

    # --- Promociones ---

    def crear_promocion(
        self, establecimiento_id: str, datos: PromocionCreate, current_user: Usuario, is_admin: bool
    ) -> PromocionOut:
        establecimiento = self.repository.get_establecimiento(establecimiento_id)
        if establecimiento is None:
            raise RecordNotFoundError(f"Establecimiento with id {establecimiento_id} not found")
        self._ensure_staff_or_admin(establecimiento_id, current_user, is_admin)

        if establecimiento.estado != PoiEstado.APROBADO:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="El establecimiento no está APROBADO"
            )

        promocion = self.repository.crear_promocion(
            {
                "establecimiento_id": establecimiento_id,
                "titulo": datos.titulo,
                "descripcion": datos.descripcion,
                "inicio": datos.inicio,
                "fin": datos.fin,
            }
        )
        self.db.commit()
        self.db.refresh(promocion)
        return PromocionOut.model_validate(promocion)

    def moderar_promocion(
        self, establecimiento_id: str, promocion_id: str, estado: str, current_user: Usuario, is_admin: bool
    ) -> PromocionOut:
        if not is_admin:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Se requieren permisos de administrador")

        promocion = self.repository.get_promocion(promocion_id)
        if promocion is None or str(promocion.establecimiento_id) != str(establecimiento_id):
            raise RecordNotFoundError(f"Promocion with id {promocion_id} not found")

        try:
            estado_nuevo = PoiEstado(estado)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Estado inválido: {estado}")

        estado_actual = PoiEstado(promocion.estado)
        permitidos = VALID_MODERATION_TRANSITIONS.get(estado_actual, set())
        if estado_nuevo not in permitidos:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Transición inválida: {estado_actual.value} -> {estado_nuevo.value}",
            )

        promocion = self.repository.actualizar_estado_promocion(promocion, estado_nuevo.value)
        return PromocionOut.model_validate(promocion)

    def list_promociones_poi(self, poi_id: str, skip: int, limit: int, page: int) -> PaginatedPromocionesResponse:
        promociones = self.repository.list_promociones_vigentes_por_poi(poi_id, skip=skip, limit=limit)
        total = self.repository.count_promociones_vigentes_por_poi(poi_id)
        items = [PromocionOut.model_validate(p) for p in promociones]
        return PaginatedPromocionesResponse(items=items, total=total, page=page, page_size=limit)
