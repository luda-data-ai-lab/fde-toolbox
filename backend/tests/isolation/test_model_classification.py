from app.db.base import AssetMixin, Base, TenantScopedMixin

GLOBAL_TABLES = {"tenants", "users", "user_tenant_assignments", "audit_logs"}


def test_every_table_is_classified() -> None:
    unclassified = []
    for mapper in Base.registry.mappers:
        cls = mapper.class_
        name = mapper.local_table.name
        kinds = [issubclass(cls, TenantScopedMixin), issubclass(cls, AssetMixin), name in GLOBAL_TABLES]
        if sum(kinds) != 1:
            unclassified.append(name)
    assert unclassified == []


def test_tenant_tables_have_indexed_non_null_fk() -> None:
    for mapper in Base.registry.mappers:
        if issubclass(mapper.class_, TenantScopedMixin):
            col = mapper.local_table.c.tenant_id
            assert not col.nullable and col.index
            assert any(fk.column.table.name == "tenants" for fk in col.foreign_keys)


def test_asset_tables_have_no_tenant_column() -> None:
    for mapper in Base.registry.mappers:
        if issubclass(mapper.class_, AssetMixin):
            assert "tenant_id" not in mapper.local_table.c
            assert {"asset_id", "version"} <= set(mapper.local_table.c.keys())
