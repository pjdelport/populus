import pytest

from populus.contracts import decode_multi


@pytest.mark.parametrize(
    'input,expected',
    (
        ('0x00000000000000000000000000000000000000000000000000000000000000060000000000000000000000000000000000000000000000000000000000000001', [6, 1]),
        ('0x00000000000000000000000000000000000000000000000000000000ffffffff00000000000000000000000000000000000000000000000000000000ffffffff', [2**32-1, 2**32-1]),
    )
)
def test_decode_two_uint32(input, expected):
    output = decode_multi(['uint32', 'uint32'], input)
    assert output == expected


def test_decode_various():
    data = ('0x00000000000000000000000082a978b3f5962a5b0957d9ee9eef472ee55b42f10000000000000'
            '0000000000000000000000000000000000000000000000000017374757069642070696e6b20616e69'
            '6d616c000000000000000000000000000000000000000000000000000000000000000000000000000'
            '00000000000000000')

    expected = [b'82a978b3f5962a5b0957d9ee9eef472ee55b42f1', 1,
                b'stupid pink animal\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00', 0]
    output = decode_multi(['address', 'uint32', 'bytes32', 'int32'], data)
