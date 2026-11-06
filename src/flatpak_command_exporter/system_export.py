from .api import FlatpakCommandExporter


def main() -> None:
    FlatpakCommandExporter(scope="system").export_commands()


if __name__ == "__main__":
    main()
