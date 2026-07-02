# SPDX-License-Identifier: Apache-2.0
"""Tests for semver comparison utility.

Edge cases from semver 2.0.0 section 11 and design.md.
"""

from scripts.semver_compare import cmp_semver, parse_semver


class TestParseSemver:
    """Test semver string parsing."""

    def test_simple_version(self) -> None:
        assert parse_semver("1.2.3") == (1, 2, 3, None)

    def test_v_prefix(self) -> None:
        assert parse_semver("v1.2.3") == (1, 2, 3, None)

    def test_prerelease(self) -> None:
        assert parse_semver("v1.0.0-beta.0") == (
            1, 0, 0, ["beta", 0],
        )

    def test_prerelease_numeric_only(self) -> None:
        assert parse_semver("v1.0.0-1") == (1, 0, 0, [1])

    def test_prerelease_complex(self) -> None:
        assert parse_semver("v1.0.0-alpha.1.beta") == (
            1, 0, 0, ["alpha", 1, "beta"],
        )


class TestCmpSemver:
    """Test semver comparison per section 11."""

    def test_major_version_ordering(self) -> None:
        a = parse_semver("v1.0.0")
        b = parse_semver("v2.0.0")
        assert cmp_semver(a, b) == -1

    def test_minor_version_ordering(self) -> None:
        a = parse_semver("v1.0.0")
        b = parse_semver("v1.1.0")
        assert cmp_semver(a, b) == -1

    def test_patch_version_ordering(self) -> None:
        a = parse_semver("v1.0.0")
        b = parse_semver("v1.0.1")
        assert cmp_semver(a, b) == -1

    def test_equal_versions(self) -> None:
        a = parse_semver("v1.0.0")
        b = parse_semver("v1.0.0")
        assert cmp_semver(a, b) == 0

    def test_prerelease_lower_than_release(self) -> None:
        """Section 11: pre-release has lower precedence."""
        a = parse_semver("v1.0.0-beta.0")
        b = parse_semver("v1.0.0")
        assert cmp_semver(a, b) == -1

    def test_release_higher_than_prerelease(self) -> None:
        a = parse_semver("v1.0.0")
        b = parse_semver("v1.0.0-beta.0")
        assert cmp_semver(a, b) == 1

    def test_numeric_lower_than_alphanumeric(self) -> None:
        """Section 11: numeric identifiers have lower
        precedence than alphanumeric."""
        a = parse_semver("v1.0.0-1")
        b = parse_semver("v1.0.0-alpha")
        assert cmp_semver(a, b) == -1

    def test_alpha_before_alpha1(self) -> None:
        """Shorter set has lower precedence when prefix
        matches."""
        a = parse_semver("v1.0.0-alpha")
        b = parse_semver("v1.0.0-alpha.1")
        assert cmp_semver(a, b) == -1

    def test_alpha1_before_alpha_beta(self) -> None:
        a = parse_semver("v1.0.0-alpha.1")
        b = parse_semver("v1.0.0-alpha.beta")
        assert cmp_semver(a, b) == -1

    def test_alpha_beta_before_beta(self) -> None:
        a = parse_semver("v1.0.0-alpha.beta")
        b = parse_semver("v1.0.0-beta")
        assert cmp_semver(a, b) == -1

    def test_beta_before_beta2(self) -> None:
        a = parse_semver("v1.0.0-beta")
        b = parse_semver("v1.0.0-beta.2")
        assert cmp_semver(a, b) == -1

    def test_beta2_before_beta11(self) -> None:
        """Numeric identifiers compared as integers,
        not strings."""
        a = parse_semver("v1.0.0-beta.2")
        b = parse_semver("v1.0.0-beta.11")
        assert cmp_semver(a, b) == -1

    def test_beta11_before_rc1(self) -> None:
        a = parse_semver("v1.0.0-beta.11")
        b = parse_semver("v1.0.0-rc.1")
        assert cmp_semver(a, b) == -1

    def test_rc1_before_release(self) -> None:
        a = parse_semver("v1.0.0-rc.1")
        b = parse_semver("v1.0.0")
        assert cmp_semver(a, b) == -1


class TestFullOrderingChain:
    """Test the full ordering chain from design.md."""

    def test_complete_ordering(self) -> None:
        """v1.0.0-alpha < v1.0.0-alpha.1 <
        v1.0.0-alpha.beta < v1.0.0-beta <
        v1.0.0-beta.2 < v1.0.0-beta.11 <
        v1.0.0-rc.1 < v1.0.0"""
        versions = [
            "v1.0.0-alpha",
            "v1.0.0-alpha.1",
            "v1.0.0-alpha.beta",
            "v1.0.0-beta",
            "v1.0.0-beta.2",
            "v1.0.0-beta.11",
            "v1.0.0-rc.1",
            "v1.0.0",
        ]
        for i in range(len(versions) - 1):
            a = parse_semver(versions[i])
            b = parse_semver(versions[i + 1])
            assert cmp_semver(a, b) == -1, (
                f"Expected {versions[i]} < {versions[i + 1]}"
            )

    def test_reverse_ordering_all_greater(self) -> None:
        """Reverse chain: each should be > the next."""
        versions = [
            "v1.0.0",
            "v1.0.0-rc.1",
            "v1.0.0-beta.11",
            "v1.0.0-beta.2",
            "v1.0.0-beta",
            "v1.0.0-alpha.beta",
            "v1.0.0-alpha.1",
            "v1.0.0-alpha",
        ]
        for i in range(len(versions) - 1):
            a = parse_semver(versions[i])
            b = parse_semver(versions[i + 1])
            assert cmp_semver(a, b) == 1, (
                f"Expected {versions[i]} > {versions[i + 1]}"
            )
