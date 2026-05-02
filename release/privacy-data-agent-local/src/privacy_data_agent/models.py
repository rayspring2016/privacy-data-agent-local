from __future__ import annotations

from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field


class EntityType(StrEnum):
    EMPLOYEE = "employee"
    ID_NUMBER = "id_number"
    DEPARTMENT = "department"
    CUSTOMER = "customer"
    PHONE = "phone"
    EMAIL = "email"


TOKEN_PREFIX: dict[EntityType, str] = {
    EntityType.EMPLOYEE: "EMP",
    EntityType.ID_NUMBER: "ID",
    EntityType.DEPARTMENT: "DEPT",
    EntityType.CUSTOMER: "CUSTOMER",
    EntityType.PHONE: "PHONE",
    EntityType.EMAIL: "EMAIL",
}


class MappingEntry(BaseModel):
    entity_type: EntityType
    original: str
    token: str


class MappingFile(BaseModel):
    version: int = 1
    entries: list[MappingEntry] = Field(default_factory=list)


class RunArtifacts(BaseModel):
    run_id: str
    output_dir: Path
    anonymized_data_path: Path
    mapping_path: Path
    anonymized_report_path: Path
    restored_report_path: Path
    manifest_path: Path


class AnalysisResult(BaseModel):
    anonymized_report: str
