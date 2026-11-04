"""Visit isolation is independent of cookie authentication and patient ownership."""

from fastapi import HTTPException
from sqlmodel import select

from app.store.db import ChartConnection, Visit


def visit_access(session, visit_id, user, *, write=False, open_only=False, lock=False):
    visit = session.get(Visit, visit_id)
    if not visit:
        raise HTTPException(404, "Visit not found.")
    patient = user.role == "patient" and visit.patient_id == user.id and not write
    if not patient:
        query = select(ChartConnection).where(
            ChartConnection.patient_id == visit.patient_id,
            ChartConnection.doctor_id == user.id,
        )
        connection = session.exec(query.with_for_update() if lock else query).first()
        if user.role != "doctor" or not connection or connection.status != "approved":
            raise HTTPException(404, "Visit not found.")
        if visit.doctor_id != user.id and (write or visit.status != "completed"):
            raise HTTPException(404, "Visit not found.")
    if lock:
        # Same lock order as uploads/publication: consent, then visit.
        visit = session.exec(
            select(Visit)
            .where(Visit.id == visit_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        ).first()
        if not visit:
            raise HTTPException(404, "Visit not found.")
    if open_only and visit.status != "open":
        raise HTTPException(409, "This visit is completed. Start a new visit for new information.")
    return visit
