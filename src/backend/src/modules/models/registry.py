# Standard Libraries
import logging
from typing import Type

# Third-party Libraries
from sklearn.svm import SVC
from sklearn.base import BaseEstimator
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.neighbors import KNeighborsClassifier
from sklearn.naive_bayes import GaussianNB
from sklearn.linear_model import LogisticRegression


# Logging
logger = logging.getLogger(__name__)


# Registry mapping model name to Scikit-Learn Estimator class
MODEL_CLASS_MAP: dict[str, Type[BaseEstimator]] = {
    "DecisionTreeClassifier": DecisionTreeClassifier,
    "RandomForestClassifier": RandomForestClassifier,
    "KNeighborsClassifier": KNeighborsClassifier,
    "SVC": SVC,
    "LogisticRegression": LogisticRegression,
    "GaussianNB": GaussianNB,
}