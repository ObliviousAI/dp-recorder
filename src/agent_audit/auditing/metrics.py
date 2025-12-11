import numpy as np


def scalar_diff_count(a: float, b: float) -> float:
    if isinstance(a, np.ndarray):
        a = a.item()
    if isinstance(b, np.ndarray):
        b = b.item()
    out = abs(a - b)

    return out


def dist_l1(a: np.ndarray, b: np.ndarray) -> float:
    print(a.shape, b.shape)
    return np.linalg.norm(np.array(a) - np.array(b), ord=1)


def dist_l2(a: np.ndarray, b: np.ndarray) -> float:
    if len(a) == 0 and len(b) == 0:
        return 0
    return np.linalg.norm(np.array(a) - np.array(b), ord=2)


def dist_linf(a: np.ndarray, b: np.ndarray) -> float:
    return np.max(np.abs(np.array(a) - np.array(b)))
