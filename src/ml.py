"""Phase 6: predict whether the team batting first wins (section 11).

    python -m src.ml            # after the pipeline; writes data/export/ml/

Model A uses information available after the first-innings Powerplay; Model B
adds the chasing side's Powerplay. Seasons are split chronologically:
train = all but the last three seasons, validation = the third-last season,
test = the last two seasons. Hyper-parameters are chosen by forward-chaining
cross-validation over the train and validation seasons (each fold trains on
earlier seasons only); the test seasons are scored exactly once.
"""
from __future__ import annotations

import argparse
import itertools
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (accuracy_score, confusion_matrix, f1_score, precision_score, recall_score,
                             roc_auc_score)
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier, plot_tree

from . import charts
from .config import PROJECT_ROOT, Paths
from .features import MODEL_A, MODEL_B, TARGET

SEED = 42
FEATURE_SETS = {"A": MODEL_A, "B": MODEL_B}
GRIDS = {
    "logistic_regression": {"C": [0.01, 0.1, 1.0, 10.0]},
    "decision_tree": {"max_depth": [2, 3, 4, 5], "min_samples_leaf": [5, 20]},
    "random_forest": {"max_depth": [3, 5, None], "min_samples_leaf": [5, 20]},
}
UPSET_CONFIDENCE = 0.7


def make_model(name: str, **params):
    impute = SimpleImputer(strategy="median")
    if name == "logistic_regression":
        return make_pipeline(impute, StandardScaler(), LogisticRegression(max_iter=1000, **params))
    if name == "decision_tree":
        return make_pipeline(impute, DecisionTreeClassifier(random_state=SEED, **params))
    if name == "random_forest":
        return make_pipeline(impute, RandomForestClassifier(n_estimators=300, random_state=SEED,
                                                            n_jobs=-1, **params))
    raise ValueError(name)


@dataclass
class Split:
    train: list[int]
    val: list[int]
    test: list[int]


def season_split(seasons, n_test: int = 2, n_val: int = 1) -> Split:
    s = sorted(set(int(x) for x in seasons))
    if len(s) < n_test + n_val + 1:
        raise ValueError(f"need at least {n_test + n_val + 1} seasons, have {len(s)}")
    return Split(s[:-(n_test + n_val)], s[-(n_test + n_val):-n_test], s[-n_test:])


def forward_folds(df: pd.DataFrame, seasons: list[int]):
    """Train on seasons before s, validate on s, for every s after the first."""
    for s in seasons[1:]:
        yield s, df.index[df.season < s], df.index[df.season == s]


def metrics(y, pred, score) -> dict:
    tn, fp, fn, tp = confusion_matrix(y, pred, labels=[0, 1]).ravel()
    auc = roc_auc_score(y, score) if len(set(y)) == 2 else np.nan
    return {"n": len(y), "accuracy": accuracy_score(y, pred),
            "precision": precision_score(y, pred, zero_division=0),
            "recall": recall_score(y, pred, zero_division=0), "f1": f1_score(y, pred, zero_division=0),
            "roc_auc": auc, "tn": tn, "fp": fp, "fn": fn, "tp": tp}


def tune(df: pd.DataFrame, features: list[str], name: str, seasons: list[int]) -> tuple[dict, pd.DataFrame]:
    rows, candidates = [], []
    grid = GRIDS[name]
    for values in itertools.product(*grid.values()):
        params = dict(zip(grid, values))
        candidates.append(params)
        scores = []
        for s, tr, va in forward_folds(df, seasons):
            y_tr, y_va = df.loc[tr, TARGET], df.loc[va, TARGET]
            if y_tr.nunique() < 2 or y_va.nunique() < 2:
                continue
            m = make_model(name, **params).fit(df.loc[tr, features], y_tr)
            scores.append(roc_auc_score(y_va, m.predict_proba(df.loc[va, features])[:, 1]))
        rows.append({"model": name, **{k: str(v) for k, v in params.items()},
                     "folds": len(scores), "cv_roc_auc": np.mean(scores) if scores else np.nan})
    cv = pd.DataFrame(rows)
    best = int(cv.cv_roc_auc.fillna(-1).idxmax())  # first (simplest) candidate wins ties
    return candidates[best], cv


def baselines(train: pd.DataFrame, test: pd.DataFrame, feature_set: str) -> dict[str, tuple]:
    y = train[TARGET]
    dummy = DummyClassifier(strategy="most_frequent").fit(train[MODEL_A], y)
    out = {"baseline_majority": (dummy.predict(test[MODEL_A]), np.full(len(test), y.mean()))}
    if feature_set == "B":
        diff = test.inn1_pp_run_rate - test.inn2_pp_run_rate
        out["baseline_higher_pp_rate_wins"] = ((diff > 0).astype(int).values, diff.values)
    else:
        cut = train.inn1_pp_run_rate.median()
        out["baseline_pp_rate_above_train_median"] = (
            (test.inn1_pp_run_rate > cut).astype(int).values, (test.inn1_pp_run_rate - cut).values)
    return out


def importance(model, name: str, features: list[str]) -> pd.Series:
    est = model[-1]
    if name == "logistic_regression":
        return pd.Series(est.coef_[0], index=features)
    return pd.Series(est.feature_importances_, index=features)


