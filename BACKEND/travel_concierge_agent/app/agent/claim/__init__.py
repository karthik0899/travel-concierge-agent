from pathlib import Path

from app.agent._skill import load_skill

SKILL = load_skill(Path(__file__).parent)
