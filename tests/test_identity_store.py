import pytest

from privacy_data_agent import identity_store
from privacy_data_agent.identity_store import UnifiedIdentityStore
from privacy_data_agent.models import EntityType, MappingEntry, MappingFile


def entry(original="张三", token="PDA_1111111111111111", kind=EntityType.EMPLOYEE):
    return MappingEntry(entity_type=kind, original=original, token=token)


def test_persists_across_sessions_and_appends_entities(tmp_path, monkeypatch):
    path = tmp_path / "private/mapping.local.json"
    monkeypatch.setattr(identity_store, "identity_mapping_path", lambda: path)
    first = MappingFile(entries=[entry()])
    with UnifiedIdentityStore() as store:
        assert store.mapping.entries == []
        store.save(first)
    with UnifiedIdentityStore() as store:
        assert store.mapping == first
        store.save(MappingFile(entries=[entry("李四", "PDA_2222222222222222")]))
    with UnifiedIdentityStore() as store:
        assert [e.original for e in store.mapping.entries] == ["张三", "李四"]
    assert path.stat().st_mode & 0o777 == 0o600
    assert not path.with_suffix(".lock").exists()


def test_conflicting_old_mapping_is_rejected_without_changing_store(tmp_path, monkeypatch):
    path = tmp_path / "mapping.local.json"
    monkeypatch.setattr(identity_store, "identity_mapping_path", lambda: path)
    with UnifiedIdentityStore() as store:
        store.save(MappingFile(entries=[entry()]))
    original = path.read_bytes()
    with pytest.raises(ValueError, match="冲突"):
        with UnifiedIdentityStore(MappingFile(entries=[entry(token="PDA_9999999999999999")])):
            pass
    assert path.read_bytes() == original
    assert not path.with_suffix(".lock").exists()


def test_different_entities_cannot_share_one_token(tmp_path, monkeypatch):
    path = tmp_path / "mapping.local.json"
    monkeypatch.setattr(identity_store, "identity_mapping_path", lambda: path)
    with pytest.raises(ValueError, match="冲突"):
        with UnifiedIdentityStore(MappingFile(entries=[entry(), entry("李四")])):
            pass
    assert not path.exists()


def test_same_text_in_different_entity_types_is_kept_separate(tmp_path, monkeypatch):
    path = tmp_path / "mapping.local.json"
    monkeypatch.setattr(identity_store, "identity_mapping_path", lambda: path)
    mapping = MappingFile(entries=[entry("销售部"), entry("销售部", "PDA_2222222222222222", EntityType.DEPARTMENT)])
    with UnifiedIdentityStore(mapping) as store:
        store.save(store.mapping)
    with UnifiedIdentityStore() as store:
        assert len(store.mapping.entries) == 2


def test_corrupt_store_is_not_silently_reset(tmp_path, monkeypatch):
    path = tmp_path / "mapping.local.json"
    path.write_text("private invalid content", encoding="utf-8")
    monkeypatch.setattr(identity_store, "identity_mapping_path", lambda: path)
    with pytest.raises(ValueError, match="无法读取") as exc:
        with UnifiedIdentityStore():
            pass
    assert "private invalid content" not in str(exc.value)
    assert path.read_text() == "private invalid content"
    assert not path.with_suffix(".lock").exists()


def test_concurrent_sessions_are_rejected_and_lock_is_released(tmp_path, monkeypatch):
    path = tmp_path / "mapping.local.json"
    monkeypatch.setattr(identity_store, "identity_mapping_path", lambda: path)
    with UnifiedIdentityStore():
        with pytest.raises(ValueError, match="正在使用"):
            with UnifiedIdentityStore():
                pass
    with UnifiedIdentityStore():
        pass


def test_save_failure_preserves_previous_file(tmp_path, monkeypatch):
    path = tmp_path / "mapping.local.json"
    monkeypatch.setattr(identity_store, "identity_mapping_path", lambda: path)
    with UnifiedIdentityStore() as store:
        store.save(MappingFile(entries=[entry()]))
    original = path.read_bytes()

    def fail_replace(*args):
        raise OSError("simulated disk failure")

    monkeypatch.setattr(identity_store.os, "replace", fail_replace)
    with pytest.raises(OSError):
        with UnifiedIdentityStore() as store:
            store.save(MappingFile(entries=[entry("李四", "PDA_2222222222222222")]))
    assert path.read_bytes() == original
    assert sorted(p.name for p in tmp_path.iterdir()) == ["mapping.local.json"]
