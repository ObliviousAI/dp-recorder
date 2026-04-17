import copy
import contextvars
import inspect
import numpy as np
import random
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple
from functools import wraps
from enum import Enum
from copy import deepcopy
from tqdm.auto import tqdm

# Ensure dp_accounting is installed
try:
    from dp_accounting.pld import privacy_loss_distribution as pld
except ImportError:
    # Fallback for type hinting if library is missing during static analysis
    pld = Any

from dp_recorder.auditing.privacy_converter import PrivacyConverter
from dp_recorder.auditing.pld_from_epsilon_delta import pld_from_epsilon_delta_curve

try:
    pass

    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

try:
    import torch

    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False


def _get_rng_state() -> Dict[str, Any]:
    """
    Captures the state of all relevant Random Number Generators.
    """
    state = {}
    state["python_random"] = random.getstate()

    state["numpy_random"] = np.random.get_state()

    if TORCH_AVAILABLE:
        try:
            state["torch_cpu"] = torch.get_rng_state()
            if torch.cuda.is_available():
                state["torch_cuda"] = [
                    torch.cuda.get_rng_state(d)
                    for d in range(torch.cuda.device_count())
                ]
        except Exception:
            pass

    return state


def _set_rng_state(state: Dict[str, Any]) -> None:
    """
    Restores the RNG state from a captured snapshot.
    """
    if not state:
        return

    # 1. Python
    if "python_random" in state:
        random.setstate(state["python_random"])

    # 2. NumPy
    if "numpy_random" in state:
        np.random.set_state(state["numpy_random"])

    # 3. PyTorch
    if TORCH_AVAILABLE:
        if "torch_cpu" in state:
            torch.set_rng_state(state["torch_cpu"])
        if "torch_cuda" in state and torch.cuda.is_available():
            for i, s in enumerate(state["torch_cuda"]):
                try:
                    torch.cuda.set_rng_state(s, i)
                except Exception:
                    pass


_active_auditor = contextvars.ContextVar("active_auditor", default=None)


class AuditMode(Enum):
    RECORD = "record"
    REPLAY = "replay"


def _snapshot(obj: Any) -> Any:
    """Deep copy to ensure log immutability."""
    if isinstance(obj, np.ndarray):
        return obj.copy()
    if isinstance(obj, (int, float, str, bool, type(None))):
        return obj
    if isinstance(obj, (list, tuple)):
        return type(obj)(_snapshot(x) for x in obj)
    if isinstance(obj, dict):
        return {k: _snapshot(v) for k, v in obj.items()}
    try:
        return deepcopy(obj)
    except BaseException:
        return obj


def _are_equal(a, b) -> bool:
    """Robust equality check for scalar, objects, and arrays."""
    if isinstance(a, np.ndarray) or isinstance(b, np.ndarray):
        return np.array_equal(a, b)
    return a == b


@dataclass
class LogEntry:
    call_id: int
    kind: str

    # -- For Mechanisms --
    func: Optional[Callable] = None
    rng_state_pre: Optional[Dict[str, Any]] = None

    inputs_d: Optional[Dict[str, Any]] = None
    inputs_dp: Optional[Dict[str, Any]] = None
    params: Optional[Dict[str, Any]] = None

    # -- For Equality --
    value_d: Any = None
    label: str = ""

    # -- Common --
    output_d: Any = None

    # -- Metadata --
    sensitivity_val: Optional[float] = None
    metric_fn: Optional[Callable] = None
    dist_audit_auc: Optional[float] = None

    # -- PLD (Trusted) --
    # If an accountant was provided, we store the analytical PLD here
    pld_trusted: Optional[Any] = None

    # -- PLD (Inferred via Audit) --
    tradeoff_curve: Optional[Tuple[np.ndarray, np.ndarray]] = None
    auc: Optional[float] = None
    privacy_profile: Optional[Tuple[np.ndarray, np.ndarray]] = None
    pld_rec: Optional[Any] = None
    ks_rec: Optional[np.ndarray] = None
    deltas_rec: Optional[np.ndarray] = None


