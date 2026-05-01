"""python -m themey entrypoint."""
if __name__ == "__main__":
    from themey.cli import app  # type: ignore[import-not-found]  # cli created in Plan 09

    app()
