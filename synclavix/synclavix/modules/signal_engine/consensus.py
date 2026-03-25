"""
Voting and consensus logic.
"""
def aggregate_votes(votes, weights):
    # Placeholder: weighted voting
    total_weight = sum(weights.values())
    scores = {"BUY":0, "SELL":0, "HOLD":0}
    for llm, vote in votes.items():
        w = weights.get(llm, 1/6)
        scores[vote] += w
    final = max(scores, key=scores.get)
    confidence = scores[final] / total_weight if total_weight else 0
    return final, confidence
