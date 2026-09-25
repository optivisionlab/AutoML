# Standard Libraries
import logging
from typing import Type

# Third-party Libraries
from xgboost import XGBRegressor, XGBClassifier
from sklearn.base import BaseEstimator
from sklearn.svm import SVC, SVR
from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor
from sklearn.ensemble import (
    RandomForestClassifier,
    RandomForestRegressor,
    GradientBoostingRegressor,
    GradientBoostingClassifier,
)
from sklearn.neighbors import KNeighborsClassifier, KNeighborsRegressor
from sklearn.naive_bayes import GaussianNB
from sklearn.linear_model import LogisticRegression, LinearRegression, Ridge, Lasso


# Logging
logger = logging.getLogger(__name__)


MODEL_CLASS_MAP: dict[str, Type[BaseEstimator]] = {
    # Classification
    "DecisionTreeClassifier": DecisionTreeClassifier,
    "RandomForestClassifier": RandomForestClassifier,
    "GradientBoostingClassifier": GradientBoostingClassifier,
    "KNeighborsClassifier": KNeighborsClassifier,
    "SVC": SVC,
    "LogisticRegression": LogisticRegression,
    "GaussianNB": GaussianNB,
    "XGBClassifier": XGBClassifier,

    # Regression
    "LinearRegression": LinearRegression,
    "DecisionTreeRegressor": DecisionTreeRegressor,
    "RandomForestRegressor": RandomForestRegressor,
    "GradientBoostingRegressor": GradientBoostingRegressor,
    "Ridge": Ridge,
    "Lasso": Lasso,
    "SVR": SVR,
    "KNeighborsRegressor": KNeighborsRegressor,
    "XGBRegressor": XGBRegressor,
}
