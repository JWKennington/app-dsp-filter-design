# Digital Signal Processing Explorer

[![Launch App](https://img.shields.io/badge/Launch-App-success?style=for-the-badge&logo=rocket)](https://dsp-explorer.onrender.com)
An interactive tool for exploring Analog and Digital filters, poles, zeros, and stability.

## For Students
**[Click here to launch the app](https://dsp-explorer.onrender.com)**. No account or setup required.

## For Developers
If you want to host your own copy or modify the code:
[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/JWKennington/app-dsp-filter-design)

---

## Key Features

### 🎛️ Interactive Design
-   **Drag-and-Drop**: Move Poles and Zeros on the complex plane and watch the Bode and Impulse plots update instantly.
-   **Real-Time Feedback**: Immediate visualization of Magnitude, Phase, and Time-Domain response.

### 📈 Advanced Analysis
-   **Stability Visualization**: Toggle between **Causal** (standard) and **Anti-Causal** (stable reconstruction from unstable poles) modes.
-   **Two-Sided Impulse Response**:
    -   **Digital**: Moving poles outside $|z|=1$ generates left-sided sequences ($n < 0$).
    -   **Analog**: Moving poles to the Right Half Plane generates negative-time decay ($t < 0$).
-   **Bode Plot**: Logarithmic frequency application for Analog, Linear for Digital (normalized frequency).

### 🎨 Professional Branding
-   **LSC Branding**: Features a professional scientific color scheme (LSC Blue) and branding.
-   **Publication Ready**: Clean, compact layout suitable for demonstrations and teaching.

---

## Local Development

This project uses [uv](https://github.com/astral-sh/uv) for fast, reliable package management.

### Prerequisites
-   Python 3.9+
-   `uv` installed (`curl -LsSf https://astral.sh/uv/install.sh | sh`)

### Running the App

1.  **Clone the repository**:
    ```bash
    git clone https://github.com/JWKennington/app-dsp-filter-design.git
    cd app-dsp-filter-design
    ```

2.  **Sync dependencies**:
    ```bash
    uv sync
    ```

3.  **Run the application**:
    ```bash
    uv run dsp-fd
    ```
    Open [http://127.0.0.1:8050](http://127.0.0.1:8050) in your browser.

---

## Deployment

### Docker
A `Dockerfile` is included for containerized deployment.

```bash
docker build -t dsp-fd .
docker run -p 8050:8050 dsp-fd
```

### Render
This repository is configured for immediate deployment on Render.
1.  Click the **Deploy to Render** button above.
2.  Connect your GitHub account.
3.  Render will automatically build using the `Dockerfile` and deploy the service.

---

## License
MIT License. See `LICENSE` for details.

© 2026 James Kennington.
