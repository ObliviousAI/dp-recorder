import numpy as np
from scipy.optimize import minimize_scalar
from scipy.interpolate import interp1d

class PrivacyConverter:
    """
    Implements the conversion from an f-DP trade-off function (f)
    to the (epsilon, delta) privacy profile based on Proposition 2.12.
    
    The conversion is:
    delta(epsilon) = 1 + f*(-exp(epsilon))
                   = 1 + sup_{x in [0,1]} (-exp(epsilon)*x - f(x))
                   = 1 - inf_{x in [0,1]} (exp(epsilon)*x + f(x))
    """

    def __init__(self, alpha_f_alpha_pairs, interpolation_kind='linear'):
        """
        Initializes the converter with discrete pairs of (alpha, f(alpha)).

        Args:
            alpha_f_alpha_pairs (list): A list of (alpha, f(alpha)) tuples.
                These points sample the f-DP trade-off function.
                alpha is the Type I error, f(alpha) is the Type II error.
                The points should ideally span the [0, 1] domain.
            interpolation_kind (str): The kind of interpolation to use
                (e.g., 'linear', 'cubic'). 'linear' is often robust.
        """
        # Sort pairs by alpha to ensure correct interpolation
        sorted_pairs = sorted(alpha_f_alpha_pairs, key=lambda p: p[0])
        alphas = np.array([p[0] for p in sorted_pairs])
        f_values = np.array([p[1] for p in sorted_pairs])

        # Warn if the data doesn't cover the full [0, 1] domain
        if not (np.isclose(alphas[0], 0.0) and np.isclose(alphas[-1], 1.0)):
            print(f"Warning: Provided data does not span the full [0, 1] domain. "
                  f"Domain given: [{alphas[0]}, {alphas[-1]}]. "
                  "The conversion will be based on the provided range.")

        # Create the interpolated function f(x)
        # We set f(x) = infinity outside the [0, 1] range,
        # as specified in the text.
        self.f = interp1d(alphas, f_values, kind=interpolation_kind,
                          bounds_error=False, fill_value=np.inf)
        
        # The optimization domain is [0, 1]
        self.domain = (0.0, 1.0)

    def get_delta_from_epsilon(self, epsilon):
        # Define the objective function to minimize
        objective = lambda x: np.exp(epsilon) * x + self.f(x)
        
        # Find the infimum (minimum) over the domain [0, 1]
        opt_result = minimize_scalar(objective, bounds=self.domain, method='bounded')
        
        if not opt_result.success:
            raise RuntimeError(f"Optimization failed for epsilon = {epsilon}")
            
        infimum = opt_result.fun
        
        # Clamp delta to the valid [0, 1] range
        return max(0.0, min(1.0, 1.0 - infimum))