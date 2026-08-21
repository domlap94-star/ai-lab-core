from sqlalchemy.orm import Session

from app.models.project import Project
from app.models.user import User
from app.repositories.client_repository import ClientRepository
from app.repositories.project_repository import ProjectRepository
from app.schemas.project import ProjectCreate, ProjectPage, ProjectUpdate


class ProjectNotFoundError(Exception):
    pass


class ProjectClientNotFoundError(Exception):
    pass


class ProjectLinkedWorkItemError(RuntimeError):
    pass


class ProjectService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = ProjectRepository(db)
        self.clients = ClientRepository(db)

    @staticmethod
    def _read(project: Project) -> Project:
        project.client_name = project.client.name
        return project

    def get(self, project_id: int) -> Project:
        project = self.repository.get(project_id)
        if project is None:
            raise ProjectNotFoundError
        return self._read(project)

    def get_page(self, *, search: str | None, client_id: int | None, status: str | None, skip: int, limit: int) -> ProjectPage:
        items, total = self.repository.get_page(search=search, client_id=client_id, status=status, skip=skip, limit=limit)
        return ProjectPage(items=[self._read(item) for item in items], total=total, skip=skip, limit=limit)

    def create(self, data: ProjectCreate, actor: User) -> Project:
        if self.clients.get(data.client_id) is None:
            raise ProjectClientNotFoundError
        project = Project(**data.model_dump(), created_by_user_id=actor.id, updated_by_user_id=actor.id)
        self.repository.create(project)
        return self.get(project.id)

    def update(self, project_id: int, data: ProjectUpdate, actor: User) -> Project:
        project = self.get(project_id)
        if project.work_item_id is not None:
            raise ProjectLinkedWorkItemError("linked_project_managed_by_work_item")
        payload = data.model_dump(exclude_unset=True)
        if "client_id" in payload and self.clients.get(payload["client_id"]) is None:
            raise ProjectClientNotFoundError
        current = {
            key: getattr(project, key)
            for key in ProjectCreate.model_fields
        }
        validated = ProjectCreate.model_validate({**current, **payload}).model_dump()
        for key, value in validated.items():
            setattr(project, key, value)
        project.updated_by_user_id = actor.id
        self.repository.update(project)
        return self.get(project.id)

    def delete(self, project_id: int, actor: User) -> None:
        project = self.get(project_id)
        if project.work_item_id is not None:
            raise ProjectLinkedWorkItemError("linked_project_managed_by_work_item")
        project.updated_by_user_id = actor.id
        self.repository.soft_delete(project)
