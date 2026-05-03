from pathlib import Path

from novel_analyzer.config.settings import Settings
from novel_analyzer.skills.loader import list_skill_names


def test_project_skills_dir_is_discovered() -> None:
    settings = Settings(skills_dir=str(Path('skills_dir')))
    names = list_skill_names(settings)
    assert 'chapter-fact-extractor' in names
    assert 'json-to-markdown' in names
    assert 'imitation-constraint-pack' in names
    assert 'draft-self-check' in names
    assert 'rhythm-analyzer' in names
    assert 'reader-sim-review' in names
    assert 'dialogue-designer' in names
    assert 'research-pack' in names
