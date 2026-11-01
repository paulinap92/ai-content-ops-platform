from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from canarias_site.db.base import Base


class GenericRepository[T: Base]:
    def __init__(
        self,
        model_type: type[T],
        session: AsyncSession,
    ) -> None:
        self.model_type = model_type
        self.session = session

    def add(self, instance: T) -> T:
        self.session.add(instance)
        return instance

    def add_all(self, instances: Iterable[T]) -> None:
        self.session.add_all(list(instances))

    async def get(self, pk: object) -> T | None:
        return await self.session.get(self.model_type, pk)

    async def get_all(self) -> list[T]:
        stmt = select(self.model_type)
        result = await self.session.scalars(stmt)
        return list(result.all())

    async def find_all(self) -> list[T]:
        return await self.get_all()

    async def delete(self, instance: T) -> None:
        await self.session.delete(instance)

    async def delete_by_id(self, pk: object) -> None:
        instance = await self.get(pk)
        if instance is not None:
            await self.session.delete(instance)

    async def commit(self) -> None:
        await self.session.commit()

    async def rollback(self) -> None:
        await self.session.rollback()

    async def flush(self) -> None:
        await self.session.flush()

    async def refresh(self, instance: T) -> None:
        await self.session.refresh(instance)

    async def add_and_commit(self, instance: T) -> T:
        self.session.add(instance)
        await self.session.commit()
        return instance

    async def delete_and_commit(self, instance: T) -> None:
        await self.session.delete(instance)
        await self.session.commit()

