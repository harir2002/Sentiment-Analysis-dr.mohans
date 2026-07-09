import pytest

from app.providers import sarvam_stt_coordinator as coord


@pytest.fixture(autouse=True)
def reset_shared_states():
    coord._states.clear()
    yield
    coord._states.clear()


@pytest.mark.asyncio
async def test_shared_state_isolated_per_audio_path():
    first = await coord.get_shared_state("/tmp/audio-one.wav", None)
    first.transcript = "first call transcript"

    second = await coord.get_shared_state("/tmp/audio-two.wav", None)

    assert second.transcript is None
    assert first is not second


@pytest.mark.asyncio
async def test_shared_state_reused_for_same_audio_path():
    first = await coord.get_shared_state("/tmp/same.wav", None)
    first.transcript = "cached transcript"

    second = await coord.get_shared_state("/tmp/same.wav", None)

    assert second is first
    assert second.transcript == "cached transcript"


@pytest.mark.asyncio
async def test_clear_shared_state_removes_audio_entry():
    state = await coord.get_shared_state("/tmp/clear-me.wav", None)
    state.transcript = "done"

    coord.clear_shared_state("/tmp/clear-me.wav")

    fresh = await coord.get_shared_state("/tmp/clear-me.wav", None)
    assert fresh.transcript is None