# (Assuming other required imports are available in your namespace: LogEntry, AuditMode, etc.)  # noqa: E501
SKLEARN_AVAILABLE = True


class Auditor:
    def __init__(self):
        self.mode = AuditMode.RECORD
        self.log: List[LogEntry] = []
        self._cursor = 0
        self._token = None
        self.overall_pld = None

    def __enter__(self):
        self._token = _active_auditor.set(self)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        _active_auditor.reset(self._token)

    def set_replay(self):
        self.mode = AuditMode.REPLAY
        self._cursor = 0

    def intercept_mechanism(
        self,
        kind: str,
        func: Callable,
        input_arg: str,
        sensitivity_arg: str,
        metric_fn: Callable,
        accountant: Optional[Callable],
        *args,
        **kwargs,
    ):
        input_val, params = _split_input_and_params(func, args, kwargs, input_arg)

        sens_val = None
        if sensitivity_arg in params:
            sens_val = params[sensitivity_arg]
        else:
            for key, val in params.items():
                if isinstance(val, dict) and sensitivity_arg in val:
                    sens_val = val[sensitivity_arg]
                    break

        if self.mode == AuditMode.RECORD:
            rng = _get_rng_state()
            output = func(*args, **kwargs)

            trusted_pld = None
            if accountant is not None:
                try:
                    trusted_pld = accountant(**params)
                except Exception as e:
                    print(
                        f"[Auditor Warning] Failed to generate trusted PLD for {kind}: {e}"  # noqa: E501
                    )

            self.log.append(
                LogEntry(
                    call_id=len(self.log),
                    kind=kind,
                    func=func,
                    rng_state_pre=rng,
                    inputs_d={input_arg: _snapshot(input_val)},
                    params=_snapshot(params),
                    output_d=_snapshot(output),
                    sensitivity_val=float(sens_val) if sens_val is not None else 0.0,
                    metric_fn=metric_fn,
                    pld_trusted=trusted_pld,
                )
            )
            return output

        elif self.mode == AuditMode.REPLAY:
            if self._cursor >= len(self.log):
                raise RuntimeError("Replay overrun")
            entry = self.log[self._cursor]

            if entry.kind != kind:
                raise AssertionError(
                    f"Divergence @ {self._cursor}: Expected {entry.kind}, got {kind}"
                )

            entry.inputs_dp = {input_arg: _snapshot(input_val)}

            if str(entry.params) != str(params):
                raise AssertionError(
                    f"Params mismatch @ {self._cursor} ({kind}).\n"
                    f"Record: {entry.params}\n"
                    f"Replay: {params}"
                )

            _set_rng_state(entry.rng_state_pre)
            self._cursor += 1
            return entry.output_d

    def check_equality(self, value: Any, label: str) -> Any:
        if self.mode == AuditMode.RECORD:
            self.log.append(
                LogEntry(
                    call_id=len(self.log),
                    kind="EQ",
                    value_d=_snapshot(value),
                    label=label,
                    output_d=_snapshot(value),
                )
            )
            return value

        elif self.mode == AuditMode.REPLAY:
            if self._cursor >= len(self.log):
                raise RuntimeError("Replay overrun")
            entry = self.log[self._cursor]

            if entry.kind != "EQ":
                raise AssertionError(
                    f"Divergence @ {self._cursor}: Expected Equality Check, got {entry.kind}"  # noqa: E501
                )

            if not _are_equal(entry.value_d, value):
                raise AssertionError(
                    f"Equality Failure @ '{label}' (Call {self._cursor})\n"
                    f"   Record (D) : {entry.value_d}\n"
                    f"   Replay (D'): {value}"
                )

            self._cursor += 1
            return entry.output_d

    def validate_records(self):
        failures = []
        for i, entry in enumerate(self.log):
            if entry.kind == "EQ" or getattr(entry, "inputs_dp", None) is None:
                continue

            val_d = list(entry.inputs_d.values())[0]
            val_dp = list(entry.inputs_dp.values())[0]

            # Only convert to numpy arrays if it's not a dictionary
            # Standard metrics  will handle conversion
            # internally if needed, but metrics for non-scalar types
            # (like JAM's dict scores) need the raw dict.
            if not isinstance(val_d, dict):
                if not isinstance(val_d, np.ndarray):
                    val_d = np.array(val_d)
                if val_d.ndim == 0:
                    val_d = val_d.reshape(1)

            if not isinstance(val_dp, dict):
                if not isinstance(val_dp, np.ndarray):
                    val_dp = np.array(val_dp)
                if val_dp.ndim == 0:
                    val_dp = val_dp.reshape(1)

            dist = entry.metric_fn(val_d, val_dp)
            limit = entry.sensitivity_val + 1e-9

            if dist > limit:
                failures.append(
                    f"Call {i} ({entry.kind}): Dist {dist:.4f} > Sens {entry.sensitivity_val}"  # noqa: E501
                )

        if failures:
            raise AssertionError("\n".join(failures))

    def run_distributional_audit(
        self,
        n_samples: int = 1000,
        epsilon_range: tuple = (-25, 25),
        alpha: float = 1e-5,
        test_size: float = 0.5,
    ):
        if not SKLEARN_AVAILABLE:
            print("[Error] sklearn is required for distributional audit.")
            return

        try:
            from scipy.stats import beta
        except ImportError:
            print("[Error] scipy is required for rigorous distributional audit.")
            return

        entries_processed = 0

        for entry in tqdm(self.log, desc="Sampling", leave=False):
            if entry.kind == "EQ":
                continue
            if entry.pld_trusted is not None:
                entries_processed += 1
                continue

            if getattr(entry, "inputs_dp", None) is None:
                print(
                    f"[Warning] Skipping Call {entry.call_id}: No neighbor input (inputs_dp)."  # noqa: E501
                )
                continue

            entries_processed += 1

            def _flatten_sample(sample):
                if isinstance(sample, tuple) and len(sample) == 2:
                    loss_arr = np.array([sample[0]], dtype=float).ravel()
                    grad_arr = np.array(sample[1], dtype=float).ravel()
                    return np.concatenate([loss_arr, grad_arr])
                arr = np.array(sample, dtype=float)
                return arr.reshape(1) if arr.ndim == 0 else arr.ravel()

            _set_rng_state(entry.rng_state_pre)

            # --- 1. PREVENT RANDOM WALK DRIFTS (DEEPCOPY) ---
            # If backend functions perform `value += noise` in-place without copies, loop iterations  # noqa: E501
            # drift mathematically further apart, sending Epsilon to Infinity.
            raw_samples_d = []
            for _ in range(n_samples // 2):
                kd = copy.deepcopy({**entry.params, **entry.inputs_d})
                raw_samples_d.append(entry.func(**kd))

            raw_samples_dp = []
            for _ in range(n_samples // 2):
                kdp = copy.deepcopy({**entry.params, **entry.inputs_dp})
                raw_samples_dp.append(entry.func(**kdp))

            samples_d = [_flatten_sample(s) for s in raw_samples_d]
            samples_dp = [_flatten_sample(s) for s in raw_samples_dp]

            X = np.vstack(samples_d + samples_dp)
            y = np.array([0] * (n_samples // 2) + [1] * (n_samples // 2))

            if not np.isfinite(X).all():
                print("CRITICAL: The mechanism returned NaNs or Infs!")
                continue

            from sklearn.linear_model import LogisticRegression
            from sklearn.preprocessing import StandardScaler
            from sklearn.pipeline import make_pipeline
            from sklearn.metrics import roc_curve, roc_auc_score
            from sklearn.model_selection import train_test_split

            if n_samples < 10:
                X_train, X_test, y_train, y_test = X, X, y, y
            else:
                X_train, X_test, y_train, y_test = train_test_split(
                    X, y, test_size=test_size, stratify=y, random_state=42
                )

            clf = make_pipeline(StandardScaler(), LogisticRegression())
            clf.fit(X_train, y_train)

            # Phase 1: Train evaluation and optimal threshold discovery
            logp_train = clf.predict_log_proba(X_train)
            scores_train = logp_train[:, 1] - logp_train[:, 0]

            scores_d_train = scores_train[y_train == 0]
            scores_dp_train = scores_train[y_train == 1]

            best_j = -np.inf
            best_z = -np.inf

            # Use Youden's J statistic (1 - FPR - FNR) to pick the threshold
            # that separates distributions best without allowing extreme
            # bound-overfitting
            for z in np.unique(scores_train):
                fpr_t = np.mean(scores_d_train >= z)
                fnr_t = np.mean(scores_dp_train < z)
                j_stat = 1.0 - (fpr_t + fnr_t)

                if j_stat > best_j:
                    best_j = j_stat
                    best_z = z

            # Phase 2: Rigorous Clopper-Pearson Bounds on the Sequestered Test set
            logp_test = clf.predict_log_proba(X_test)
            scores_test = logp_test[:, 1] - logp_test[:, 0]

            n_neg_test = np.sum(y_test == 0)
            n_pos_test = np.sum(y_test == 1)

            fp_test = np.sum((scores_test >= best_z) & (y_test == 0))
            fn_test = np.sum((scores_test < best_z) & (y_test == 1))

            def _cp_upper(k_success, n_total, alpha_tail_val):
                if k_success >= n_total:
                    return 1.0
                return float(
                    beta.ppf(1 - alpha_tail_val, k_success + 1, n_total - k_success)
                )

            alpha_tail = alpha / 2.0
            fpr_U_test = _cp_upper(fp_test, n_neg_test, alpha_tail)
            fnr_U_test = _cp_upper(fn_test, n_pos_test, alpha_tail)

            if fpr_U_test + fnr_U_test >= 1.0:
                pessimistic_tradeoff = [(0.0, 1.0), (1.0, 0.0)]
                eps_lb = 0.0
            else:
                pessimistic_tradeoff = [
                    (0.0, 1.0),
                    (fpr_U_test, fnr_U_test),
                    (1.0, 0.0),
                ]

                e1 = (
                    np.inf if fnr_U_test == 0 else np.log((1 - fpr_U_test) / fnr_U_test)
                )
                e2 = (
                    np.inf if fpr_U_test == 0 else np.log((1 - fnr_U_test) / fpr_U_test)
                )
                eps_lb = float(max(e1, e2))

            pessimistic_tradeoff.sort(key=lambda x: x[0])

            auc = roc_auc_score(y_test, scores_test)
            fpr_full, tpr_full, _ = roc_curve(y_test, scores_test)

            entry.tradeoff_curve_empirical = list(zip(fpr_full, 1.0 - tpr_full))
            entry.tradeoff_curve = pessimistic_tradeoff
            entry.auc = float(auc)
            entry.empirical_epsilon_lb = eps_lb

            # Build PLD securely preventing piecewise step hallucination
            converter = PrivacyConverter(pessimistic_tradeoff)
            epsilons = np.linspace(epsilon_range[0], epsilon_range[1], 1000)
            deltas = [converter.get_delta_from_epsilon(float(eps)) for eps in epsilons]

            entry.privacy_profile = (epsilons, np.asarray(deltas))

            try:
                pld_rec, ks_rec, deltas_rec = pld_from_epsilon_delta_curve(
                    epsilons, deltas
                )
                entry.pld_rec = pld_rec
                entry.ks_rec = ks_rec
                entry.deltas_rec = deltas_rec
            except Exception:
                entry.pld_rec = None

        if entries_processed == 0:
            print(
                "[Audit Failed] No valid mechanism calls found. Ensure you have run the Replay phase."  # noqa: E501
            )

    def compute_overall_pld(self) -> Any:
        curr_pld = None
        for entry in self.log:
            entry_pld = (
                entry.pld_trusted
                if entry.pld_trusted is not None
                else getattr(entry, "pld_rec", None)
            )

            if entry_pld is not None:
                if curr_pld is None:
                    curr_pld = entry_pld
                else:
                    curr_pld = curr_pld.compose(entry_pld)

        self.overall_pld = curr_pld
        return curr_pld

    def get_overall_current_guarantee(self, delta: float) -> float:
        if self.overall_pld is None:
            raise ValueError(
                "Overall PLD not computed yet. Call compute_overall_pld first."
            )
        return self.overall_pld.get_epsilon_for_delta(delta)


def audit_spec(
    kind: str,
    input_arg: str,
    sensitivity_arg: str,
    metric_fn: Callable,
    accountant: Optional[Callable] = None,
):
    """
    Decorator for DP Mechanisms.

    :param accountant: Optional callable. If provided, the mechanism is considered TRUSTED.  # noqa: E501
                       The auditor will use this accountant (passed with mechanism params)  # noqa: E501
                       to compute the privacy loss analytically, skipping the inference step.  # noqa: E501
                       If None, the auditor will infer the privacy loss via distributional audit.  # noqa: E501
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            auditor = _active_auditor.get()
            if auditor:
                return auditor.intercept_mechanism(
                    kind,
                    func,
                    input_arg,
                    sensitivity_arg,
                    metric_fn,
                    accountant,
                    *args,
                    **kwargs,
                )
            return func(*args, **kwargs)

        return wrapper

    return decorator


def _split_input_and_params(func, args, kwargs, input_arg_name):
    """
    Robustly separates the sensitive input data from the configuration parameters.
    Handles explicit arguments and inputs nested inside **kwargs.
    """
    sig = inspect.signature(func)
    bound = sig.bind(*args, **kwargs)
    bound.apply_defaults()
    all_args = bound.arguments  # This maps arg_names -> values

    # 1. Try finding the input in the top-level arguments
    if input_arg_name in all_args:
        input_val = all_args[input_arg_name]
        # Create params by excluding the input_arg
        params = {k: v for k, v in all_args.items() if k != input_arg_name}
        return input_val, params

    # 2. If not found, check if it's hidden inside a **kwargs dictionary
    # Find the name of the **kwargs parameter in the function definition
    var_kw_name = None
    for name, param in sig.parameters.items():
        if param.kind == inspect.Parameter.VAR_KEYWORD:
            var_kw_name = name
            break

    # If the function has **kwargs and it was used...
    if var_kw_name and var_kw_name in all_args:
        kw_dict = all_args[var_kw_name]  # The dictionary passed to **kwargs

        if input_arg_name in kw_dict:
            input_val = kw_dict[input_arg_name]

            # Deep copy params so we can mutate the kwargs part without affecting
            # original
            params = {k: _snapshot(v) for k, v in all_args.items()}

            # Remove the sensitive input from the nested kwargs in params
            # This ensures 'params' only contains configuration, not data.
            if var_kw_name in params and isinstance(params[var_kw_name], dict):
                # We must check existence again on the copy to be safe
                if input_arg_name in params[var_kw_name]:
                    del params[var_kw_name][input_arg_name]

            return input_val, params

    # 3. Failure: Configuration Error
    raise ValueError(
        f"Auditor Error: The input argument '{input_arg_name}' defined in @audit_spec "
        f"was not found in the call to '{func.__name__}'.\n"
        f"Available args: {list(all_args.keys())}"
    )


def ensure_equality(*args, **kwargs) -> Any:
    if len(kwargs) == 0:
        raise ValueError("ensure_equality: No value provided.")
    if len(args) > 0:
        raise ValueError("ensure_equality: Do not provide positional arguments.")

    for label, value in kwargs.items():
        auditor = _active_auditor.get()
        if auditor:
            return auditor.check_equality(value=value, label=label)

    return value
