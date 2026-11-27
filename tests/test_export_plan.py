import unittest
from fractions import Fraction
from timeline import Clip, Timeline
from export_plan import Source, plan, statistics

class PlanTests(unittest.TestCase):
    def setUp(self):
        self.s=Source(100, Fraction(25), 640,480,"verified",(0,25,50,75,100))
    def make(self,clips,sources=None,signature="verified"):
        return plan(Timeline(25,clips),sources or {"a":self.s},output_signature=signature)
    def test_exact_boundary(self):
        self.assertEqual(statistics(self.make([Clip("a",25,75)]))["COPY"],50)
    def test_partial_boundaries(self):
        p=self.make([Clip("a",10,90)])
        self.assertEqual([(x.action,x.start,x.end,x.output_start) for x in p],
            [("ENCODE",10,25,0),("COPY",25,75,15),("ENCODE",75,90,65)])
    def test_short_clip(self):
        self.assertEqual(self.make([Clip("a",26,49)])[0].action,"ENCODE")
    def test_hidden(self):
        p=self.make([Clip("a",0,100,True,True)])
        self.assertEqual(p[0].action,"GENERATE")
        self.assertTrue(p[0].mute)
    def test_unverified_signature(self):
        self.assertEqual(self.make([Clip("a",0,100)],signature=None)[0].action,"ENCODE")
    def test_no_verified_boundaries(self):
        s=Source(100,Fraction(25),640,480,"verified")
        self.assertEqual(self.make([Clip("a",0,100)],{"a":s})[0].action,"ENCODE")
    def test_incompatible_resolution(self):
        s=Source(100,Fraction(25),1280,720,"other")
        p=self.make([Clip("a",0,25),Clip("b",0,25)],{"a":self.s,"b":s})
        self.assertEqual([x.action for x in p],["COPY","CONVERT"])
    def test_mixed_rate_rejected(self):
        s=Source(100,Fraction(30),640,480)
        with self.assertRaises(ValueError): self.make([Clip("a",0,25)],{"a":s})
    def test_reordered_clips(self):
        p=self.make([Clip("a",75,100),Clip("a",0,25),Clip("a",75,100)])
        self.assertEqual([x.output_start for x in p],[0,25,50])
    def test_source_bounds(self):
        with self.assertRaises(ValueError): self.make([Clip("a",0,101)])
    def test_unverified_eof(self):
        s=Source(100,Fraction(25),640,480,"verified",(0,25,50,75))
        self.assertEqual(self.make([Clip("a",50,100)],{"a":s})[-1].action,"ENCODE")
    def test_invalid_boundaries(self):
        with self.assertRaises(ValueError): Source(100,Fraction(25),640,480,"x",(0,50,25))
    def test_exhaustive_ranges(self):
        for a in range(100):
            for b in range(a+1,101):
                p=self.make([Clip("a",a,b)])
                self.assertEqual(sum(x.frames for x in p),b-a)
                self.assertEqual([n for x in p for n in range(x.start,x.end)],list(range(a,b)))

if __name__=="__main__":
    unittest.main()
