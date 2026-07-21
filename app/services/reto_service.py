import json
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

import redis
from fastapi import HTTPException, status
from sqlalchemy import or_
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, DBError, RecordNotFoundError, SinStockError
from app.models.canje import Canje
from app.models.enums import RetoEstado, RetoModoRecompensa, RetoRecurrencia, RetoTipo
from app.models.gamificacion import ReglaPuntos, Recompensa, Reto
from app.models.usuario import Usuario
from app.repositories.comercial_repository import ComercialRepository
from app.repositories.movimiento_puntos_repository import MovimientoPuntosRepository
from app.repositories.reto_repository import RetoRepository
from app.schemas.retos import (
    InsigniaAlcanzadaOut,
    InsigniaMini,
    PaginatedInsigniasResponse,
    PaginatedRetosResponse,
    PaginatedUsuarioRetosResponse,
    RachaOut,
    RetoCreate,
    RetoDetail,
    RetoListItem,
    RetoRecompensaMini,
    RetoProgressUpdate,
    SesionPuntoCreate,
    SesionPuntoOut,
    SesionRetoCreate,
    SesionRetoFinalizar,
    SesionRetoOut,
    SesionTrackOut,
    UsuarioRetoOut,
)
from app.utils.geo import haversine_metros
from app.utils.qr import generar_qr_canje

# Igual que POI/establecimientos: BORRADOR nace cuando lo propone un
# establecimiento (pendiente de aprobación); ADMIN nace directo en ACTIVO.
VALID_MODERATION_TRANSITIONS = {
    RetoEstado.BORRADOR: {RetoEstado.ACTIVO, RetoEstado.CANCELADO},
    RetoEstado.ACTIVO: {RetoEstado.CANCELADO},
}

# Si reglas_puntos no tiene una regla evento=RETO propia, se usa este default
# al completar un intento (no hay ejemplo en doc/endpoints_api.md para
# calibrar esto contra nada, a diferencia de VISITA/COMPRA).
PUNTOS_RETO_POR_DEFECTO = 50

# Vigencia de un canje emitido por completar un reto (mismo criterio que los
# canjes por puntos en recompensas_service.py).
VIGENCIA_CANJE_DIAS = 30

# TTL de seguridad sobre el tracking en Redis de una sesión RECORRIDO: si el
# cliente nunca llama a /finish, la key se autolimpia en vez de crecer para siempre.
SESION_TRACK_TTL_SEGUNDOS = 60 * 60 * 24


