"""Export a trained sklearn GradientBoostingClassifier to plain JSON and score with it.

The same JSON is used by the Python API and by the browser workbench, so both give identical results.
Per-feature contributions use path attribution (Saabas): walking each tree, the change in node value at
every split is credited to that split's feature. Contributions + bias add up exactly to the model's log-odds.
"""
import json, math
import numpy as np


def _node_values(tree):
    left, right = tree.children_left, tree.children_right
    val = tree.value[:, 0, 0].copy()
    w = tree.weighted_n_node_samples

    def rec(i):
        if left[i] == -1:
            return val[i]
        a, b = rec(left[i]), rec(right[i])
        val[i] = (a * w[left[i]] + b * w[right[i]]) / (w[left[i]] + w[right[i]])
        return val[i]
    rec(0)
    return val


def export_model(gb, feature_names, y_train_mean, meta=None):
    trees = []
    for est in gb.estimators_[:, 0]:
        t = est.tree_
        v = _node_values(t)
        trees.append({"f": t.feature.tolist(), "t": [round(float(x), 6) for x in t.threshold],
                      "l": t.children_left.tolist(), "r": t.children_right.tolist(),
                      "v": [round(float(x), 6) for x in v]})
    init = math.log(y_train_mean / (1 - y_train_mean))
    return {"features": list(feature_names), "init": init, "lr": float(gb.learning_rate), "trees": trees, **(meta or {})}


def raw_and_contribs(model, x):
    """x: list of feature values in model['features'] order. Returns (raw_logit, contribs list, bias)."""
    contribs = [0.0] * len(x)
    bias = model["init"]
    raw = model["init"]
    lr = model["lr"]
    for t in model["trees"]:
        f, th, l, r, v = t["f"], t["t"], t["l"], t["r"], t["v"]
        i = 0
        bias += lr * v[0]
        while l[i] != -1:
            j = l[i] if x[f[i]] <= th[i] else r[i]
            contribs[f[i]] += lr * (v[j] - v[i])
            i = j
        raw += lr * v[i]
    return raw, contribs, bias


def sigmoid(z):
    return 1 / (1 + math.exp(-z))


def save(model, path):
    with open(path, "w") as fh:
        json.dump(model, fh, separators=(",", ":"))


def load(path):
    with open(path) as fh:
        return json.load(fh)
