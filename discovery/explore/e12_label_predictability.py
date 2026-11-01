"""Explore: can the reviewers' M-vs-F labels (669 candidates) be predicted from numeric features alone?"""
import os, pickle, sys, glob
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from common import WORK, DECISIONS
from s07b_group import load_verdicts
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.model_selection import cross_val_predict
from sklearn.metrics import roc_auc_score
v = load_verdicts()
cands = {x["id"]: x for x in pickle.load(open(os.path.join(WORK, "candidates.pkl"), "rb"))}
cols = ["n", "ic", "uniform", "contrast", "median_ioi", "stepwise", "pitches", "n_occ", "passages", "n_scenes", "n_acts", "n_operas", "top_stream_share"]
ids = [i for i in v if v[i]["label"] in ("M", "F") and i in cands]
X = np.array([[cands[i]["f"][k] for k in cols] for i in ids]); y = np.array([v[i]["label"] == "M" for i in ids])
m = GradientBoostingClassifier(n_estimators=150, max_depth=3, random_state=0)
p = cross_val_predict(m, X, y, cv=5, method="predict_proba")[:, 1]
print(len(ids), "labelled; M share %.2f; CV AUC %.3f" % (y.mean(), roc_auc_score(y, p)))
for t in (0.1, 0.2, 0.3):
    low = p < t
    print(f"p(M) < {t}: {low.sum()} candidates, of which actually M: {(y & low).sum()}")
m.fit(X, y)
print("importance:", dict(zip(cols, np.round(m.feature_importances_, 2))))