def run(paths: Paths, n_test: int = 2, n_val: int = 1) -> dict[str, pd.DataFrame]:
    out = paths.export / "ml"
    figs = out / "figures"
    figs.mkdir(parents=True, exist_ok=True)
    charts.style()
    df = pd.read_csv(paths.export / "ml_features.csv")
    # No previous season (first season, new franchise): neutral prior, not a median of other teams.
    prev = ["bat_first_prev_season_win_pct", "chase_prev_season_win_pct"]
    df[prev] = df[prev].fillna(0.5)
    split = season_split(df.season, n_test, n_val)
    dev_seasons = split.train + split.val
    dev = df[df.season.isin(dev_seasons)].reset_index(drop=True)
    test = df[df.season.isin(split.test)].reset_index(drop=True)
    train_only = df[df.season.isin(split.train)]
    val = df[df.season.isin(split.val)]

    metric_rows, cv_frames, imp_rows, upsets = [], [], [], []
    for fs, features in FEATURE_SETS.items():
        for name, (pred, score) in baselines(dev, test, fs).items():
            metric_rows.append({"feature_set": fs, "model": name, "params": "", "split": "test",
                                **metrics(test[TARGET], pred, score)})
        for name in GRIDS:
            params, cv = tune(dev, features, name, dev_seasons)
            cv_frames.append(cv.assign(feature_set=fs))
            # Validation score: fit on train seasons, score on the validation season.
            m_val = make_model(name, **params).fit(train_only[features], train_only[TARGET])
            p_val = m_val.predict_proba(val[features])[:, 1]
            metric_rows.append({"feature_set": fs, "model": name, "params": str(params), "split": "validation",
                                **metrics(val[TARGET], (p_val >= .5).astype(int), p_val)})
            # Final model: fit on train + validation seasons, score the test seasons once.
            model = make_model(name, **params).fit(dev[features], dev[TARGET])
            proba = model.predict_proba(test[features])[:, 1]
            pred = (proba >= .5).astype(int)
            metric_rows.append({"feature_set": fs, "model": name, "params": str(params), "split": "test",
                                **metrics(test[TARGET], pred, proba)})
            imp = importance(model, name, features)
            imp_rows += [{"feature_set": fs, "model": name, "feature": f, "value": v} for f, v in imp.items()]
            conf = np.maximum(proba, 1 - proba)
            wrong = test[(pred != test[TARGET]) & (conf >= UPSET_CONFIDENCE)]
            upsets.append(wrong[["match_key", "source_match_id", "match_date", "season", TARGET]].assign(
                feature_set=fs, model=name, predicted_prob_bat_first_wins=proba[wrong.index].round(3)))
            if name == "decision_tree":
                fig, ax = charts.plt.subplots(figsize=(14, 7))
                plot_tree(model[-1], feature_names=features, class_names=["chase wins", "bat first wins"],
                          filled=False, impurity=False, proportion=True, rounded=True, fontsize=7, ax=ax)
                ax.set_title(f"Decision tree, Model {fs} ({params})")
                charts.save(fig, figs / f"decision_tree_model_{fs}.png")

    results = {
        "metrics": pd.DataFrame(metric_rows),
        "cv_results": pd.concat(cv_frames, ignore_index=True),
        "feature_importance": pd.DataFrame(imp_rows),
        "upsets": pd.concat(upsets, ignore_index=True),
        "split": pd.DataFrame([{"part": k, "seasons": " ".join(map(str, v)),
                                "matches": int(df.season.isin(v).sum())}
                               for k, v in vars(split).items()]),
    }
    for name, frame in results.items():
        frame.round(4).to_csv(out / f"{name}.csv", index=False)
    fig_comparison(results["metrics"], figs / "model_comparison.png")
    return results


def fig_comparison(m: pd.DataFrame, path: Path) -> None:
    t = m[m.split == "test"]
    models = list(dict.fromkeys(t.model))
    fig, axes = charts.plt.subplots(1, 2, figsize=(10, 0.45 * len(models) + 1.6), sharey=True)
    for ax, fs in zip(axes, ("A", "B")):
        g = t[t.feature_set == fs].set_index("model").reindex(models)
        y = np.arange(len(models))
        ax.barh(y, g.accuracy.fillna(0), color=charts.BLUE, height=0.65)
        for i, v in enumerate(g.accuracy):
            if pd.notna(v):
                ax.text(v, i, f" {v:.2f}", va="center", color=charts.TEXT_2, fontsize=8)
        ax.set_yticks(y, [m.replace("_", " ") for m in models])
        ax.set_xlim(0, 1.1)
        ax.grid(axis="y", visible=False)
        ax.set_title(f"Model {fs}: test accuracy")
    charts.save(fig, path)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--root", type=Path, default=PROJECT_ROOT)
    p.add_argument("--test-seasons", type=int, default=2)
    p.add_argument("--val-seasons", type=int, default=1)
    a = p.parse_args(argv)
    res = run(Paths(root=a.root), a.test_seasons, a.val_seasons)
    test = res["metrics"][res["metrics"].split == "test"]
    print(test[["feature_set", "model", "accuracy", "f1", "roc_auc"]].round(3).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
