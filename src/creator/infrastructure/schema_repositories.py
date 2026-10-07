from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import Select, asc, desc, func, select
from sqlalchemy.orm import Session

from creator.infrastructure import models, schema_models
from creator.repositories import (
    BrandAssetRecord,
    CampaignRecord,
    GeneratedImageRecord,
    Page,
    PageRequest,
    PersonaRecord,
    PlanningRecord,
    PostStructureRecord,
)


def _record(row: schema_models.Campaign) -> CampaignRecord:
    return CampaignRecord(
        id=row.id,
        workspace_id=row.workspace_id,
        created_by=row.created_by,
        name=row.name,
        description=row.description,
        target_audience=row.target_audience,
        objectives=row.objectives,
        voice=row.voice,
        start_at=row.start_at,
        end_at=row.end_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
        deleted_at=row.deleted_at,
    )


class _CampaignRepositoryBase:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(
        self,
        *,
        workspace_id: UUID,
        created_by: UUID,
        name: str,
        description: str | None = None,
        target_audience: str | None = None,
        objectives: str | None = None,
        voice: str | None = None,
        start_at: datetime | None = None,
        end_at: datetime | None = None,
    ) -> CampaignRecord:
        row = schema_models.Campaign(
            workspace_id=workspace_id,
            created_by=created_by,
            name=name,
            description=description,
            target_audience=target_audience,
            objectives=objectives,
            voice=voice,
            start_at=start_at,
            end_at=end_at,
        )
        self._session.add(row)
        self._session.flush()
        return _record(row)

    def update(self, *, campaign_id: UUID, fields: dict[str, object]) -> CampaignRecord:
        row = self._session.get(schema_models.Campaign, campaign_id)
        if row is None or row.deleted_at is not None:
            raise ValueError("Campaign not found")
        for name, value in fields.items():
            setattr(row, name, value)
        row.updated_at = datetime.now(UTC)
        self._session.flush()
        return _record(row)

    def soft_delete(self, *, campaign_id: UUID) -> None:
        row = self._session.get(schema_models.Campaign, campaign_id)
        if row is None or row.deleted_at is not None:
            raise ValueError("Campaign not found")
        timestamp = datetime.now(UTC)
        row.deleted_at = timestamp
        row.updated_at = timestamp
        self._session.flush()


def _planning_record(row: schema_models.Planning) -> PlanningRecord:
    return PlanningRecord(
        id=row.id,
        brand_id=row.brand_id,
        campaign_id=row.campaign_id,
        persona_id=row.persona_id,
        created_by=row.created_by,
        info=row.planning_info,
        static_amount=row.planning_static_amount,
        carousel_amount=row.planning_carousel_amount,
        stories_amount=row.planning_stories_amount,
        special_dates=row.planning_special_dates,
        start_period=row.planning_start_period,
        end_period=row.planning_end_period,
        created_at=row.created_at,
        updated_at=row.updated_at,
        deleted_at=row.deleted_at,
    )


def _persona_record(row: schema_models.Persona) -> PersonaRecord:
    return PersonaRecord(
        id=row.id,
        brand_id=row.brand_id,
        created_by=row.created_by,
        name=row.name,
        age=row.age,
        gender=row.gender,
        main_goal=row.main_goal,
        challenge=row.challenge,
        interest=row.interest,
        routine=row.routine,
        journey=row.journey,
        trigger=row.trigger,
        created_at=row.created_at,
        updated_at=row.updated_at,
        deleted_at=row.deleted_at,
    )


def _generated_image_record(row: schema_models.GeneratedImage) -> GeneratedImageRecord:
    return GeneratedImageRecord(
        id=row.id,
        workspace_id=row.workspace_id,
        design_structure_id=row.design_structure_id,
        signed_url=row.signed_url,
        size=row.size,
        resolution=row.resolution,
        image_ratio=row.image_ratio,
        status=row.image_status,
        created_at=row.created_at,
        updated_at=row.updated_at,
        deleted_at=row.deleted_at,
    )


class SqlAlchemyGeneratedImageRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_for_user(self, *, user_id: UUID, image_id: UUID) -> GeneratedImageRecord | None:
        row = self._session.scalars(
            select(schema_models.GeneratedImage)
            .join(
                models.WorkspaceMembership,
                models.WorkspaceMembership.workspace_id
                == schema_models.GeneratedImage.workspace_id,
            )
            .where(
                schema_models.GeneratedImage.id == image_id,
                schema_models.GeneratedImage.deleted_at.is_(None),
                models.WorkspaceMembership.user_id == user_id,
                models.WorkspaceMembership.deleted_at.is_(None),
            )
        ).one_or_none()
        return _generated_image_record(row) if row else None


class SqlAlchemyPersonaRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, *, created_by: UUID, **fields: object) -> PersonaRecord:
        row = schema_models.Persona(created_by=created_by, **fields)
        self._session.add(row)
        self._session.flush()
        return _persona_record(row)

    def list_for_user(
        self,
        *,
        user_id: UUID,
        brand_id: UUID | None = None,
        page: PageRequest | None = None,
    ) -> Page[PersonaRecord]:
        page = page or PageRequest()
        statement = self._select(user_id)
        count = (
            select(func.count())
            .select_from(schema_models.Persona)
            .join(models.Brand, models.Brand.id == schema_models.Persona.brand_id)
            .join(
                models.WorkspaceMembership,
                models.WorkspaceMembership.workspace_id == models.Brand.workspace_id,
            )
            .where(
                models.WorkspaceMembership.user_id == user_id,
                models.WorkspaceMembership.deleted_at.is_(None),
                schema_models.Persona.deleted_at.is_(None),
                models.Brand.deleted_at.is_(None),
            )
        )
        if brand_id is not None:
            statement = statement.where(schema_models.Persona.brand_id == brand_id)
            count = count.where(schema_models.Persona.brand_id == brand_id)
        order = (
            asc(schema_models.Persona.created_at)
            if page.sort == "asc"
            else desc(schema_models.Persona.created_at)
        )
        rows = self._session.scalars(
            statement.order_by(order).offset(page.offset).limit(page.limit)
        ).all()
        return Page(
            items=[_persona_record(row) for row in rows],
            total=self._session.scalar(count) or 0,
            page=page.page,
            limit=page.limit,
        )

    def get_for_user(self, *, user_id: UUID, persona_id: UUID) -> PersonaRecord | None:
        row = self._session.scalars(
            self._select(user_id).where(schema_models.Persona.id == persona_id)
        ).one_or_none()
        return _persona_record(row) if row else None

    def update(self, *, persona_id: UUID, fields: dict[str, object]) -> PersonaRecord:
        row = self._session.get(schema_models.Persona, persona_id)
        if row is None or row.deleted_at is not None:
            raise ValueError("Persona not found")
        for name, value in fields.items():
            setattr(row, name, value)
        row.updated_at = datetime.now(UTC)
        self._session.flush()
        return _persona_record(row)

    def soft_delete(self, *, persona_id: UUID) -> None:
        row = self._session.get(schema_models.Persona, persona_id)
        if row is None or row.deleted_at is not None:
            raise ValueError("Persona not found")
        timestamp = datetime.now(UTC)
        row.deleted_at = timestamp
        row.updated_at = timestamp
        self._session.flush()

    def _select(self, user_id: UUID) -> Select[schema_models.Persona]:
        return (
            select(schema_models.Persona)
            .join(models.Brand, models.Brand.id == schema_models.Persona.brand_id)
            .join(
                models.WorkspaceMembership,
                models.WorkspaceMembership.workspace_id == models.Brand.workspace_id,
            )
            .where(
                models.WorkspaceMembership.user_id == user_id,
                models.WorkspaceMembership.deleted_at.is_(None),
                schema_models.Persona.deleted_at.is_(None),
                models.Brand.deleted_at.is_(None),
            )
        )


class SqlAlchemyPlanningRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, *, created_by: UUID, **fields: object) -> PlanningRecord:
        persona = self._session.get(schema_models.Persona, fields["persona_id"])
        if persona is None or persona.deleted_at is not None:
            raise ValueError("Persona does not exist")
        campaign = self._session.get(schema_models.Campaign, fields["campaign_id"])
        if campaign is None or campaign.deleted_at is not None:
            raise ValueError("Campaign does not exist")
        if persona.brand_id != fields["brand_id"]:
            raise ValueError("Persona and planning brand do not match")
        brand = self._session.get(models.Brand, fields["brand_id"])
        if (
            brand is None
            or brand.deleted_at is not None
            or brand.workspace_id != campaign.workspace_id
        ):
            raise ValueError("Brand and campaign workspace do not match")
        fields = {"planning_info" if key == "info" else key: value for key, value in fields.items()}
        fields = {
            {
                "static_amount": "planning_static_amount",
                "carousel_amount": "planning_carousel_amount",
                "stories_amount": "planning_stories_amount",
                "special_dates": "planning_special_dates",
                "start_period": "planning_start_period",
                "end_period": "planning_end_period",
            }.get(key, key): value
            for key, value in fields.items()
        }
        fields.update(
            {
                "persona_name": persona.name,
                "persona_age": persona.age,
                "persona_gender": persona.gender,
                "persona_main_goal": persona.main_goal,
                "persona_challenge": persona.challenge,
                "persona_interest": persona.interest,
                "persona_routine": persona.routine,
                "persona_journey": persona.journey,
                "persona_trigger": persona.trigger,
            }
        )
        row = schema_models.Planning(created_by=created_by, **fields)
        self._session.add(row)
        self._session.flush()
        return _planning_record(row)

    def list_for_user(
        self,
        *,
        user_id: UUID,
        campaign_id: UUID | None = None,
        page: PageRequest | None = None,
    ) -> Page[PlanningRecord]:
        page = page or PageRequest()
        statement = self._select(user_id)
        count = (
            select(func.count())
            .select_from(schema_models.Planning)
            .join(
                schema_models.Campaign,
                schema_models.Campaign.id == schema_models.Planning.campaign_id,
            )
            .join(
                models.WorkspaceMembership,
                models.WorkspaceMembership.workspace_id == schema_models.Campaign.workspace_id,
            )
            .where(
                models.WorkspaceMembership.user_id == user_id,
                models.WorkspaceMembership.deleted_at.is_(None),
                schema_models.Planning.deleted_at.is_(None),
                schema_models.Campaign.deleted_at.is_(None),
            )
        )
        if campaign_id is not None:
            statement = statement.where(schema_models.Planning.campaign_id == campaign_id)
            count = count.where(schema_models.Planning.campaign_id == campaign_id)
        order = (
            asc(schema_models.Planning.created_at)
            if page.sort == "asc"
            else desc(schema_models.Planning.created_at)
        )
        rows = self._session.scalars(
            statement.order_by(order).offset(page.offset).limit(page.limit)
        ).all()
        return Page(
            items=[_planning_record(row) for row in rows],
            total=self._session.scalar(count) or 0,
            page=page.page,
            limit=page.limit,
        )

    def get_for_user(self, *, user_id: UUID, planning_id: UUID) -> PlanningRecord | None:
        row = self._session.scalars(
            self._select(user_id).where(schema_models.Planning.id == planning_id)
        ).one_or_none()
        return _planning_record(row) if row else None

    def update(self, *, planning_id: UUID, fields: dict[str, object]) -> PlanningRecord:
        row = self._session.get(schema_models.Planning, planning_id)
        if row is None or row.deleted_at is not None:
            raise ValueError("Planning not found")
        mapping = {
            "info": "planning_info",
            "static_amount": "planning_static_amount",
            "carousel_amount": "planning_carousel_amount",
            "stories_amount": "planning_stories_amount",
            "special_dates": "planning_special_dates",
            "start_period": "planning_start_period",
            "end_period": "planning_end_period",
        }
        for name, value in fields.items():
            setattr(row, mapping.get(name, name), value)
        row.updated_at = datetime.now(UTC)
        self._session.flush()
        return _planning_record(row)

    def soft_delete(self, *, planning_id: UUID) -> None:
        row = self._session.get(schema_models.Planning, planning_id)
        if row is None or row.deleted_at is not None:
            raise ValueError("Planning not found")
        timestamp = datetime.now(UTC)
        row.deleted_at = timestamp
        row.updated_at = timestamp
        self._session.flush()

    def _select(self, user_id: UUID) -> Select[schema_models.Planning]:
        return (
            select(schema_models.Planning)
            .join(
                schema_models.Campaign,
                schema_models.Campaign.id == schema_models.Planning.campaign_id,
            )
            .join(
                models.WorkspaceMembership,
                models.WorkspaceMembership.workspace_id == schema_models.Campaign.workspace_id,
            )
            .where(
                models.WorkspaceMembership.user_id == user_id,
                models.WorkspaceMembership.deleted_at.is_(None),
                schema_models.Planning.deleted_at.is_(None),
                schema_models.Campaign.deleted_at.is_(None),
            )
        )


