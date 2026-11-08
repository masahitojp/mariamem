import unittest
from undo_analysis import link
class LinkTests(unittest.TestCase):
 def fixtures(self):return ({'child':1,'rseg':100,'ea':104,'start':20,'end':60},{'child':1,'rseg':100,'scope':7,'thread':2,'page_matches':True,'start':10,'end':50},{'child':1,'rseg':100,'scope':7,'thread':2,'acquired':5,'release_before':55})
 def test_matching(self):self.assertTrue(link(*self.fixtures()))
 def test_wrong_instance_rseg_scope_thread_page_or_interval(self):
  for idx,key,val in [(0,'child',2),(0,'rseg',200),(0,'ea',108),(1,'scope',8),(1,'thread',3),(1,'page_matches',False),(2,'release_before',40),(0,'start',51)]:
   x=list(self.fixtures());x[idx][key]=val
   with self.subTest(idx=idx,key=key):self.assertFalse(link(*x))
if __name__=='__main__':unittest.main()
