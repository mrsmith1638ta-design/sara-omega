import math

from app.science.riemann.baez_duarte import mobius_sieve
from app.science.riemann.vasyunin import (
    EULER_GAMMA,
    d_squared,
    determinant_ratio_d_squared,
    gram_entry,
    gram_matrix,
    optimal_coefficients,
    q_n,
    residual_against_negative_mobius,
    schur_extension,
    v_k,
)


def test_v_k_closed_form():
    assert math.isclose(v_k(1), 1.0 - EULER_GAMMA, rel_tol=1e-14, abs_tol=1e-14)


def test_gram_is_symmetric_and_has_reference_g11():
    g = gram_matrix(6)
    for i in range(6):
        assert g[i][i] > 0.0
        for j in range(6):
            assert math.isclose(g[i][j], g[j][i], rel_tol=1e-12, abs_tol=1e-12)
    assert math.isclose(gram_entry(1, 1), math.log(2.0 * math.pi) - EULER_GAMMA, rel_tol=1e-12)


def test_quadratic_identity_at_optimizer():
    c = optimal_coefficients(6)
    assert math.isclose(q_n(c), d_squared(6), rel_tol=1e-10, abs_tol=1e-10)


def test_determinant_ratio_matches_distance():
    for n in (2, 3, 4, 5):
        assert math.isclose(
            determinant_ratio_d_squared(n),
            d_squared(n),
            rel_tol=2e-9,
            abs_tol=2e-9,
        )


def test_schur_decrement_matches_direct_next_distance():
    for n in (2, 3, 4, 5):
        result = schur_extension(n)
        assert result["s_n"] > 0.0
        assert result["absolute_error"] < 2e-9
        assert result["recursive_next_d_squared"] <= result["d_n_squared"] + 1e-12


def test_mobius_residual_correction_has_expected_dimensions():
    data = residual_against_negative_mobius(mobius_sieve(8))
    assert len(data["baseline"]) == 8
    assert len(data["residual"]) == 8
    assert len(data["correction"]) == 8
