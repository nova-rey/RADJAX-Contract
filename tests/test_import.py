def test_package_imports() -> None:
    import radjax_contract

    assert (
        radjax_contract.CONTRACT_VERSION
        if hasattr(radjax_contract, "CONTRACT_VERSION")
        else True
    )
