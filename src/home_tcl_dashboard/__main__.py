import uvicorn


def main() -> None:
    """Start the dashboard server."""
    uvicorn.run("home_tcl_dashboard.app:app", host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
