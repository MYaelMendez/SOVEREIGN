from ae import registry as r


def test_registry_loads_and_validates():
    data = r.load()
    assert data["version"]
    # NOT a magic number. A hardcoded total meant every legitimate addition
    # broke the suite — and a test that fails on correct input teaches you to
    # update the number instead of reading the failure. Assert the invariants
    # the contract actually promises instead.
    assert len(data["resources"]) > 0
    assert r.validate(data) is None


def test_scopes_are_valid_and_ids_unique():
    rs = r.resources()
    assert all(x.scope in r.SCOPES for x in rs)
    ids = [x.id for x in rs]
    assert len(ids) == len(set(ids))


def test_public_only_resolves_to_https():
    for x in r.resources():
        if x.scope == "public":
            assert x.route.startswith("https://")


def test_local_resolves_to_ae_scheme():
    for x in r.resources():
        if x.scope == "local":
            assert x.route.startswith("ae://local/")


def test_by_category_and_resolve():
    scenes = r.by_category("threejs_scenes")
    assert len(scenes) == 8
    one = scenes[0]
    assert r.resolve(one.id) is not None
    assert r.resolve("does-not-exist") is None


def test_counts_total_matches():
    """counts() must account for every resource — self-consistent, not a
    hardcoded total. This catches a real defect (a resource no category claims)
    and never breaks on a legitimate addition."""
    assert sum(r.counts().values()) == len(r.resources())


def test_every_resource_declares_verified_and_evidence():
    """`verified` must be an honest boolean and `evidence` must be present.
    An entry that implies a pass it did not have is the defect this registry
    exists to prevent — so a `verified: true` with no evidence must fail."""
    for x in r.resources():
        d = x.to_dict() if hasattr(x, "to_dict") else vars(x)
        assert isinstance(d.get("verified"), bool), f"{x.id}: verified not a bool"
        assert "evidence" in d, f"{x.id}: no evidence field"
        if d.get("verified"):
            assert d.get("evidence"), f"{x.id}: verified without evidence"
