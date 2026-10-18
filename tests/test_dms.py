"""Synthetic geometry fixtures are tests, not player measurements."""
import copy,json,tempfile,unittest
from pathlib import Path
import numpy as np
from dms.contract import (ContractError,base_metadata,interior_angles,validate_packet,
                          write_packet,load_packet,compare_event,json_safe)
from dms.definitions import ANGLE_NAMES,TRIPLETS,LEGACY_TO_DMS_ANGLES
from dms.adapters import export_mediapipe_image

class DMSTests(unittest.TestCase):
    def packet(self,dim=2):
        p=np.random.default_rng(12).normal(size=(5,17,dim))
        t=np.arange(5)/30;c=np.ones((5,17))*.9;a=interior_angles(p)
        src={'model':'synthetic-test','coordinate_system':'image_2d' if dim==2 else 'camera_3d','camera_view':'rear_oblique','fps':30.,
             'axis_convention':'x_right_y_down' if dim==2 else 'xyz_test','units':'pixels' if dim==2 else 'meters','metric_space':True,'comparison_profile_id':'synthetic-test-rig'}
        events={'max_knee_flexion':{'frame':2,'timestamp':float(t[2]),'confidence':.9,'method':'synthetic_fixture','definition_id':'test-knee-v1','status':'validated'},'contact':None}
        m=base_metadata('synthetic_test','TEST FIXTURE','right',src,p,a,t,c,events)
        m['pose']['mapping_evidence']='Synthetic canonical-index fixture'
        m['joint_confidence']['score_definition']='synthetic-test-score'
        return m,dict(pose=p,features=a,timestamps=t,joint_confidence=c)

    def test_known_knee_angle_and_missing_joint(self):
        m,a=self.packet();a['pose'][:,11]=[0,0];a['pose'][:,13]=[1,0];a['pose'][:,15]=[1,1]
        self.assertTrue(np.allclose(interior_angles(a['pose'])[:,2],90))
        a['pose'][1,15]=np.nan;self.assertTrue(np.isnan(interior_angles(a['pose'])[1,2]))
        a['pose'][2,15]=a['pose'][2,13];self.assertTrue(np.isnan(interior_angles(a['pose'])[2,2]))

    def test_roundtrip_and_positive_knee_integration(self):
        m,a=self.packet()
        with tempfile.TemporaryDirectory() as tmp:
            f=write_packet(Path(tmp)/'packet',m,a);p=load_packet(f)
            result=compare_event(p,p,event_name='max_knee_flexion')
            self.assertTrue(result['comparable']);self.assertEqual(result['right_minus_left'],[0.,0.])
            self.assertEqual(result['metrics'],['left_knee_flexion','right_knee_flexion'])

    def test_reject_2d_3d(self):
        result=compare_event(self.packet(2),self.packet(3),event_name='max_knee_flexion')
        self.assertFalse(result['comparable']);self.assertEqual(result['reason'],'2D and 3D angle representations differ')

    def test_reject_unvalidated_or_falsely_named_canonical(self):
        m,a=self.packet();m['pose']['mapping_validated']=False
        with self.assertRaises(ContractError):validate_packet(m,a)
        m['pose'].update(joint_schema='djoker17_unvalidated',joint_names=None);m['features']['definitions_validated']=False
        self.assertTrue(validate_packet(m,a)['valid'])
        self.assertFalse(compare_event((m,a),(m,a),event_name='max_knee_flexion')['comparable'])

    def test_reject_definition_order_units_and_bad_feature_values(self):
        for mutate in [lambda m,a:m['features']['names'].reverse(), lambda m,a:m['features'].update(units='radians'),
                       lambda m,a:a['features'].__setitem__((0,2),44.),lambda m,a:m['features']['definitions'][0].update(calculation='180_minus_angle')]:
            m,a=self.packet();mutate(m,a)
            with self.assertRaises(ContractError):validate_packet(m,a)

    def test_reject_camera_handedness_confidence_and_event(self):
        changes=[lambda m,a:m['source'].update(camera_view='front'),lambda m,a:m['source'].update(comparison_profile_id=None),
                 lambda m,a:m.update(handedness='left'),lambda m,a:m['events'].update(max_knee_flexion=None),
                 lambda m,a:m['events']['max_knee_flexion'].update(status='estimated'),
                 lambda m,a:m['events']['max_knee_flexion'].update(definition_id='another-event'),
                 lambda m,a:a['joint_confidence'].__setitem__((2,13),.1),
                 lambda m,a:m['joint_confidence'].update(kind='availability'),
                 lambda m,a:a['features'].__setitem__((2,2),np.nan)]
        for change in changes:
            left=self.packet();m,a=self.packet();change(m,a)
            self.assertFalse(compare_event(left,(m,a),event_name='max_knee_flexion')['comparable'])

    def test_shape_time_event_and_nonfinite_validation(self):
        changes=[lambda m,a:m['pose'].update(shape=[4,17,2]),lambda m,a:a['timestamps'].__setitem__(3,0),
                 lambda m,a:m['events']['max_knee_flexion'].update(frame=5),
                 lambda m,a:m['events']['max_knee_flexion'].update(timestamp=.5),
                 lambda m,a:a['features'].__setitem__((0,0),np.inf)]
        for change in changes:
            m,a=self.packet();change(m,a)
            with self.assertRaises(ContractError):validate_packet(m,a)
        self.assertEqual(json.dumps(json_safe({'missing':np.nan}),allow_nan=False),'{"missing": null}')

    def test_media_pipe_is_2d_and_aspect_correct(self):
        landmarks=np.zeros((5,33,3));landmarks[:,:,:2]=np.random.default_rng(5).random((5,33,2));landmarks[:,:,2]=9999
        # A 90-degree right triangle in pixel space must remain 90 degrees on a non-square image.
        landmarks[:,23,:2]=[0,0];landmarks[:,25,:2]=[.5,0];landmarks[:,27,:2]=[.5,1]
        with tempfile.TemporaryDirectory() as tmp:
            path=export_mediapipe_image(Path(tmp)/'mp',landmarks=landmarks,image_size=(1920,1080),timestamps=np.arange(5)/30,visibility=np.ones((5,33))*.9,
                shot_id='synthetic_mp',player='TEST FIXTURE',handedness='right',camera_view='rear_oblique',events={})
            m,a=load_packet(path);self.assertEqual(a['pose'].shape,(5,17,2));np.testing.assert_allclose(a['pose'][:,13,0],960)
            np.testing.assert_allclose(a['features'][:,2],90)
            self.assertEqual(m['features']['representation'],'projected_2d')

    def test_paths_and_nonstandard_json(self):
        m,a=self.packet();m['pose']['file']='../outside.npy'
        with self.assertRaises(ContractError):validate_packet(m,a)
        with tempfile.TemporaryDirectory() as tmp:
            f=Path(tmp)/'bad.json';f.write_text('{"bad":NaN}')
            with self.assertRaises(ContractError):load_packet(f)

    def test_legacy_reorder_preserves_computed_definitions(self):
        from reference.analyze import angles
        # Synthetic pose in H36M; transfer only the 12 shared limb joints explicitly for this numerical test.
        p=np.random.default_rng(7).normal(size=(20,17,3));c=np.full((20,17,3),np.nan)
        for canonical,h36m in {5:11,6:14,7:12,8:15,9:13,10:16,11:4,12:1,13:5,14:2,15:6,16:3}.items():c[:,canonical]=p[:,h36m]
        np.testing.assert_allclose(interior_angles(c),angles(p)[:,LEGACY_TO_DMS_ANGLES],atol=1e-8)

if __name__=='__main__':unittest.main()
