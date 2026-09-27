#!/usr/bin/env python3
"""Reproduce chapter calculations; this is not a ChrisCPU timing test."""
from fractions import Fraction


def split(address, line_bytes=64, sets=64):
    block, offset = divmod(address, line_bytes)
    tag, index = divmod(block, sets)
    return tag, index, offset


def lru_misses(addresses, ways=8):
    cache = {}
    misses = []
    for address in addresses:
        tag, index, _ = split(address)
        lines = cache.setdefault(index, [])
        miss = tag not in lines
        misses.append(miss)
        if not miss:
            lines.remove(tag)
        elif len(lines) == ways:
            lines.pop(0)
        lines.append(tag)
    return misses


def main():
    assert split(0x12340) == (18, 13, 0)
    assert split(0x13340) == (19, 13, 0)
    assert 32768 // (8 * 64) == 64
    for count in (8, 9):
        addresses = [i * 4096 for i in range(count)] * 3
        misses = lru_misses(addresses)
        assert all(misses[:count])
        assert all(misses[count:]) if count == 9 else not any(misses[count:])
    sequential = lru_misses(range(0, 4096, 4))
    assert sum(sequential) == 64
    assert Fraction(4, 64) == Fraction(1, 16)
    expected = ['4.00', '4.96', '6.40', '8.80', '13.60']
    for percentage, value in zip((0, 2, 5, 10, 20), expected):
        amat = 4 + Fraction(percentage, 100) * (12 + Fraction(1, 5) * 180)
        assert f'{float(amat):.2f}' == value
    print('cache examples: address decomposition, LRU conflicts, sequential locality and 5 AMAT cases passed')
    print('Scope: illustrative model only; no kernel execution or hardware timing evidence.')


if __name__ == '__main__':
    main()
