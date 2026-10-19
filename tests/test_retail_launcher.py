import unittest
from launch_retail_stress import eligible_children,require_fresh,snapshot,executable
class LauncherTests(unittest.TestCase):
    def test_exact_owned_new_child(self):
        rows=[{'pid':3,'parent':1,'exe':'pol.exe'}]
        self.assertEqual(eligible_children(rows,{1,2},1,'E:/pol.exe',lambda _: 'E:/pol.exe'),[3])
    def test_old_or_foreign_process_is_never_selected(self):
        for pid,parent in ((3,99),(2,1)):
            self.assertEqual(eligible_children([{'pid':pid,'parent':parent,'exe':'pol.exe'}],{1,2},1,'E:/pol.exe',lambda _:'E:/pol.exe'),[])
    def test_wrong_path_or_unknown_path_is_refused(self):
        row=[{'pid':3,'parent':1,'exe':'pol.exe'}]
        for value in ('F:/other/pol.exe',None):
            self.assertEqual(eligible_children(row,{1},1,'E:/pol.exe',lambda _:value),[])
    def test_ambiguous_children_refused(self):
        with self.assertRaises(RuntimeError):
            eligible_children([{'pid':p,'parent':1,'exe':'pol.exe'} for p in (2,3)],{1},1,'E:/pol.exe',lambda _:'E:/pol.exe')
    def test_existing_retail_client_or_launcher_refused(self):
        for name,path in (('pol.exe','E:/pol.exe'),('Windower.exe','E:/Windower.exe')):
            with self.assertRaises(RuntimeError):require_fresh([{'pid':1,'exe':name}], 'E:/Windower.exe','E:/pol.exe',lambda _:path)
    def test_other_instances_are_left_alone(self):
        require_fresh([{'pid':1,'exe':'pol.exe'}], 'E:/Windower.exe','E:/pol.exe',lambda _:'F:/other/pol.exe')
    def test_real_read_only_process_inventory(self):
        import os
        rows=snapshot();self.assertIn(os.getpid(),{r['pid'] for r in rows});self.assertTrue(executable(os.getpid()).lower().endswith('python.exe'))
if __name__=='__main__':unittest.main()
