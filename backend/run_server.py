"""Entry point for PyInstaller-frozen backend."""
import sys
import os

# Ensure stdout/stderr are unbuffered in frozen mode
sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', buffering=1)
sys.stderr = os.fdopen(sys.stderr.fileno(), 'w', buffering=1)

print("Starting ASCI-Desktop backend...", flush=True)


def main():
    port = 8765
    for i, arg in enumerate(sys.argv[1:], 1):
        if arg == "--port" and i < len(sys.argv) - 1:
            port = int(sys.argv[i + 1])

    print(f"Importing uvicorn...", flush=True)
    import uvicorn
    print(f"Importing app...", flush=True)
    from app.main import app
    print(f"Starting server on port {port}...", flush=True)
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    main()
