"""python -m themey entrypoint."""
if __name__ == "__main__":
    from themey.cli import app  # imported lazily so missing module doesn't break tests

    app()