class RetoService:
    def __init__(self, db: Session, redis_client: redis.Redis):
        self.db = db
        self.repository = RetoRepository(db)
        self.comercial_repo = ComercialRepository(db)
        self.movimiento_repo = MovimientoPuntosRepository(db)
        self.redis = redis_client

    # --- Retos (plantillas) ---

    def _recompensa_mini(self, recompensa: Optional[Recompensa]) -> Optional[RetoRecompensaMini]:
        if recompensa is None:
            return None
        return RetoRecompensaMini(id=recompensa.id, nombre=recompensa.nombre, puntos=recompensa.puntos)

    def _disponible(self, reto: Reto, recompensa: Optional[Recompensa]) -> bool:
        """Mismo criterio que la vista `retos_disponibilidad` (ver doc/schem_posgrest.sql):
        SIN_RECOMPENSA y LIMITADA siempre disponibles (el riesgo de LIMITADA se
        resuelve al completar, no al listar); GARANTIZADA solo si hay stock para reservar."""
        if reto.modo_recompensa == RetoModoRecompensa.GARANTIZADA:
            return recompensa is not None and recompensa.stock > 0
        return True

    def _to_list_item(self, reto: Reto, recompensa: Optional[Recompensa]) -> RetoListItem:
        return RetoListItem(
            id=reto.id,
            nombre=reto.nombre,
            tipo=reto.tipo,
            recurrencia=reto.recurrencia,
            cantidad_requerida=reto.cantidad_requerida,
            modo_recompensa=reto.modo_recompensa,
            recompensa=self._recompensa_mini(recompensa),
            inicio=reto.inicio,
            fin=reto.fin,
            estado=reto.estado,
            disponible=self._disponible(reto, recompensa),
        )

    def _recompensas_por_id(self, retos: list) -> dict:
        ids = [r.recompensa_id for r in retos if r.recompensa_id]
        if not ids:
            return {}
        rows = self.db.query(Recompensa).filter(Recompensa.id.in_(ids)).all()
        return {r.id: r for r in rows}

    def list_retos(self, skip: int, limit: int, page: int, is_admin: bool, **filters) -> PaginatedRetosResponse:
        try:
            if not is_admin:
                filters.pop("estado", None)
            retos = self.repository.list(skip=skip, limit=limit, **filters)
            total = self.repository.count(**filters)
            recompensas = self._recompensas_por_id(retos)
            items = [self._to_list_item(r, recompensas.get(r.recompensa_id)) for r in retos]
            return PaginatedRetosResponse(items=items, total=total, page=page, page_size=limit)
        except Exception as exc:
            raise DBError(f"List retos failed: {str(exc)}") from exc

    def get_reto(self, reto_id: str) -> RetoDetail:
        reto = self.repository.get_by_id(reto_id)
        if reto is None:
            raise RecordNotFoundError(f"Reto with id {reto_id} not found")
        recompensa = None
        if reto.recompensa_id:
            recompensa = self.db.query(Recompensa).filter(Recompensa.id == reto.recompensa_id).first()
        base = self._to_list_item(reto, recompensa)
        return RetoDetail(
            **base.model_dump(),
            descripcion=reto.descripcion,
            establecimiento_id=reto.establecimiento_id,
            configuracion=reto.configuracion,
        )

    def crear_reto(self, data: RetoCreate, current_user: Usuario, is_admin: bool) -> RetoDetail:
        try:
            if data.recompensa_id is not None:
                recompensa = self.db.query(Recompensa).filter(Recompensa.id == data.recompensa_id).first()
                if recompensa is None:
                    raise RecordNotFoundError(f"Recompensa with id {data.recompensa_id} not found")

            if is_admin:
                estado = RetoEstado.ACTIVO
            else:
                if data.establecimiento_id is None:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail="establecimiento_id es obligatorio si no eres ADMIN",
                    )
                if not self.comercial_repo.es_staff(str(data.establecimiento_id), str(current_user.id)):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN, detail="No tienes permisos sobre este establecimiento"
                    )
                estado = RetoEstado.BORRADOR

            reto = self.repository.create(
                {
                    "nombre": data.nombre,
                    "descripcion": data.descripcion,
                    "tipo": data.tipo.value,
                    "recurrencia": data.recurrencia.value,
                    "cantidad_requerida": data.cantidad_requerida,
                    "recompensa_id": data.recompensa_id,
                    "modo_recompensa": data.modo_recompensa.value,
                    "creado_por_usuario_id": current_user.id,
                    "establecimiento_id": data.establecimiento_id,
                    "inicio": data.inicio,
                    "fin": data.fin,
                    "estado": estado.value,
                    "configuracion": data.configuracion,
                }
            )
            self.db.commit()
            return self.get_reto(str(reto.id))
        except HTTPException:
            raise
        except RecordNotFoundError:
            raise
        except Exception as exc:
            self.db.rollback()
            raise DBError(f"Reto creation failed: {str(exc)}") from exc

    def moderar_reto(self, reto_id: str, estado: str) -> RetoDetail:
        reto = self.repository.get_by_id(reto_id)
        if reto is None:
            raise RecordNotFoundError(f"Reto with id {reto_id} not found")

        try:
            estado_nuevo = RetoEstado(estado)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Estado inválido: {estado}")

        estado_actual = RetoEstado(reto.estado)
        permitidos = VALID_MODERATION_TRANSITIONS.get(estado_actual, set())
        if estado_nuevo not in permitidos:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Transición inválida: {estado_actual.value} -> {estado_nuevo.value}",
            )

        self.repository.actualizar_estado(reto, estado_nuevo.value)
        return self.get_reto(reto_id)

    # --- Cálculo de periodos ---

    @staticmethod
    def _siguiente_mes(dt: datetime) -> datetime:
        if dt.month == 12:
            return dt.replace(year=dt.year + 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        return dt.replace(month=dt.month + 1, day=1, hour=0, minute=0, second=0, microsecond=0)

    def _calcular_periodo(self, reto: Reto, ahora: datetime) -> "tuple[datetime, Optional[datetime]]":
        if reto.recurrencia == RetoRecurrencia.UNICA:
            return reto.inicio, reto.fin
        if reto.recurrencia == RetoRecurrencia.DIARIA:
            inicio = ahora.replace(hour=0, minute=0, second=0, microsecond=0)
            return inicio, inicio + timedelta(days=1)
        if reto.recurrencia == RetoRecurrencia.SEMANAL:
            inicio_dia = ahora.replace(hour=0, minute=0, second=0, microsecond=0)
            inicio = inicio_dia - timedelta(days=inicio_dia.weekday())
            return inicio, inicio + timedelta(days=7)
        # MENSUAL
        inicio = ahora.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return inicio, self._siguiente_mes(inicio)

    def _siguiente_periodo_esperado(self, periodo_inicio: datetime, recurrencia: RetoRecurrencia) -> datetime:
        if recurrencia == RetoRecurrencia.DIARIA:
            return periodo_inicio + timedelta(days=1)
        if recurrencia == RetoRecurrencia.SEMANAL:
            return periodo_inicio + timedelta(days=7)
        if recurrencia == RetoRecurrencia.MENSUAL:
            return self._siguiente_mes(periodo_inicio)
        return periodo_inicio

    # --- Inscripción ---

    def inscribirme(self, reto_id: str, current_user: Usuario) -> UsuarioRetoOut:
        reto = self.repository.get_by_id(reto_id)
        if reto is None:
            raise RecordNotFoundError(f"Reto with id {reto_id} not found")
        if reto.estado != RetoEstado.ACTIVO:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="El reto no está activo")

        ahora = datetime.now(timezone.utc)
        if ahora < reto.inicio:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="El reto todavía no comenzó")
        if reto.fin is not None and ahora >= reto.fin:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="El reto ya finalizó")

        periodo_inicio, periodo_fin = self._calcular_periodo(reto, ahora)

        if self.repository.get_usuario_reto_activo(str(current_user.id), reto_id, periodo_inicio) is not None:
            raise ConflictError("Ya existe un intento activo para este periodo")

        numero_intento = self.repository.get_max_numero_intento(str(current_user.id), reto_id, periodo_inicio) + 1

        try:
            usuario_reto = self.repository.crear_usuario_reto(
                {
                    "usuario_id": current_user.id,
                    "reto_id": reto_id,
                    "periodo_inicio": periodo_inicio,
                    "periodo_fin": periodo_fin,
                    "numero_intento": numero_intento,
                }
            )
        except SQLAlchemyError as exc:
            self.db.rollback()
            # El trigger fn_reservar_o_bloquear_reto lanza RAISE EXCEPTION si
            # el reto es GARANTIZADA y no queda stock para reservar.
            raise SinStockError("Sin stock disponible para reservar la recompensa") from exc

        if reto.recurrencia != RetoRecurrencia.UNICA:
            self._actualizar_racha_en_join(str(current_user.id), reto_id, reto.recurrencia, periodo_inicio)

        self.db.commit()
        self.db.refresh(usuario_reto)
        return UsuarioRetoOut.model_validate(usuario_reto)

    def abandonar(self, reto_id: str, current_user: Usuario) -> UsuarioRetoOut:
        """No estaba en el diseño original: sin esto, un intento GARANTIZADA
        deja el stock reservado atrapado para siempre (la única otra forma de
        liberarlo es `fn_expirar_retos_vencidos`, pensada para un cron externo
        que este entorno no tiene programado). El UPDATE dispara
        `trg_liberar_reserva_si_no_completa`, que devuelve el stock si aplica."""
        intento = self.repository.get_mi_intento_activo(str(current_user.id), reto_id)
        if intento is None:
            raise RecordNotFoundError("No tienes un intento activo para este reto")
        intento = self.repository.actualizar_usuario_reto(intento, {"estado": "CANCELADO"})
        return UsuarioRetoOut.model_validate(intento)

    def _actualizar_racha_en_join(
        self, usuario_id: str, reto_id: str, recurrencia: RetoRecurrencia, periodo_inicio: datetime
    ) -> None:
        racha = self.repository.get_racha(usuario_id, reto_id)
        if racha is None:
            racha = self.repository.crear_racha(usuario_id, reto_id)
        elif racha.ultimo_periodo_inicio is not None:
            esperado = self._siguiente_periodo_esperado(racha.ultimo_periodo_inicio, recurrencia)
            if periodo_inicio != esperado:
                racha.racha_actual = 0  # hueco entre periodos: se rompe la racha

        racha.ultimo_periodo_inicio = periodo_inicio
        racha.ultimo_periodo_completado = False
        self.repository.guardar_racha(racha)

    # --- Progreso / finalización ---

    def obtener_mi_progreso(self, reto_id: str, current_user: Usuario) -> UsuarioRetoOut:
        intento = self.repository.get_mi_intento_activo(str(current_user.id), reto_id)
        if intento is None:
            raise RecordNotFoundError("No tienes un intento activo para este reto")
        return UsuarioRetoOut.model_validate(intento)

    def listar_mis_intentos(self, usuario_id: str, skip: int, limit: int, page: int) -> PaginatedUsuarioRetosResponse:
        rows = self.repository.list_mis_usuario_retos(usuario_id, skip=skip, limit=limit)
        total = self.repository.count_mis_usuario_retos(usuario_id)
        items = [UsuarioRetoOut.model_validate(r) for r in rows]
        return PaginatedUsuarioRetosResponse(items=items, total=total, page=page, page_size=limit)

    def reportar_progreso(self, reto_id: str, data: RetoProgressUpdate, current_user: Usuario) -> UsuarioRetoOut:
        reto = self.repository.get_by_id(reto_id)
        if reto is None:
            raise RecordNotFoundError(f"Reto with id {reto_id} not found")

        intento = self.repository.get_mi_intento_activo(str(current_user.id), reto_id)
        if intento is None:
            raise RecordNotFoundError("No tienes un intento activo para este reto")

        intento = self._aplicar_incremento(reto, intento, data.incremento, data.detalle, current_user)
        return UsuarioRetoOut.model_validate(intento)

    def _aplicar_incremento(self, reto: Reto, intento, incremento: int, detalle: Optional[str], current_user: Usuario):
        """Cuerpo compartido por POST /challenges/{id}/progress y por el cierre de una
        sesión RECORRIDO (la distancia recorrida se acredita con el mismo camino)."""
        progreso = dict(intento.progreso or {"completados": [], "cantidad": 0})
        completados = list(progreso.get("completados", []))
        if detalle:
            completados.append(detalle)
        nueva_cantidad = min(progreso.get("cantidad", 0) + incremento, reto.cantidad_requerida)
        porcentaje = int(nueva_cantidad / reto.cantidad_requerida * 100)

        cambios = {"progreso": {"completados": completados, "cantidad": nueva_cantidad}, "porcentaje": porcentaje}
        se_completa = nueva_cantidad >= reto.cantidad_requerida
        if se_completa:
            cambios["estado"] = "FINALIZADO"
            cambios["fecha_completado"] = datetime.now(timezone.utc)

        intento = self.repository.actualizar_usuario_reto(intento, cambios)

        if se_completa:
            self._al_completar(reto, intento, current_user)

        return intento

    def _puntos_para_reto(self, reto: Reto) -> "tuple[int, Optional[UUID]]":
        ahora = datetime.now(timezone.utc)
        reglas = (
            self.db.query(ReglaPuntos)
            .filter(
                ReglaPuntos.activo.is_(True),
                ReglaPuntos.configuracion["evento"].astext == "RETO",
                or_(ReglaPuntos.vigencia_inicio.is_(None), ReglaPuntos.vigencia_inicio <= ahora),
                or_(ReglaPuntos.vigencia_fin.is_(None), ReglaPuntos.vigencia_fin > ahora),
            )
            .order_by(ReglaPuntos.prioridad.desc())
            .all()
        )
        for regla in reglas:
            configuracion = regla.configuracion or {}
            puntos = configuracion.get("puntos")
            if isinstance(puntos, int) and not isinstance(puntos, bool) and puntos > 0:
                return puntos, regla.id
        return PUNTOS_RETO_POR_DEFECTO, None

    def _al_completar(self, reto: Reto, intento, current_user: Usuario) -> None:
        """Otorga puntos + racha + hitos en una transacción. El canje de la
        recompensa (si aplica) se intenta en una transacción APARTE a
        propósito: si falla por falta de stock (modo LIMITADA), el rollback
        no debe arrastrar lo que el usuario ya ganó — 'nunca bloquear el
        logro, solo omitir el premio físico' (ver doc/logica_negocio.md)."""
        try:
            puntos, regla_id = self._puntos_para_reto(reto)
            if puntos > 0:
                self.movimiento_repo.crear(
                    {
                        "usuario_id": current_user.id,
                        "usuario_reto_id": intento.id,
                        "regla_id": regla_id,
                        "puntos": puntos,
                    }
                )

            if reto.recurrencia != RetoRecurrencia.UNICA:
                racha = self.repository.get_racha(str(current_user.id), str(reto.id))
                if racha is None:
                    racha = self.repository.crear_racha(str(current_user.id), str(reto.id))
                racha.racha_actual += 1
                racha.racha_maxima = max(racha.racha_maxima, racha.racha_actual)
                racha.ultimo_periodo_completado = True
                self.repository.guardar_racha(racha)

                for hito in self.repository.list_hitos_reto(str(reto.id)):
                    if hito.racha_requerida == racha.racha_actual:
                        self.repository.crear_hito_alcanzado(
                            {"usuario_id": current_user.id, "hito_id": hito.id, "usuario_reto_id": intento.id}
                        )
                        if hito.puntos_bonus > 0:
                            self.movimiento_repo.crear(
                                {
                                    "usuario_id": current_user.id,
                                    "usuario_reto_id": intento.id,
                                    "puntos": hito.puntos_bonus,
                                }
                            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        if reto.modo_recompensa in (RetoModoRecompensa.GARANTIZADA, RetoModoRecompensa.LIMITADA):
            try:
                self._emitir_canje_reto(reto, intento, current_user)
            except SQLAlchemyError:
                self.db.rollback()

    def _emitir_canje_reto(self, reto: Reto, intento, current_user: Usuario) -> None:
        ahora = datetime.now(timezone.utc)
        canje = Canje(
            usuario_id=current_user.id,
            recompensa_id=reto.recompensa_id,
            origen="RETO",
            usuario_reto_id=intento.id,
            codigo_qr=generar_qr_canje(),
            fecha_expira=ahora + timedelta(days=VIGENCIA_CANJE_DIAS),
            estado="PENDIENTE",
            created_at=ahora,
        )
        self.db.add(canje)
        self.db.flush()  # dispara fn_descontar_stock_canje (skip para GARANTIZADA, valida stock para LIMITADA)
        self.db.commit()

    # --- Sesiones (RECORRIDO) ---

    def crear_sesion(self, reto_id: str, data: SesionRetoCreate, current_user: Usuario) -> SesionRetoOut:
        reto = self.repository.get_by_id(reto_id)
        if reto is None:
            raise RecordNotFoundError(f"Reto with id {reto_id} not found")
        if reto.tipo != RetoTipo.RECORRIDO:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Solo los retos de tipo RECORRIDO tienen sesiones"
            )

        intento = self.repository.get_usuario_reto(str(data.usuario_reto_id))
        if (
            intento is None
            or str(intento.usuario_id) != str(current_user.id)
            or str(intento.reto_id) != str(reto_id)
        ):
            raise RecordNotFoundError("Intento no encontrado para este reto")
        if intento.estado != RetoEstado.ACTIVO:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="El intento no está activo")

        sesion = self.repository.crear_sesion({"usuario_reto_id": data.usuario_reto_id})
        return SesionRetoOut.model_validate(sesion)

    def _get_sesion_propia(self, reto_id: str, sesion_id: str, current_user: Usuario):
        sesion = self.repository.get_sesion(sesion_id)
        if sesion is None:
            raise RecordNotFoundError(f"Sesion with id {sesion_id} not found")

        intento = self.repository.get_usuario_reto(str(sesion.usuario_reto_id))
        if intento is None or str(intento.usuario_id) != str(current_user.id) or str(intento.reto_id) != str(reto_id):
            raise RecordNotFoundError(f"Sesion with id {sesion_id} not found")
        return sesion, intento

    def _redis_key(self, sesion_id: str) -> str:
        return f"session:points:{sesion_id}"

    def _leer_puntos(self, sesion_id: str) -> list:
        crudos = self.redis.lrange(self._redis_key(sesion_id), 0, -1)
        return [json.loads(item) for item in crudos]

    def _distancia_total(self, puntos: list) -> float:
        total = 0.0
        for anterior, actual in zip(puntos, puntos[1:]):
            total += haversine_metros(anterior["lat"], anterior["lng"], actual["lat"], actual["lng"])
        return total

    def agregar_punto(
        self, reto_id: str, sesion_id: str, data: SesionPuntoCreate, current_user: Usuario
    ) -> None:
        sesion, _ = self._get_sesion_propia(reto_id, sesion_id, current_user)
        if sesion.estado != RetoEstado.ACTIVO:
            raise ConflictError("Esta sesión ya está finalizada")

        punto = {"lat": data.lat, "lng": data.lng, "ts": datetime.now(timezone.utc).isoformat()}
        key = self._redis_key(sesion_id)
        self.redis.rpush(key, json.dumps(punto))
        self.redis.expire(key, SESION_TRACK_TTL_SEGUNDOS)

    def obtener_track(self, reto_id: str, sesion_id: str, current_user: Usuario) -> SesionTrackOut:
        self._get_sesion_propia(reto_id, sesion_id, current_user)
        puntos = self._leer_puntos(sesion_id)
        return SesionTrackOut(
            puntos=[SesionPuntoOut(**punto) for punto in puntos],
            distancia_metros=self._distancia_total(puntos),
        )

    def finalizar_sesion(
        self, reto_id: str, sesion_id: str, data: SesionRetoFinalizar, current_user: Usuario
    ) -> SesionRetoOut:
        sesion, intento = self._get_sesion_propia(reto_id, sesion_id, current_user)
        if sesion.estado != RetoEstado.ACTIVO:
            raise ConflictError("Esta sesión ya está finalizada")

        puntos = self._leer_puntos(sesion_id)
        distancia_metros = self._distancia_total(puntos)

        sesion = self.repository.finalizar_sesion(sesion, data.estado, datetime.now(timezone.utc))
        self.redis.delete(self._redis_key(sesion_id))

        if distancia_metros > 0 and intento.estado == RetoEstado.ACTIVO:
            reto = self.repository.get_by_id(reto_id)
            self._aplicar_incremento(reto, intento, int(distancia_metros), None, current_user)

        salida = SesionRetoOut.model_validate(sesion)
        salida.distancia_metros = distancia_metros
        return salida

    # --- Racha / insignias ---

    def obtener_racha(self, reto_id: str, current_user: Usuario) -> RachaOut:
        racha = self.repository.get_racha(str(current_user.id), reto_id)
        if racha is None:
            return RachaOut(racha_actual=0, racha_maxima=0)
        return RachaOut(racha_actual=racha.racha_actual, racha_maxima=racha.racha_maxima)

    def listar_mis_insignias(self, usuario_id: str, skip: int, limit: int, page: int) -> PaginatedInsigniasResponse:
        rows = self.repository.list_insignias_usuario(usuario_id, skip=skip, limit=limit)
        total = self.repository.count_insignias_usuario(usuario_id)
        items = [
            InsigniaAlcanzadaOut(
                insignia=InsigniaMini.model_validate(insignia),
                recompensa_otorgada=alcanzado.recompensa_otorgada,
                created_at=alcanzado.created_at,
            )
            for alcanzado, insignia in rows
        ]
        return PaginatedInsigniasResponse(items=items, total=total, page=page, page_size=limit)
