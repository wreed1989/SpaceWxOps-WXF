"""Portable, non-executable numeric export of the reviewed multi-output forest."""
import json
from pathlib import Path

import numpy as np


class FrozenForest:
    def __init__(self, trees):
        self.trees=trees

    def predict(self, features):
        # sklearn's tree input conversion is float32 even with float64 thresholds.
        x=np.asarray(features,dtype=np.float32)
        if x.ndim!=2 or not np.isfinite(x).all():
            raise ValueError('Finite two-dimensional predictor array required')
        result=np.zeros((len(x),24))
        for left,right,feature,threshold,value in self.trees:
            nodes=np.zeros(len(x),dtype=np.int64)
            active=left[nodes]>=0
            while active.any():
                rows=np.flatnonzero(active);n=nodes[rows]
                nodes[rows]=np.where(x[rows,feature[n]]<=threshold[n],left[n],right[n])
                active=left[nodes]>=0
            result+=value[nodes]
        return result/len(self.trees)


def export_model(artifact,path):
    arrays={}
    for i,estimator in enumerate(artifact['estimator'].estimators_):
        tree=estimator.tree_
        for name,value in [('left',tree.children_left),('right',tree.children_right),
                            ('feature',tree.feature),('threshold',tree.threshold),('value',tree.value[:,:,0])]:
            arrays[f'{i}_{name}']=value
    for name in ['residuals','trainingFeatureMin','trainingFeatureMax']:arrays[name]=artifact[name]
    metadata={name:artifact[name] for name in ['version','featureNames','report']}
    metadata['treeCount']=len(artifact['estimator'].estimators_)
    arrays['metadata']=np.array(json.dumps(metadata,allow_nan=False))
    np.savez_compressed(path,**arrays)


def load_model(path):
    with np.load(Path(path),allow_pickle=False) as archive:
        metadata=json.loads(str(archive['metadata']))
        trees=[tuple(archive[f'{i}_{name}'] for name in ['left','right','feature','threshold','value'])
               for i in range(metadata.pop('treeCount'))]
        artifact={**metadata,'estimator':FrozenForest(trees)}
        for name in ['residuals','trainingFeatureMin','trainingFeatureMax']:artifact[name]=archive[name]
    return artifact
