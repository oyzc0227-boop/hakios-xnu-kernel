#!/usr/bin/env python3
"""pngstat.py FILE.png [FILE.png ...]: what a screenshot holds -- how much of it is not black, and how many colours.

A screenshot comes back from the phone as a PNG (`xl screenshot`), 8-bit RGB or RGBA, no interlace. This reads it with
zlib alone (no Pillow: the machines a port starts on do not always have one) and prints, per file, the size, the share
of sampled pixels whose three channels sum above 30, and the number of distinct sampled colours.

The sampling is the same for every file: 108 columns by 240 rows of the screen, whatever its size, so that two runs'
numbers can be compared. They are a blunt instrument -- what they are good for is a question with a yes or no answer,
like "is the wallpaper there": the home screen with its wallpaper is 99.9% and 13000 colours on this phone, the same
screen with a black page behind the icons 45% and 1300, and a boot text screen 11% and 4. A picture is what settles
everything else.

Exit 1 if a file is not a PNG this can read.
"""
import struct
import sys
import zlib

CHANNELS = {0: 1, 2: 3, 4: 2, 6: 4}


def read(path):
    """(width, height, rows of RGB bytes) of an 8-bit, non-interlaced PNG."""
    data = open(path, 'rb').read()
    if data[:8] != b'\x89PNG\r\n\x1a\n':
        raise ValueError('%s: not a PNG' % path)
    pos, width, height, colour, interlace, chunks = 8, None, None, None, 0, []
    while pos < len(data):
        length, kind = struct.unpack('>I4s', data[pos:pos + 8])
        body = data[pos + 8:pos + 8 + length]
        pos += 12 + length
        if kind == b'IHDR':
            width, height, depth, colour, _comp, _filter, interlace = struct.unpack('>IIBBBBB', body)
            if depth != 8 or colour not in CHANNELS:
                raise ValueError('%s: %d bits a channel, colour type %d: not read' % (path, depth, colour))
        elif kind == b'IDAT':
            chunks.append(body)
        elif kind == b'IEND':
            break
    if width is None:
        raise ValueError('%s: no header' % path)
    raw = zlib.decompress(b''.join(chunks))
    bpp = CHANNELS[colour]                     # bytes a pixel, its channels
    stride = width * bpp
    out = bytearray(width * height * 3)
    prev = bytearray(stride)
    at = 0
    for y in range(height):
        kind = raw[at]
        at += 1
        line = bytearray(raw[at:at + stride])
        at += stride
        if kind == 1:                          # Sub
            for i in range(bpp, stride):
                line[i] = (line[i] + line[i - bpp]) & 0xff
        elif kind == 2:                        # Up
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 0xff
        elif kind == 3:                        # Average
            for i in range(stride):
                a = line[i - bpp] if i >= bpp else 0
                line[i] = (line[i] + ((a + prev[i]) >> 1)) & 0xff
        elif kind == 4:                        # Paeth
            for i in range(stride):
                a = line[i - bpp] if i >= bpp else 0
                b = prev[i]
                c = prev[i - bpp] if i >= bpp else 0
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                line[i] = (line[i] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 0xff
        elif kind != 0:
            raise ValueError('%s: row %d: filter %d' % (path, y, kind))
        for x in range(width):
            s = x * bpp
            d = (y * width + x) * 3
            if colour in (0, 4):               # grey, with or without alpha
                out[d] = out[d + 1] = out[d + 2] = line[s]
            else:
                out[d], out[d + 1], out[d + 2] = line[s], line[s + 1], line[s + 2]
        prev = line
    return width, height, out


def stats(path):
    width, height, pixels = read(path)
    columns, rows = 108, 240               # the same grid for every screen, so that the numbers compare
    black = colours = total = 0
    seen = set()
    for row in range(rows):
        y = row * height // rows
        for column in range(columns):
            x = column * width // columns
            d = (y * width + x) * 3
            r, g, b = pixels[d], pixels[d + 1], pixels[d + 2]
            total += 1
            if r + g + b > 30:
                black += 1
            seen.add((r, g, b))
    print('%s: %dx%d, %.1f%% not black, %d colours (%dx%d sampled)'
          % (path, width, height, 100.0 * black / total, len(seen), columns, rows))


def main(argv):
    if not argv:
        print(__doc__.strip().splitlines()[0], file=sys.stderr)
        print('usage: tools/pngstat.py FILE.png [FILE.png ...]', file=sys.stderr)
        return 2
    failed = 0
    for path in argv:
        try:
            stats(path)
        except (OSError, ValueError, zlib.error) as error:
            print('pngstat: %s' % error, file=sys.stderr)
            failed = 1
    return failed


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
