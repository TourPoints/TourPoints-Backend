"""Scheduler in-process para jobs periódicos.

Neon no permite pg_cron (verificado: CREATE EXTENSION falla incluso en la
base `postgres` del proyecto — permission denied, requiere habilitación desde
el panel de Neon que no tenemos). Como el despliegue actual (ver
docker-compose.yml) es un único contenedor con un único proceso uvicorn,
un scheduler in-process es la opción de menor fricción: no agrega
infraestructura nueva. Si en el futuro se escala a múltiples réplicas, cada
una correría su propio scheduler — no rompe nada (el UPDATE de
fn_expirar_retos_vencidos es idempotente, WHERE estado='ACTIVO' no vuelve a
tocar filas ya CANCELADO), pero sería trabajo redundante; en ese escenario
conviene moverse a un cron externo pegándole a un endpoint dedicado."""
import logging

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import text

from app.database import SessionLocal

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()


def expirar_retos_vencidos() -> int:
    """Cancela los usuario_retos ACTIVO cuyo periodo_fin ya pasó (vía
    fn_expirar_retos_vencidos). Eso dispara trg_liberar_reserva_si_no_completa,
    que devuelve el stock reservado de retos GARANTIZADA que nadie completó
    ni abandonó a tiempo (ver POST /challenges/{id}/abandon)."""
    db = SessionLocal()
    try:
        cancelados = db.execute(text("SELECT fn_expirar_retos_vencidos()")).scalar()
        db.commit()
        if cancelados:
            logger.info("fn_expirar_retos_vencidos: %s intento(s) expirados", cancelados)
        return cancelados or 0
    except Exception:
        db.rollback()
        logger.exception("Error ejecutando fn_expirar_retos_vencidos")
        raise
    finally:
        db.close()


def iniciar_scheduler() -> None:
    if scheduler.running:
        return
    scheduler.add_job(
        expirar_retos_vencidos,
        trigger="cron",
        minute=0,  # cada hora en punto, misma cadencia que sugiere el comentario de fn_expirar_retos_vencidos en schem_posgrest.sql
        id="expirar_retos_vencidos",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    scheduler.start()
    logger.info("Scheduler iniciado: expirar_retos_vencidos corre cada hora")


def detener_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
