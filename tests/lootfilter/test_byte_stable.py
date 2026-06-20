import os
from osrs_planner.lootfilter.generate import generate_filter
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
def test_committed_matches_fresh():
    assert open(os.path.join(REPO, "outputs", "gilded-tome-iron.rs2f"), encoding="utf-8").read() == generate_filter()
