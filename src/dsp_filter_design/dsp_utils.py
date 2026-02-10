import numpy as np
from scipy import signal


def sanitize_json(obj):
    """Recursively convert numpy types to standard python types for JSON serialization."""
    if isinstance(obj, dict):
        return {k: sanitize_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [sanitize_json(x) for x in obj]
    if isinstance(obj, np.ndarray):
        return sanitize_json(obj.tolist())
    if isinstance(obj, complex):
        return float(obj.real) if abs(obj.imag) < 1e-14 else [obj.real, obj.imag]
    if isinstance(obj, (np.generic)):
        return float(obj)
    return obj


def to_complex_array(data_list):
    """Convert list of [real, imag] lists back to numpy complex array."""
    if not data_list:
        return np.array([])
    return np.array([complex(x[0], x[1]) for x in data_list])


def design_filter(family, ftype, order, domain, c1, c2):
    """Wrapper for scipy.signal filter design functions."""
    analog = (domain == "analog")

    # Frequency constraint logic
    if ftype in ["bandpass", "bandstop"]:
        Wn = [min(c1, c2), max(c1, c2)]
    else:
        Wn = c1

    # Safety clamps (Using np.clip/maximum handles both scalar and list inputs automatically)
    if not analog:
        # Digital freq must be 0 < Wn < 1 (Nyquist)
        Wn = np.clip(Wn, 1e-6, 0.999)
    else:
        # Analog freq must be > 0
        Wn = np.maximum(Wn, 1e-6)

    try:
        if family == "Butterworth":
            z, p, k = signal.butter(order, Wn, btype=ftype, analog=analog, output='zpk')
        elif family == "Chebyshev I":
            z, p, k = signal.cheby1(order, 1, Wn, btype=ftype, analog=analog,
                                    output='zpk')
        elif family == "Chebyshev II":
            z, p, k = signal.cheby2(order, 40, Wn, btype=ftype, analog=analog,
                                    output='zpk')
        elif family == "Elliptic":
            z, p, k = signal.ellip(order, 1, 40, Wn, btype=ftype, analog=analog,
                                   output='zpk')
        elif family == "Bessel":
            z, p, k = signal.bessel(order, Wn, btype=ftype, analog=analog, output='zpk')
        else:
            return [], [], 1.0
    except Exception as e:
        print(f"Filter Design Error: {e}")
        return [], [], 1.0

    return z, p, k


def compute_responses(zeros, poles, gain, domain):
    """Computes Frequency (Bode) and Impulse responses."""
    analog = (domain == "analog")

    # 1. Frequency Response
    if analog:
        all_p = np.concatenate([np.abs(zeros), np.abs(poles)])
        if len(all_p) > 0:
            fmax = max(all_p) * 100
            fmin = min(all_p[all_p > 0]) / 10 if any(all_p > 0) else 0.1
        else:
            fmin, fmax = 0.1, 100

        # logspace generation
        w = np.logspace(np.log10(fmin), np.log10(fmax), 500)
        w, h = signal.freqs_zpk(zeros, poles, gain, worN=w)
    else:
        w, h = signal.freqz_zpk(zeros, poles, gain, worN=500)

    mag_db = 20 * np.log10(np.abs(h) + 1e-15)
    phase_deg = np.rad2deg(np.unwrap(np.angle(h)))

    # 2. Impulse Response
    if analog:
        # Check stability for auto-ranging time vector
        real_poles = poles.real
        if len(real_poles) > 0 and np.max(real_poles) < 0:
            # Stable: plot until decay (5 time constants of the slowest pole)
            min_decay = np.min(np.abs(real_poles))
            t_max = 5.0 / min_decay if min_decay > 0 else 10.0
        else:
            t_max = 10.0

        sys = signal.lti(zeros, poles, gain)
        # Use simple linspace for T to avoid issues with signal.impulse auto-ranging
        T_vals = np.linspace(0, t_max, 500)
        t, y = signal.impulse(sys, T=T_vals)

        # FIX: Ensure output is Real (removes 1e-12j noise and handles complex filters)
        y = np.real(y)

    else:
        dim = 50
        u = np.zeros(dim);
        u[0] = 1
        b, a = signal.zpk2tf(zeros, poles, gain)
        y = signal.lfilter(b, a, u)

        # FIX: Ensure output is Real
        y = np.real(y)
        t = np.arange(dim)

    return w, mag_db, phase_deg, t, y
