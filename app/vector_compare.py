"""Vector clock comparison and relationship
"""


def compare_vectors(v1, v2):
    if len(v1) != len(v2):
        raise ValueError("vectors must be the same length")

    if v1 == v2:
        return "EQUAL"

    v1_comp_v2 = all(a <= b for a, b in zip(v1, v2))
    v2_comp_v1 = all(b <= a for a, b in zip(v1, v2))

    if v1_comp_v2:
        return "BEFORE"
    if v2_comp_v1:
        return "AFTER"
    return "CONCURRENT"
