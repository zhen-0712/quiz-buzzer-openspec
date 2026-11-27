"""Local entry point for the classroom quiz buzzer."""

from quiz_buzzer.cli import create_parser
from quiz_buzzer import create_app


def main() -> None:
    args = create_parser().parse_args()
    app = create_app()
    app.run(host=args.host, port=args.port, debug=False)


if __name__ == "__main__":
    main()
