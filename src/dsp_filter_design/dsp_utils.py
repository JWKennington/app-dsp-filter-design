import numpy as np
from scipy import signal


def sanitize_json(obj):
    """Recursively convert numpy types to standard python types for JSON
    serialization."""
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

    # Safety clamps
    if not analog:
        Wn = np.clip(Wn, 1e-6, 0.999)
    else:
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
    """Computes Frequency (Bode) and Impulse responses.
       For Impulse Response, uses Partial Fraction Expansion to support
       stable non-causal responses (two-sided).
    """
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

    # 2. Impulse Response (Two-Sided / Stable)
    t, y = None, None
    b, a = signal.zpk2tf(zeros, poles, gain)

    if analog:
        # Check properness: if Zeros > Poles, impulse is undefined (Dirac deltas)
        if len(zeros) > len(poles):
            return w, mag_db, phase_deg, None, None
        
        try:
            r, p, k = signal.residue(b, a)
        except Exception:
            return w, mag_db, phase_deg, None, None

        # Determine time range
        real_p = np.real(p)
        if len(real_p) > 0:
             # Use the slowest decay (closest to axis) for range
             min_decay = np.min(np.abs(real_p))
             min_decay = max(min_decay, 0.1)
             t_max = 5.0 / min_decay
        else:
             t_max = 10.0
        
        # Create symmetric time vector to show both sides
        t = np.linspace(-t_max, t_max, 1000)
        y = np.zeros_like(t, dtype=np.complex128)

        # 1. Add Residue terms
        for ri, pi in zip(r, p):
            if np.real(pi) > 0:
                # Anticausal (Right Half Plane): -r * e^(pt) * u(-t)
                mask = t < 0
                y[mask] -= ri * np.exp(pi * t[mask])
            else:
                # Causal (Left Half Plane): r * e^(pt) * u(t)
                mask = t >= 0
                y[mask] += ri * np.exp(pi * t[mask])
        
        # Add direct term k if present (though usually delta function)
        # For visualization, we skip drawing the delta arrow for now.
        y = np.real(y)

    else:
        # Digital
        try:
            r, p, k = signal.residuez(b, a)
        except Exception:
             return w, mag_db, phase_deg, None, None
        
        # Digital Time Vector: -50 to +50
        dim = 50
        t = np.arange(-dim, dim + 1)
        y = np.zeros_like(t, dtype=np.complex128)

        # 1. Direct terms (k)
        for i, val in enumerate(k):
            # delta at n=i. t vector starts at -dim.
            # Index in 'y' corresponding to n=i is i + dim
            idx = i + dim
            if 0 <= idx < len(y):
                y[idx] += val
        
        # 2. Residue terms
        for ri, pi in zip(r, p):
            if abs(pi) > 1.0000001: 
                # Anticausal: -r * p^n * u[-n-1]
                mask = t <= -1
                y[mask] -= ri * (pi ** t[mask])
            else:
                # Causal: r * p^n * u[n]
                mask = t >= 0
                y[mask] += ri * (pi ** t[mask])

        y = np.real(y)

    return w, mag_db, phase_deg, t, y
