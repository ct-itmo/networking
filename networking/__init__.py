from pathlib import Path

from networking.core.router import get_mount


static_path = Path(__file__).parent / "static"
template_path = Path(__file__).parent / "templates"
main_route = "networking:main"
mount = get_mount()

__all__ = ["main_route", "mount", "static_path", "template_path"]
