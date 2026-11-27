from quiz_buzzer.cli import create_parser


def test_server_host_defaults_to_all_interfaces():
    args = create_parser().parse_args([])
    assert args.host == "0.0.0.0"


def test_server_host_can_be_overridden():
    args = create_parser().parse_args(["--host", "192.168.1.20", "--port", "5050"])
    assert args.host == "192.168.1.20"
    assert args.port == 5050
