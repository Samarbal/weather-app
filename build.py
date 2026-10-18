"""Build the React frontend for the Vercel deployment."""

import subprocess
from pathlib import Path


def main() -> None:
    frontend = Path(__file__).resolve().parent / "frontend"

    subprocess.run(["npm", "ci"], cwd=frontend, check=True)
    subprocess.run(["npm", "run", "build"], cwd=frontend, check=True)


if __name__ == "__main__":
    main()
