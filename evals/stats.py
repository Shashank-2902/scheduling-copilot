"""Small statistics for the evaluation. No scipy: only math.comb."""
from math import comb


def fisher_exact_two_sided(a_pass, a_total, b_pass, b_total):
    """Two-sided Fisher exact test for two groups, each with passed and failed questions.

    The p-value is the sum of the probabilities of all tables with the same margins that are
    not more likely than the observed table.
    """
    passes = a_pass + b_pass
    total = a_total + b_total

    def probability(x):
        return comb(passes, x) * comb(total - passes, a_total - x) / comb(total, a_total)

    observed = probability(a_pass)
    low = max(0, a_total - (total - passes))
    high = min(a_total, passes)
    p = sum(probability(x) for x in range(low, high + 1) if probability(x) <= observed * (1 + 1e-9))
    return min(1.0, p)
