import unittest
from reference_data import reference_data
class ReferenceTests(unittest.TestCase):
    def test_both_cohorts_and_subtypes_have_real_individual_poses(self):
        for player,count in [('djokovic',88),('sinner',219)]:
            for subtype in [1,2]:
                result=reference_data(player,subtype)
                self.assertEqual(result['sourceTotal'],count)
                self.assertLess(result['total'],count)
                self.assertEqual(result['excluded'],count-result['total'])
                self.assertEqual(result['view']['view'],'rear')
                self.assertEqual(result['view']['sourceView'],'unknown')
                self.assertTrue(all(s['serveNumber']==subtype for s in result['serves']))
                self.assertEqual(len(result['poses']),101)
                self.assertEqual(len(result['poses'][0]),17)
                self.assertIn(result['selected'],[s['id'] for s in result['serves']])
                self.assertEqual(result['kind'],'individual')
    def test_unknown_player_and_wrong_subtype_selection_rejected(self):
        with self.assertRaises(ValueError): reference_data('../private',1)
        first=reference_data('sinner',1)
        with self.assertRaises(ValueError): reference_data('sinner',2,first['selected'])
    def test_excluded_reference_cannot_be_selected_explicitly(self):
        import csv,json
        from reference_data import ROOT
        for player,folder in [('djokovic','reference'),('sinner','sinner')]:
            base=ROOT/folder/'results'
            manifest=json.loads((base/'rear_view_manifest.json').read_text())
            excluded=next(r['filename'] for r in manifest['records'] if not r['included'])
            with (base/'phase_events.csv').open() as f:
                row=next(r for r in csv.DictReader(f) if r['filename']==excluded)
            with self.assertRaises(ValueError):reference_data(player,int(row['serve_number']),excluded)
