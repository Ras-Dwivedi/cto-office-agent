import yaml
from pathlib import Path

# Resolve config/projects.yaml relative to repo root
PROJECTS_FILE = Path(__file__).resolve().parents[2] / "src" / "config" / "projects.yaml"
print(PROJECTS_FILE)


def load_projects():
    """
    Load the authoritative project registry.

    Returns:
        dict: { project_id: {name, description, owners, tags, status} }
    """
    if not PROJECTS_FILE.exists():
        raise FileNotFoundError(f"Project registry not found: {PROJECTS_FILE}")

    with open(PROJECTS_FILE, "r") as f:
        data = yaml.safe_load(f)

    projects = data.get("projects", {})
    if not isinstance(projects, dict):
        raise ValueError("Invalid projects.yaml format")

    return projects