class SqlAlchemyCampaignRepository(_CampaignRepositoryBase):
    def get_for_user(self, *, user_id: UUID, campaign_id: UUID) -> CampaignRecord | None:
        row = self._session.scalars(
            self._select(user_id).where(schema_models.Campaign.id == campaign_id)
        ).one_or_none()
        return _record(row) if row else None

    def list_for_user(
        self,
        *,
        user_id: UUID,
        workspace_id: UUID | None = None,
        page: PageRequest | None = None,
    ) -> Page[CampaignRecord]:
        page = page or PageRequest()
        statement = self._select(user_id)
        count = (
            select(func.count())
            .select_from(schema_models.Campaign)
            .join(
                models.WorkspaceMembership,
                models.WorkspaceMembership.workspace_id == schema_models.Campaign.workspace_id,
            )
            .where(
                models.WorkspaceMembership.user_id == user_id,
                models.WorkspaceMembership.deleted_at.is_(None),
                schema_models.Campaign.deleted_at.is_(None),
            )
        )
        if workspace_id is not None:
            statement = statement.where(schema_models.Campaign.workspace_id == workspace_id)
            count = count.where(schema_models.Campaign.workspace_id == workspace_id)
        order = (
            asc(schema_models.Campaign.created_at)
            if page.sort == "asc"
            else desc(schema_models.Campaign.created_at)
        )
        rows = self._session.scalars(
            statement.order_by(order).offset(page.offset).limit(page.limit)
        ).all()
        return Page(
            items=[_record(row) for row in rows],
            total=self._session.scalar(count) or 0,
            page=page.page,
            limit=page.limit,
        )

    def _select(self, user_id: UUID) -> Select[schema_models.Campaign]:
        return (
            select(schema_models.Campaign)
            .join(
                models.WorkspaceMembership,
                models.WorkspaceMembership.workspace_id == schema_models.Campaign.workspace_id,
            )
            .where(
                models.WorkspaceMembership.user_id == user_id,
                models.WorkspaceMembership.deleted_at.is_(None),
                schema_models.Campaign.deleted_at.is_(None),
            )
        )


def _post_record(row: schema_models.PostStructure) -> PostStructureRecord:
    return PostStructureRecord(
        id=row.id,
        workspace_id=row.workspace_id,
        planning_id=row.planning_id,
        created_by=row.created_by,
        title=row.post_title,
        objective=row.post_objective,
        big_idea=row.post_big_idea,
        main_message=row.post_main_message,
        headline=row.post_headline,
        image_cta=row.image_cta,
        art_guiding=row.art_guiding,
        status=row.post_status,
        format=row.content_format,
        ratio=row.art_ratio,
        resolution=row.art_resolution,
        created_at=row.created_at,
        updated_at=row.updated_at,
        deleted_at=row.deleted_at,
    )


class SqlAlchemyPostStructureRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(
        self, *, workspace_id: UUID, planning_id: UUID, created_by: UUID, **fields: str | None
    ) -> PostStructureRecord:
        planning = self._session.get(schema_models.Planning, planning_id)
        if planning is None or planning.deleted_at is not None:
            raise ValueError("Planning does not exist")
        campaign = self._session.get(schema_models.Campaign, planning.campaign_id)
        if campaign is None or campaign.workspace_id != workspace_id:
            raise ValueError("Planning and post structure workspace do not match")
        field_names = {
            "title": "post_title",
            "objective": "post_objective",
            "big_idea": "post_big_idea",
            "main_message": "post_main_message",
            "headline": "post_headline",
            "status": "post_status",
            "format": "content_format",
            "ratio": "art_ratio",
            "resolution": "art_resolution",
        }
        fields = {field_names.get(key, key): value for key, value in fields.items()}
        row = schema_models.PostStructure(
            workspace_id=workspace_id, planning_id=planning_id, created_by=created_by, **fields
        )
        self._session.add(row)
        self._session.flush()
        return _post_record(row)

    def get_for_user(self, *, user_id: UUID, post_structure_id: UUID) -> PostStructureRecord | None:
        row = self._session.scalars(
            self._select(user_id).where(schema_models.PostStructure.id == post_structure_id)
        ).one_or_none()
        return _post_record(row) if row else None

    def update(
        self, *, post_structure_id: UUID, fields: dict[str, str | None]
    ) -> PostStructureRecord | None:
        row = self._session.get(schema_models.PostStructure, post_structure_id)
        if row is None or row.deleted_at is not None:
            return None
        for field, value in fields.items():
            setattr(
                row,
                {
                    "title": "post_title",
                    "objective": "post_objective",
                    "big_idea": "post_big_idea",
                    "main_message": "post_main_message",
                    "headline": "post_headline",
                    "status": "post_status",
                    "format": "content_format",
                    "ratio": "art_ratio",
                    "resolution": "art_resolution",
                }.get(field, field),
                value,
            )
        self._session.flush()
        return _post_record(row)

    def soft_delete(self, *, post_structure_id: UUID) -> bool:
        row = self._session.get(schema_models.PostStructure, post_structure_id)
        if row is None or row.deleted_at is not None:
            return False
        row.deleted_at = datetime.now(UTC)
        self._session.flush()
        return True

    def list_for_user(
        self,
        *,
        user_id: UUID,
        workspace_id: UUID | None = None,
        planning_id: UUID | None = None,
        page: PageRequest | None = None,
    ) -> Page[PostStructureRecord]:
        page = page or PageRequest()
        statement = self._select(user_id)
        count = (
            select(func.count())
            .select_from(schema_models.PostStructure)
            .join(
                models.WorkspaceMembership,
                models.WorkspaceMembership.workspace_id == schema_models.PostStructure.workspace_id,
            )
            .where(
                models.WorkspaceMembership.user_id == user_id,
                models.WorkspaceMembership.deleted_at.is_(None),
                schema_models.PostStructure.deleted_at.is_(None),
            )
        )
        if workspace_id is not None:
            statement = statement.where(schema_models.PostStructure.workspace_id == workspace_id)
            count = count.where(schema_models.PostStructure.workspace_id == workspace_id)
        if planning_id is not None:
            statement = statement.where(schema_models.PostStructure.planning_id == planning_id)
            count = count.where(schema_models.PostStructure.planning_id == planning_id)
        order = (
            asc(schema_models.PostStructure.created_at)
            if page.sort == "asc"
            else desc(schema_models.PostStructure.created_at)
        )
        rows = self._session.scalars(
            statement.order_by(order).offset(page.offset).limit(page.limit)
        ).all()
        return Page(
            items=[_post_record(row) for row in rows],
            total=self._session.scalar(count) or 0,
            page=page.page,
            limit=page.limit,
        )

    def _select(self, user_id: UUID) -> Select[schema_models.PostStructure]:
        return (
            select(schema_models.PostStructure)
            .join(
                models.WorkspaceMembership,
                models.WorkspaceMembership.workspace_id == schema_models.PostStructure.workspace_id,
            )
            .where(
                models.WorkspaceMembership.user_id == user_id,
                models.WorkspaceMembership.deleted_at.is_(None),
                schema_models.PostStructure.deleted_at.is_(None),
            )
        )


