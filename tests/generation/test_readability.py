from __future__ import annotations

from backend.app.readability import flesch_reading_ease


def test_flesch_reading_ease_is_computed_and_recorded_as_observation() -> None:
    easy = flesch_reading_ease("The cat sat on the mat. The dog ran fast.")
    harder = flesch_reading_ease(
        "The educational institution implemented a comprehensive intervention. "
        "Consequently, participating students demonstrated substantial improvement "
        "in analytical proficiency and sustained academic performance."
    )

    assert 90 <= easy <= 125
    assert harder < easy
