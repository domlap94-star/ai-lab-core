from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.document_asset import DocumentAsset


class DocumentAssetRepository:
    def __init__(
        self,
        db: Session,
    ) -> None:
        self.db = db

    def get(
        self,
        asset_id: int,
    ) -> DocumentAsset | None:
        return (
            self.db.query(DocumentAsset)
            .filter(
                DocumentAsset.id == asset_id,
            )
            .first()
        )

    def get_by_document_and_index(
        self,
        *,
        document_id: int,
        asset_index: int,
    ) -> DocumentAsset | None:
        return (
            self.db.query(DocumentAsset)
            .filter(
                DocumentAsset.document_id
                == document_id,
                DocumentAsset.asset_index
                == asset_index,
            )
            .first()
        )

    def get_by_document_and_checksum(
        self,
        *,
        document_id: int,
        checksum_sha256: str,
    ) -> DocumentAsset | None:
        return (
            self.db.query(DocumentAsset)
            .filter(
                DocumentAsset.document_id
                == document_id,
                DocumentAsset.checksum_sha256
                == checksum_sha256,
            )
            .first()
        )

    def get_for_document(
        self,
        document_id: int,
    ) -> list[DocumentAsset]:
        return (
            self.db.query(DocumentAsset)
            .filter(
                DocumentAsset.document_id
                == document_id,
            )
            .order_by(
                DocumentAsset.asset_index.asc(),
            )
            .all()
        )

    def create(
        self,
        asset: DocumentAsset,
    ) -> DocumentAsset:
        self.db.add(asset)
        self.db.flush()
        self.db.refresh(asset)

        return asset

    def update(
        self,
        asset: DocumentAsset,
    ) -> DocumentAsset:
        self.db.add(asset)
        self.db.flush()
        self.db.refresh(asset)

        return asset

    def delete_for_document(
        self,
        document_id: int,
    ) -> int:
        return (
            self.db.query(DocumentAsset)
            .filter(
                DocumentAsset.document_id
                == document_id,
            )
            .delete(
                synchronize_session=False,
            )
        )

    def commit(
        self,
    ) -> None:
        self.db.commit()

    def rollback(
        self,
    ) -> None:
        self.db.rollback()