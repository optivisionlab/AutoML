import itertools
import time
from sklearn.model_selection import StratifiedKFold
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
import numpy as np


def grid_search(param_grid, model_func, data, targets, cv=5, scoring=None, metric_sort='accuracy',
                return_train_score=False):
    if scoring is None:
        scoring = {
            'accuracy': accuracy_score,
            'precision': lambda y_true, y_pred: precision_score(y_true, y_pred, average='macro', zero_division=0),
            'recall': lambda y_true, y_pred: recall_score(y_true, y_pred, average='macro', zero_division=0),
            'f1': lambda y_true, y_pred: f1_score(y_true, y_pred, average='macro', zero_division=0)
        }

    if metric_sort not in scoring:
        raise ValueError(f"metric_sort '{metric_sort}' not in scoring metrics")

    cv_results_ = {
        'params': [],
        'mean_test_score': [],
        'std_test_score': [],
        'rank_test_score': []
    }

    if return_train_score:
        cv_results_['mean_train_score'] = []
        cv_results_['std_train_score'] = []

    for metric in scoring.keys():
        cv_results_[f'mean_test_{metric}'] = []
        cv_results_[f'std_test_{metric}'] = []
        if return_train_score:
            cv_results_[f'mean_train_{metric}'] = []
            cv_results_[f'std_train_{metric}'] = []

    cv_results_['mean_fit_time'] = []
    cv_results_['std_fit_time'] = []
    cv_results_['mean_score_time'] = []
    cv_results_['std_score_time'] = []

    for i in range(cv):
        cv_results_[f'split{i}_test_score'] = []
        if return_train_score:
            cv_results_[f'split{i}_train_score'] = []

    best_score = float('-inf')
    best_params = None
    best_all_scores = None
    best_index = 0

    keys = param_grid.keys()
    combinations = list(itertools.product(*(param_grid[key] for key in keys)))

    for idx, combination in enumerate(combinations):
        params = dict(zip(keys, combination))
        cv_results_['params'].append(params)

        metric_scores = {metric: [] for metric in scoring.keys()}
        train_scores = {metric: [] for metric in scoring.keys()} if return_train_score else None
        fit_times = []
        score_times = []

        kf = StratifiedKFold(n_splits=cv, shuffle=True, random_state=42)

        for fold, (train_index, test_index) in enumerate(kf.split(data, targets)):
            train_data, test_data = data[train_index], data[test_index]
            train_targets, test_targets = targets[train_index], targets[test_index]

            model_params = params.copy()
            if model_func.__name__ == 'SVC':
                model_params['random_state'] = 42

            start_time = time.time()
            model = model_func(**model_params)
            model.fit(train_data, train_targets)
            fit_time = time.time() - start_time
            fit_times.append(fit_time)

            start_time = time.time()
            predictions = model.predict(test_data)
            score_time = time.time() - start_time
            score_times.append(score_time)

            for metric_name, metric_func in scoring.items():
                score = metric_func(test_targets, predictions)
                metric_scores[metric_name].append(score)
                cv_results_[f'split{fold}_test_score'].append(score)

                if return_train_score:
                    train_predictions = model.predict(train_data)
                    for metric_name, metric_func in scoring.items():
                        score = metric_func(train_targets, train_predictions)
                        train_scores[metric_name].append(score)

        average_score = {metric: np.mean(scores) for metric, scores in metric_scores.items()}
        std_score = {metric: np.std(scores) for metric, scores in metric_scores.items()}

        cv_results_['mean_test_score'].append(average_score[metric_sort])
        cv_results_['std_test_score'].append(std_score[metric_sort])

        for metric in scoring.keys():
            cv_results_[f'mean_test_{metric}'].append(average_score[metric])
            cv_results_[f'std_test_{metric}'].append(std_score[metric])

        if return_train_score:
            average_train_score = {metric: np.mean(scores) for metric, scores in train_scores.items()}
            std_train_score = {metric: np.std(scores) for metric, scores in train_scores.items()}

            cv_results_['mean_train_score'].append(average_train_score[metric_sort])
            cv_results_['std_train_score'].append(std_train_score[metric_sort])

            for metric in scoring.keys():
                cv_results_[f'mean_train_{metric}'].append(average_train_score[metric])
                cv_results_[f'std_train_{metric}'].append(std_train_score[metric])

        cv_results_['mean_fit_time'].append(np.mean(fit_times))
        cv_results_['std_fit_time'].append(np.std(fit_times))
        cv_results_['mean_score_time'].append(np.mean(score_times))
        cv_results_['std_score_time'].append(np.std(score_times))

        current_score = average_score[metric_sort]
        if current_score > best_score:
            best_score = current_score
            best_params = params
            best_all_scores = average_score
            best_index = idx

    test_scores = cv_results_['mean_test_score']
    ranks = np.argsort(np.argsort(-np.array(test_scores))) + 1
    cv_results_['rank_test_score'] = ranks.tolist()

    return best_params, best_score, best_all_scores, cv_results_

