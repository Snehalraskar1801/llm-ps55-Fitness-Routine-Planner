"""Quick tests (no API needed). Run: python test_core.py   or   pytest"""
from fitness_core import (extract_json, generate_plan, plan_to_dataframe,
                          validate_plan, build_prompt)


def test_offline_all_combinations():
    for goal in ["Lose weight", "Build muscle", "Stay fit / general health",
                 "Improve flexibility", "Increase stamina"]:
        for level in ["Beginner", "Intermediate", "Advanced"]:
            plan, src = generate_plan("Offline demo (no API)", goal, level, 30,
                                      "Dumbbells, Resistance bands", 5)
            assert src == "offline" and len(plan["days"]) == 7
            assert sum(d["rest_day"] for d in plan["days"]) == 2
            df = plan_to_dataframe(plan)
            assert not df.empty


def test_json_with_fences():
    raw = '```json\n{"days":[{"day":"Monday","exercises":[]}]}\n```'
    plan = validate_plan(extract_json(raw))
    assert plan["days"][0]["rest_day"] is True


def test_prompt_contains_inputs():
    p = build_prompt("Build muscle", "Beginner", 45, "Dumbbells", 4)
    assert "Build muscle" in p and "45 minutes" in p and "Dumbbells" in p


if __name__ == "__main__":
    test_offline_all_combinations()
    test_json_with_fences()
    test_prompt_contains_inputs()
    print("All tests passed")
