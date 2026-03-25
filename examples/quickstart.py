"""Quickstart: 3 lines to rate an agent and check reputation."""
from agent_rating_protocol import RatingRecord, RatingStore, get_reputation

store = RatingStore("demo_ratings.jsonl")
store.append_rating(RatingRecord(rater_id="agent-a", ratee_id="agent-b", reliability=85, accuracy=90, rater_chain_age_days=100, rater_total_ratings_given=50))
print(get_reputation(store, "agent-b"))
