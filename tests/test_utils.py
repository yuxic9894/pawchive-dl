import hashlib

import pytest

from pawchive_dl.utils import format_bytes, generate_file_path, get_sha256_hash


def test_get_sha256_hash(tmp_path) -> None:
    content = b"hello world\n"
    fpath = tmp_path / "test.txt"
    fpath.write_bytes(content)

    result = get_sha256_hash(str(fpath))

    expected = hashlib.sha256(content).hexdigest()
    assert result == expected


@pytest.mark.parametrize(
    "size,expected",
    [
        (0, "0.00 B"),
        (1, "1.00 B"),
        (1023, "1023.00 B"),
        (1024, "1.00 KiB"),
        (1536, "1.50 KiB"),
        (1048576, "1.00 MiB"),
        (1048576 * 1.5, "1.50 MiB"),
        (1073741824, "1.00 GiB"),
        (1073741824 * 1.5, "1.50 GiB"),
        (1099511627776, "1.00 TiB"),
    ],
)
def test_format_bytes(size, expected):
    assert format_bytes(size) == expected



def test_generate_file_path_raises_valueerror():
    with pytest.raises(ValueError) as exc:
        generate_file_path(
            base_path="/base",
            output_template="folder/{missing}.txt",
            template_variables={},
        )
    assert "Missing template key" in str(exc.value)
