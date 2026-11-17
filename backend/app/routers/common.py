from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..models import Project


def get_in_workspace(db: Session, model, obj_id: str, workspace_id: str):
    obj = db.get(model, obj_id)
    if obj is None or obj.workspace_id != workspace_id:
        raise HTTPException(404, f"{model.__name__} not found")
    return obj


def check_project(db: Session, workspace_id: str, project_id: str | None) -> str | None:
    if not project_id:
        return None
    get_in_workspace(db, Project, project_id, workspace_id)
    return project_id
