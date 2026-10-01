import json

from .database import SessionLocal
from .experiment import build_report


def main() -> None:
    with SessionLocal() as db:
        print(json.dumps(build_report(db), indent=2))


if __name__ == "__main__":
    main()
