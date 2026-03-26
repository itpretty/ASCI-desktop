use std::process::{Child, Command};
use std::sync::Mutex;
use tauri::Manager;

struct BackendProcess(Mutex<Option<Child>>);

#[tauri::command]
async fn check_backend() -> Result<String, String> {
    let client = reqwest::Client::new();
    match client.get("http://127.0.0.1:8765/health").send().await {
        Ok(resp) => {
            if resp.status().is_success() {
                Ok("Backend is running".to_string())
            } else {
                Err(format!("Backend returned status: {}", resp.status()))
            }
        }
        Err(e) => Err(format!("Backend not reachable: {}", e)),
    }
}

fn find_backend_dir() -> Option<std::path::PathBuf> {
    let exe = std::env::current_exe().ok()?;
    let exe_dir = exe.parent()?;

    // Search upward from exe dir for a sibling "backend/app" directory
    let mut dir = exe_dir.to_path_buf();
    for _ in 0..5 {
        let candidate = dir.join("backend");
        if candidate.join("app").exists() {
            return Some(candidate.canonicalize().ok()?);
        }
        if !dir.pop() {
            break;
        }
    }

    // Fallback: working directory
    let candidate = std::env::current_dir().ok()?.join("backend");
    if candidate.join("app").exists() {
        return Some(candidate.canonicalize().ok()?);
    }

    None
}

fn spawn_backend() -> Option<Child> {
    let backend_dir = find_backend_dir();
    if backend_dir.is_none() {
        eprintln!("Backend directory not found");
        return None;
    }
    let backend_dir = backend_dir.unwrap();
    eprintln!("Found backend at: {:?}", backend_dir);
    let venv_python = backend_dir.join(".venv/bin/python");

    let python = if venv_python.exists() {
        venv_python
    } else {
        // Fallback to system python
        std::path::PathBuf::from("python3")
    };

    let child = Command::new(&python)
        .args([
            "-m", "uvicorn",
            "app.main:app",
            "--host", "127.0.0.1",
            "--port", "8765",
            "--log-level", "warning",
        ])
        .current_dir(&backend_dir)
        .spawn()
        .ok()?;

    Some(child)
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_fs::init())
        .setup(|app| {
            // Launch Python backend
            let child = spawn_backend();
            if child.is_none() {
                eprintln!("Warning: Failed to start Python backend. Start it manually.");
            }
            app.manage(BackendProcess(Mutex::new(child)));
            Ok(())
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::Destroyed = event {
                if let Some(state) = window.try_state::<BackendProcess>() {
                    if let Ok(mut guard) = state.0.lock() {
                        if let Some(mut child) = guard.take() {
                            let _ = child.kill();
                            let _ = child.wait();
                        }
                    }
                }
            }
        })
        .invoke_handler(tauri::generate_handler![check_backend])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