def _brand_asset_record(row: schema_models.BrandAsset) -> BrandAssetRecord:
    return BrandAssetRecord(
        id=row.id,
        brand_id=row.brand_id,
        type=row.type,
        file_url=row.file_url,
        file_name=row.file_name,
        description=row.description,
        created_at=row.created_at,
        updated_at=row.updated_at,
        deleted_at=row.deleted_at,
    )


class SqlAlchemyBrandAssetRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(
        self,
        *,
        brand_id: UUID,
        type: str,
        file_url: str,
        file_name: str | None = None,
        description: str | None = None,
    ) -> BrandAssetRecord:
        row = schema_models.BrandAsset(
            brand_id=brand_id,
            type=type,
            file_url=file_url,
            file_name=file_name,
            description=description,
        )
        self._session.add(row)
        self._session.flush()
        return _brand_asset_record(row)

    def get_for_user(self, *, user_id: UUID, asset_id: UUID) -> BrandAssetRecord | None:
        row = self._session.scalars(
            self._select(user_id).where(schema_models.BrandAsset.id == asset_id)
        ).one_or_none()
        return _brand_asset_record(row) if row else None

    def list_for_user(
        self,
        *,
        user_id: UUID,
        brand_id: UUID | None = None,
        page: PageRequest | None = None,
    ) -> Page[BrandAssetRecord]:
        page = page or PageRequest()
        statement = self._select(user_id)
        count = (
            select(func.count())
            .select_from(schema_models.BrandAsset)
            .join(models.Brand, models.Brand.id == schema_models.BrandAsset.brand_id)
            .join(
                models.WorkspaceMembership,
                models.WorkspaceMembership.workspace_id == models.Brand.workspace_id,
            )
            .where(
                models.WorkspaceMembership.user_id == user_id,
                models.WorkspaceMembership.deleted_at.is_(None),
                schema_models.BrandAsset.deleted_at.is_(None),
                models.Brand.deleted_at.is_(None),
            )
        )
        if brand_id is not None:
            statement = statement.where(schema_models.BrandAsset.brand_id == brand_id)
            count = count.where(schema_models.BrandAsset.brand_id == brand_id)
        order = (
            asc(schema_models.BrandAsset.created_at)
            if page.sort == "asc"
            else desc(schema_models.BrandAsset.created_at)
        )
        rows = self._session.scalars(
            statement.order_by(order).offset(page.offset).limit(page.limit)
        ).all()
        return Page(
            items=[_brand_asset_record(row) for row in rows],
            total=self._session.scalar(count) or 0,
            page=page.page,
            limit=page.limit,
        )

    def update(self, *, asset_id: UUID, fields: dict[str, object]) -> BrandAssetRecord:
        row = self._session.get(schema_models.BrandAsset, asset_id)
        if row is None or row.deleted_at is not None:
            raise ValueError("Brand asset not found")
        for name, value in fields.items():
            setattr(row, name, value)
        row.updated_at = datetime.now(UTC)
        self._session.flush()
        return _brand_asset_record(row)

    def soft_delete(self, *, asset_id: UUID) -> None:
        row = self._session.get(schema_models.BrandAsset, asset_id)
        if row is None or row.deleted_at is not None:
            raise ValueError("Brand asset not found")
        timestamp = datetime.now(UTC)
        row.deleted_at = timestamp
        row.updated_at = timestamp
        self._session.flush()

    def _select(self, user_id: UUID) -> Select[schema_models.BrandAsset]:
        return (
            select(schema_models.BrandAsset)
            .join(models.Brand, models.Brand.id == schema_models.BrandAsset.brand_id)
            .join(
                models.WorkspaceMembership,
                models.WorkspaceMembership.workspace_id == models.Brand.workspace_id,
            )
            .where(
                models.WorkspaceMembership.user_id == user_id,
                models.WorkspaceMembership.deleted_at.is_(None),
                schema_models.BrandAsset.deleted_at.is_(None),
                models.Brand.deleted_at.is_(None),
            )
        )
