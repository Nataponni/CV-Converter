# pip install pytest
# pytest tests/
# pip install pytest-cov
# pytest --cov=your_module_name tests/

from postprocess import unify_durations
from postprocess import unify_languages, remap_hard_skills, validate_cv_schema                  
from postprocess import normalize_year

def test_normalize_year():
    assert normalize_year("21") == "2021"
    assert normalize_year("98") == "1998"
    assert normalize_year("2023") == "2023"
    assert normalize_year("abc") == "abc"

def test_unify_durations_basic():
    projects = [{"duration": "07.21 - 12.23"}]
    result = unify_durations(projects)
    assert result[0]["duration"] == "Jul 2021 – Dec 2023"


def test_unify_languages_with_levels():
    langs = [{"language": "German", "level": "C2"}, {"language": "English", "level": ""}]
    result = unify_languages(langs)
    assert result == [{"language": "German", "level": "C2"}, {"language": "English", "level": "Unspecified"}]


def test_validate_cv_schema_missing_fields():
    cv = {"education": "", "projects_experience": [], "languages": []}
    missing = validate_cv_schema(cv)
    assert "profile_summary" in missing
    assert "hard_skills" in missing


def test_remap_hard_skills_cloud_collapse():
    input_skills = {"cloud_platforms": ["Azure", "AWS", "GCP"]}
    result = remap_hard_skills(input_skills)
    collapsed = [t["name"] for t in result.get("cloud_platforms", [])]
    assert any("Azure" in c or "AWS" in c or "Google" in c for c in collapsed)


def test_remap_hard_skills_cloud_collapse():
    input_skills = {"cloud_platforms": ["Azure", "AWS", "GCP"]}
    result = remap_hard_skills(input_skills)
    assert result["cloud_platforms"] == [{"name": "Microsoft Azure"}] or [{"name": "AWS"}] or [{"name": "Google Cloud"}]

def test_validate_cv_schema_missing_fields():
    cv = {"education": "", "projects_experience": [], "languages": []}
    missing = validate_cv_schema(cv)
    assert "profile_summary" in missing
    assert "hard_skills" in missing
