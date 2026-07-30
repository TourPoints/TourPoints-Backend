from typing import Generic, TypeVar, Type, List
from sqlalchemy.orm import Session
from sqlalchemy.exc import NoResultFound, StatementError
import sqlalchemy
from app.core.exceptions import RecordNotFoundError, DBError

ModelT = TypeVar('ModelT')


class BaseRepository(Generic[ModelT]):
    def __init__(self, model: Type[ModelT]) -> None:
        self.model = model
        super().__init__()

    def get(self, id: str) -> ModelT:
        try:
            return self._get_by_id(id)
        except (NoResultFound, StatementError) as e:
            raise RecordNotFoundError(f"{self.model.__name__} with id {id} not found") from e

    def _get_by_id(self, id: str) -> ModelT:
        raise NotImplementedError

    def list(self, skip: int = 0, limit: int = 100, **filters) -> List[ModelT]:
        raise NotImplementedError

    def create(self, data: dict) -> ModelT:
        raise NotImplementedError

    def update(self, id: str, data: dict) -> ModelT:
        raise NotImplementedError

    def delete(self, id: str) -> None:
        raise NotImplementedError

    def _session(self) -> Session:
        from app.database import get_db
        return get_db()

    def _query(self) -> sqlalchemy.orm.Query:
        return self._session().query(self.model)

    def _handle_db_error(self, exc: Exception) -> None:
        raise DBError(str(exc))
