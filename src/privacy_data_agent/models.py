from __future__ import annotations

from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field


class EntityType(StrEnum):
    EMPLOYEE = "employee"
    ID_NUMBER = "id_number"
    EMPLOYEE_ID = "employee_id"
    DEPARTMENT = "department"
    CUSTOMER = "customer"
    PHONE = "phone"
    EMAIL = "email"
    LICENSE_PLATE = "license_plate"


ANON_TOKEN_PREFIX = "PDA"


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
