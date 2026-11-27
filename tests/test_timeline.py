import unittest
from timeline import Clip, Timeline

class TimelineTests(unittest.TestCase):
    def setUp(self):
        self.t=Timeline(25,[Clip("a.mp4",0,100)])

    def test_delete(self):
        self.t.delete(20,40)
        self.assertEqual(self.t.clips,(Clip("a.mp4",0,20),Clip("a.mp4",40,100)))
        self.assertEqual(self.t.length,80)

    def test_copy_paste(self):
        c=self.t.copy(10,20)
        self.t.paste(50,c)
        self.assertEqual(self.t.length,110)
        self.assertEqual(self.t.clips[1],Clip("a.mp4",10,20))

    def test_cut(self):
        c=self.t.cut(0,10)
        self.assertEqual(c,(Clip("a.mp4",0,10),))
        self.t.paste(90,c)
        self.assertEqual(self.t.clips[-1],c[0])

    def test_move_right(self):
        self.t.move(10,20,80)
        self.assertEqual(self.t.clips,(Clip("a.mp4",0,10),Clip("a.mp4",20,80),Clip("a.mp4",10,20),Clip("a.mp4",80,100)))

    def test_move_left(self):
        self.t.move(70,80,10)
        self.assertEqual(self.t.clips[1],Clip("a.mp4",70,80))
        self.assertEqual(self.t.length,100)

    def test_move_inside(self):
        self.t.move(10,20,15)
        self.assertFalse(self.t.undo())

    def test_replace_external(self):
        self.t.replace(20,40,[Clip("b.mp4",10,15)])
        self.assertEqual(self.t.length,85)
        self.assertEqual(self.t.clips[1].source,"b.mp4")

    def test_hide_preserved_on_copy(self):
        self.t.hide(10,20)
        self.t.paste(100,self.t.copy(10,20))
        self.assertTrue(self.t.clips[-1].hidden)
        self.assertTrue(self.t.clips[-1].mute)

    def test_undo_redo(self):
        self.t.delete(10,20)
        self.assertTrue(self.t.undo())
        self.assertEqual(self.t.length,100)
        self.assertTrue(self.t.redo())
        self.assertEqual(self.t.length,90)
        self.t.undo()
        self.t.split(50)
        self.assertFalse(self.t.redo())

    def test_invalid_atomic(self):
        original=self.t.clips
        with self.assertRaises(ValueError): self.t.move(10,20,101)
        self.assertEqual(self.t.clips,original)
        with self.assertRaises(ValueError): self.t.insert(101,[Clip("b",0,2)])
        self.assertEqual(self.t.clips,original)

    def test_json_roundtrip(self):
        self.t.hide(5,10)
        self.assertEqual(Timeline.from_dict(self.t.to_dict()).clips,self.t.clips)

    def test_legacy(self):
        t=Timeline.from_legacy({"file":"a","intervals":[[0.041,0.12]],"mute":True},25,100)
        self.assertEqual(t.clips[1],Clip("a",2,3,True,True))
        self.assertEqual(t.length,100)

    def test_cross_clip(self):
        self.t.insert(50,[Clip("b",0,10)])
        self.assertEqual(self.t.copy(45,65),(Clip("a.mp4",45,50),Clip("b",0,10),Clip("a.mp4",50,55)))

if __name__=="__main__":
    unittest.main()
