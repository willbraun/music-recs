use std::{
    net::{SocketAddr, TcpListener, TcpStream},
    os::unix::process::CommandExt,
    process::{Child, Command},
    sync::Mutex,
    thread,
    time::{Duration, Instant},
};

use tauri::{
    webview::NewWindowResponse, AppHandle, Manager, RunEvent, WebviewUrl, WebviewWindow,
    WebviewWindowBuilder,
};
use tauri_plugin_opener::OpenerExt;

const MAIN_WINDOW: &str = "main";
// The first launch applies migrations and imports the MLX stack, so a cold start can take a while.
const STARTUP_TIMEOUT: Duration = Duration::from_secs(120);
const STARTUP_POLL: Duration = Duration::from_millis(200);

// Holds the packaged API process so it can be stopped on exit.
struct Sidecar(Mutex<Option<Child>>);

fn pick_free_port() -> std::io::Result<u16> {
    Ok(TcpListener::bind("127.0.0.1:0")?.local_addr()?.port())
}

fn spawn_sidecar(app: &AppHandle, port: u16) -> Result<Child, String> {
    let resources = app.path().resource_dir().map_err(|e| e.to_string())?;
    let data_dir = app.path().app_data_dir().map_err(|e| e.to_string())?;
    Command::new(resources.join("music-recs-api").join("music-recs-api"))
        .env("MUSIC_RECS_PORT", port.to_string())
        .env("MUSIC_RECS_DATA_DIR", data_dir)
        // Its own process group, so the API and its download child processes can be stopped together.
        .process_group(0)
        .spawn()
        .map_err(|e| format!("Could not start the music-recs API: {e}"))
}

fn wait_for_port(port: u16, sidecar: &Sidecar) -> Result<(), String> {
    let addr = SocketAddr::from(([127, 0, 0, 1], port));
    let deadline = Instant::now() + STARTUP_TIMEOUT;
    while Instant::now() < deadline {
        if let Some(child) = sidecar.0.lock().unwrap().as_mut() {
            if let Ok(Some(status)) = child.try_wait() {
                return Err(format!("The music-recs API exited during startup ({status})."));
            }
        }
        if TcpStream::connect_timeout(&addr, STARTUP_POLL).is_ok() {
            return Ok(());
        }
        thread::sleep(STARTUP_POLL);
    }
    Err("The music-recs API did not start in time.".to_string())
}

fn stop_sidecar(sidecar: &Sidecar) {
    if let Some(mut child) = sidecar.0.lock().unwrap().take() {
        // SIGTERM to the whole group lets uvicorn shut down and takes its child processes with it.
        unsafe { libc::killpg(child.id() as i32, libc::SIGTERM) };
        let _ = child.wait();
    }
}

fn show_error(window: &WebviewWindow, message: &str) {
    let literal = serde_json::to_string(message).unwrap_or_default();
    let _ = window.eval(format!("window.showError && window.showError({literal})"));
}

pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .manage(Sidecar(Mutex::new(None)))
        .setup(|app| {
            let opener_handle = app.handle().clone();
            // In dev the window loads devUrl (Vite) and the API runs separately, as with start.sh.
            let window = WebviewWindowBuilder::new(app, MAIN_WINDOW, WebviewUrl::default())
                .title("Music Recs")
                .inner_size(1280.0, 860.0)
                .min_inner_size(480.0, 600.0)
                // Links that open a new window (target="_blank", window.open) go to the system browser.
                .on_new_window(move |url, _features| {
                    let _ = opener_handle.opener().open_url(url.as_str(), None::<&str>);
                    NewWindowResponse::Deny
                })
                .build()?;

            if cfg!(debug_assertions) {
                return Ok(());
            }

            let handle = app.handle().clone();
            thread::spawn(move || {
                let sidecar = handle.state::<Sidecar>();
                let result = pick_free_port()
                    .map_err(|e| e.to_string())
                    .and_then(|port| {
                        let child = spawn_sidecar(&handle, port)?;
                        *sidecar.0.lock().unwrap() = Some(child);
                        wait_for_port(port, &sidecar).map(|_| port)
                    });
                match result {
                    Ok(port) => {
                        let url = format!("http://127.0.0.1:{port}");
                        let _ = window.navigate(url.parse().unwrap());
                    }
                    Err(message) => show_error(&window, &message),
                }
            });
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building tauri application")
        .run(|handle, event| {
            if let RunEvent::Exit = event {
                stop_sidecar(&handle.state::<Sidecar>());
            }
        });
}
