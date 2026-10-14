"""Row-diff packing for the physical screen mirror. No board required."""
import unittest
from mirror_link import changed_spans, parse_touch, STRIDE, FRAME_BYTES

def frame(fill=0):
    return bytes([fill]) * FRAME_BYTES

class SpanTests(unittest.TestCase):
    def test_full_frame_is_eight_row_strips(self):
        spans = changed_spans(None, frame())
        self.assertEqual(spans[0], (0, 8))
        self.assertEqual(spans[-1], (312, 320))
        self.assertEqual(len(spans), 40)

    def test_one_changed_row_is_one_strip(self):
        base = bytearray(frame(1))
        nxt = bytearray(base)
        nxt[10 * STRIDE] = 9
        self.assertEqual(changed_spans(bytes(base), bytes(nxt)), [(10, 11)])

    def test_touch_report(self):
        self.assertEqual(parse_touch('@@TOUCH 12 40 1'), (12, 40, True))
        self.assertEqual(parse_touch('@@TOUCH 12 40 0'), (12, 40, False))
        self.assertIsNone(parse_touch('@@TOUCH 300 10 1'))
        self.assertIsNone(parse_touch('@@OK'))

    def test_unchanged_rows_split_a_run(self):
        base = bytearray(frame(1))
        nxt = bytearray(base)
        nxt[2 * STRIDE] = 4
        nxt[4 * STRIDE] = 5
        self.assertEqual(changed_spans(bytes(base), bytes(nxt)), [(2, 3), (4, 5)])

if __name__ == '__main__':
    unittest.main()
