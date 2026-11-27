import unittest
from media_inspect import nal_types,is_idr,nal_length_size,packet_grid,unhex_dump

def packet(*types):
    return b"".join(b"\x00\x00\x00\x02"+bytes([t])+b"\x80" for t in types)

class InspectorTests(unittest.TestCase):
    def test_idr(self):
        self.assertTrue(is_idr(packet(6,5,5),4))
        self.assertFalse(is_idr(packet(1),4))
        self.assertFalse(is_idr(packet(7,5),4))
        self.assertFalse(is_idr(packet(1,5),4))
    def test_truncated(self):
        with self.assertRaises(ValueError): nal_types(b"\x00\x00\x00\x05\x65",4)
    def test_avcc(self):
        self.assertEqual(nal_length_size(bytes([1,100,0,31,255,225,0])),4)
    def test_hex(self):
        self.assertEqual(unhex_dump("00000000: 0164 001f  ...."),bytes([1,100,0,31]))
    def test_reordered(self):
        self.assertEqual(packet_grid([(0,-2,True),(2,-1,False),(1,0,False),(3,1,True),(5,2,False),(4,3,False)],6,1),(0,3,6))
    def test_cross_boundary(self):
        with self.assertRaises(ValueError): packet_grid([(0,0,True),(2,1,False),(1,2,True)],3,1)
    def test_duplicate(self):
        with self.assertRaises(ValueError): packet_grid([(0,0,True),(0,1,False)],2,1)
    def test_non_idr_start(self):
        with self.assertRaises(ValueError): packet_grid([(0,0,False)],1,1)
    def test_bad_dts(self):
        with self.assertRaises(ValueError): packet_grid([(0,0,True),(1,0,False)],2,1)
    def test_bad_grid(self):
        with self.assertRaises(ValueError): packet_grid([(0,0,True),(3,2,False)],2,2)
    def test_incomplete(self):
        with self.assertRaises(ValueError): packet_grid([(0,0,True)],2,1)

if __name__=="__main__":
    unittest.main()
