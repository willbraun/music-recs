import model_download
import pytest


@pytest.fixture(autouse=True)
def reset_model_state() -> None:
    model_download._downloads.clear()
    model_download._remote_sizes.clear()
