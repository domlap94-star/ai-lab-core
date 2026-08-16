from __future__ import annotations

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from app.models.candidate_source import CandidateSource
from app.models.client import Client
from app.models.client_candidate import ClientCandidate
from app.models.client_contact_point import ClientContactPoint
from app.models.import_run import ImportRun
from app.models.import_source import ImportSource


class ImportRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_import_source(
        self,
        source_id: int,
    ) -> ImportSource | None:
        return (
            self.db.query(ImportSource)
            .filter(
                ImportSource.id == source_id,
                ImportSource.deleted_at.is_(None),
            )
            .first()
        )

    def get_import_run(
        self,
        run_id: int,
    ) -> ImportRun | None:
        return (
            self.db.query(ImportRun)
            .filter(
                ImportRun.id == run_id,
                ImportRun.deleted_at.is_(None),
            )
            .first()
        )

    def find_candidate_source(
        self,
        *,
        import_source_id: int,
        source_type: str,
        external_id: str,
    ) -> CandidateSource | None:
        return (
            self.db.query(CandidateSource)
            .filter(
                CandidateSource.import_source_id == import_source_id,
                CandidateSource.source_type == source_type,
                CandidateSource.external_id == external_id,
                CandidateSource.deleted_at.is_(None),
            )
            .first()
        )

    def get_candidate(
        self,
        candidate_id: int,
    ) -> ClientCandidate | None:
        return (
            self.db.query(ClientCandidate)
            .filter(
                ClientCandidate.id == candidate_id,
                ClientCandidate.deleted_at.is_(None),
            )
            .first()
        )

    def find_client_by_tax_id(
        self,
        tax_id: str,
    ) -> Client | None:
        normalized_tax_id = self._normalize_identifier(tax_id)

        if not normalized_tax_id:
            return None

        return (
            self.db.query(Client)
            .filter(
                Client.deleted_at.is_(None),
                func.regexp_replace(
                    func.lower(Client.tax_id),
                    r"[^a-z0-9]",
                    "",
                    "g",
                )
                == normalized_tax_id,
            )
            .first()
        )

    def find_client_by_email(
        self,
        email: str,
    ) -> Client | None:
        normalized_email = self._normalize_email(email)

        if not normalized_email:
            return None

        return (
            self.db.query(Client)
            .filter(
                Client.deleted_at.is_(None),
                or_(
                    func.lower(func.trim(Client.primary_email))
                    == normalized_email,
                    Client.contact_points.any(
                        and_(
                            ClientContactPoint.deleted_at.is_(None),
                            ClientContactPoint.kind == "email",
                            ClientContactPoint.normalized_value == normalized_email,
                        )
                    ),
                ),
            )
            .first()
        )

    def find_candidate_by_tax_id(
        self,
        tax_id: str,
    ) -> ClientCandidate | None:
        normalized_tax_id = self._normalize_identifier(tax_id)

        if not normalized_tax_id:
            return None

        return (
            self.db.query(ClientCandidate)
            .filter(
                ClientCandidate.deleted_at.is_(None),
                ClientCandidate.status.in_(
                    (
                        "pending",
                        "duplicate",
                    )
                ),
                func.regexp_replace(
                    func.lower(ClientCandidate.tax_id),
                    r"[^a-z0-9]",
                    "",
                    "g",
                )
                == normalized_tax_id,
            )
            .order_by(ClientCandidate.created_at.asc())
            .first()
        )

    def find_candidate_by_email(
        self,
        email: str,
    ) -> ClientCandidate | None:
        normalized_email = self._normalize_email(email)

        if not normalized_email:
            return None

        return (
            self.db.query(ClientCandidate)
            .filter(
                ClientCandidate.deleted_at.is_(None),
                ClientCandidate.status.in_(
                    (
                        "pending",
                        "duplicate",
                    )
                ),
                func.lower(
                    func.trim(ClientCandidate.primary_email)
                )
                == normalized_email,
            )
            .order_by(ClientCandidate.created_at.asc())
            .first()
        )

    def create_candidate(
        self,
        candidate: ClientCandidate,
    ) -> ClientCandidate:
        self.db.add(candidate)
        self.db.flush()

        return candidate

    def find_candidate_by_phone(self, phone: str) -> ClientCandidate | None:
        normalized_phone = self._normalize_phone(phone)
        if not normalized_phone:
            return None
        return (
            self.db.query(ClientCandidate)
            .filter(
                ClientCandidate.deleted_at.is_(None),
                ClientCandidate.status.in_(("pending", "duplicate")),
                func.regexp_replace(
                    ClientCandidate.primary_phone, r"[^0-9]", "", "g"
                ).in_((normalized_phone, f"48{normalized_phone}")),
            )
            .order_by(ClientCandidate.created_at.asc())
            .first()
        )

    def create_candidate_source(
        self,
        source: CandidateSource,
    ) -> CandidateSource:
        self.db.add(source)
        self.db.flush()

        return source

    def update_candidate(
        self,
        candidate: ClientCandidate,
    ) -> ClientCandidate:
        self.db.add(candidate)
        self.db.flush()

        return candidate

    def update_candidate_source(
        self,
        source: CandidateSource,
    ) -> CandidateSource:
        self.db.add(source)
        self.db.flush()

        return source

    def increment_import_run_counters(
        self,
        import_run: ImportRun,
        *,
        received: int = 0,
        processed: int = 0,
        candidates_created: int = 0,
        duplicates_detected: int = 0,
        failed: int = 0,
    ) -> ImportRun:
        import_run.records_received += received
        import_run.records_processed += processed
        import_run.candidates_created += candidates_created
        import_run.duplicates_detected += duplicates_detected
        import_run.records_failed += failed

        self.db.add(import_run)
        self.db.flush()

        return import_run

    def commit(self) -> None:
        self.db.commit()

    def rollback(self) -> None:
        self.db.rollback()

    @staticmethod
    def _normalize_email(value: str | None) -> str:
        if value is None:
            return ""

        return value.strip().lower()

    @staticmethod
    def _normalize_phone(value: str | None) -> str:
        if value is None:
            return ""
        digits = "".join(character for character in value if character.isdigit())
        if len(digits) == 11 and digits.startswith("48"):
            digits = digits[2:]
        return digits if len(digits) == 9 else ""

    @staticmethod
    def _normalize_identifier(value: str | None) -> str:
        if value is None:
            return ""

        return "".join(
            character.lower()
            for character in value.strip()
            if character.isalnum()
        )

    def find_client_by_phone(self, phone: str) -> Client | None:
        normalized_phone = self._normalize_phone(phone)
        if not normalized_phone:
            return None
        return (
            self.db.query(Client)
            .filter(
                Client.deleted_at.is_(None),
                or_(
                    func.regexp_replace(
                        Client.primary_phone, r"[^0-9]", "", "g"
                    ).in_((normalized_phone, f"48{normalized_phone}")),
                    Client.contact_points.any(
                        and_(
                            ClientContactPoint.deleted_at.is_(None),
                            ClientContactPoint.kind == "phone",
                            ClientContactPoint.normalized_value.in_(
                                (normalized_phone, f"48{normalized_phone}")
                            ),
                        )
                    ),
                ),
            )
            .first()
        )
