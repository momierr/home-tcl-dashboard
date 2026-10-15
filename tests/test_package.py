import home_tcl_dashboard


def test_package_is_importable_from_src() -> None:
    assert home_tcl_dashboard.__file__ is not None
    assert home_tcl_dashboard.__file__.endswith("src/home_tcl_dashboard/__init__.py")
