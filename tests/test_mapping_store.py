from cryptography.fernet import Fernet

from privacy_data_agent.mapping_store import (
    load_mapping_file,
    load_mapping_table,
    save_mapping_file,
    save_mapping_table,
)
from privacy_data_agent.models import EntityType, MappingEntry, MappingFile


def test_mapping_store_encrypts_raw_values(tmp_path):
    key = Fernet.generate_key().decode()
    mapping = MappingFile(
        entries=[
            MappingEntry(entity_type=EntityType.EMPLOYEE, original="张三", token="EMP_0001"),
            MappingEntry(entity_type=EntityType.CUSTOMER, original="上海春雷科技有限公司", token="CUSTOMER_0001"),
        ]
    )
    path = tmp_path / "mapping.enc.json"

    save_mapping_file(mapping, path, key)

    encrypted_text = path.read_text(encoding="utf-8")
    assert "张三" not in encrypted_text
    assert "上海春雷科技有限公司" not in encrypted_text
    assert load_mapping_file(path, key) == mapping


def test_mapping_table_round_trips_for_local_restore(tmp_path):
    mapping = MappingFile(
        entries=[
            MappingEntry(entity_type=EntityType.EMPLOYEE, original="张三", token="EMP_0001"),
            MappingEntry(entity_type=EntityType.DEPARTMENT, original="华东销售一部", token="DEPT_0001"),
        ]
    )
    path = tmp_path / "mapping_table.csv"

    save_mapping_table(mapping, path)

    assert load_mapping_table(path) == mapping
