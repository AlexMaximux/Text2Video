import os
import sys
import subprocess
import threading
import time
import json
import signal
import shlex
from pathlib import Path
from flask import Flask, jsonify, request, send_file, Response

BASE_DIR = Path(__file__).parent.resolve()
PROJECTS_DIR = BASE_DIR / "projects"

app = Flask(__name__, static_folder="static", static_url_path="/static")
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0

@app.after_request
def add_header(response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "-1"
    return response

# Execution State Tracker
execution_state = {
    "is_running": False,
    "current_step": None,
    "project": None,
    "status": "idle",       # "idle", "running", "success", "error", "cancelled"
    "logs": [],
    "returncode": None,
    "start_time": None,
    "last_log_time": None
}

state_lock = threading.RLock()
active_process = None
active_process_lock = threading.RLock()

def append_log(line: str):
    with state_lock:
        execution_state["logs"].append(line)
        execution_state["last_log_time"] = time.time()
        if len(execution_state["logs"]) > 2000:
            execution_state["logs"] = execution_state["logs"][-2000:]

def run_cmd_sync(cmd: str) -> int:
    """Run command synchronously in worker thread with unbuffered line streaming and process group management."""
    global active_process
    
    # Ensure unbuffered execution
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"

    try:
        args = shlex.split(cmd)
    except Exception:
        args = cmd.split()

    proc = subprocess.Popen(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        cwd=str(BASE_DIR),
        env=env,
        start_new_session=True  # create new process group
    )

    with active_process_lock:
        active_process = proc

    def reader():
        try:
            for line in iter(proc.stdout.readline, ''):
                if not line:
                    break
                append_log(line)
        except Exception:
            pass
        finally:
            try:
                proc.stdout.close()
            except Exception:
                pass

    reader_thread = threading.Thread(target=reader, daemon=True)
    reader_thread.start()

    # Poll process completion
    while proc.poll() is None:
        time.sleep(0.15)

    ret = proc.returncode
    reader_thread.join(timeout=0.5)

    with active_process_lock:
        active_process = None

    return ret

def cleanup_browser2api_locks():
    """Kill any orphaned browser2api Chrome processes and remove stale SingletonLock files."""
    try:
        subprocess.Popen(
            "pkill -9 -f 'user-data-dir=.*\\.browser2api'",
            shell=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
    except Exception:
        pass
    
    try:
        base_browser_dir = Path.home() / ".browser2api" / "browser_data"
        if base_browser_dir.exists():
            for p in base_browser_dir.rglob("Singleton*"):
                try:
                    p.unlink(missing_ok=True)
                except Exception:
                    pass
    except Exception:
        pass

def run_cmd_async(cmd: str, step_name: str, proj_name: str = None):
    def worker():
        global execution_state
        cleanup_browser2api_locks()
        with state_lock:
            execution_state["is_running"] = True
            execution_state["current_step"] = step_name
            execution_state["project"] = proj_name
            execution_state["status"] = "running"
            execution_state["logs"] = [f"[🚀 START STEP: {step_name}]\n[COMMAND] {cmd}\n\n"]
            execution_state["returncode"] = None
            execution_state["start_time"] = time.time()

        ret = run_cmd_sync(cmd)
        
        with state_lock:
            if execution_state["status"] != "cancelled":
                execution_state["is_running"] = False
                execution_state["returncode"] = ret
                execution_state["status"] = "success" if ret == 0 else "error"
                if ret == 0:
                    append_log(f"\n[✓ FINISHED STEP: {step_name}] Completed successfully with code 0.\n")
                else:
                    append_log(f"\n[✗ FAILED STEP: {step_name}] Exited with code {ret}.\n")

    t = threading.Thread(target=worker, daemon=True)
    t.start()

def run_pipeline_sequence_async(steps_config: list, proj_name: str = None):
    """Run pipeline steps sequentially. Stops immediately if any step fails or is cancelled."""
    def worker():
        global execution_state
        cleanup_browser2api_locks()
        with state_lock:
            execution_state["is_running"] = True
            execution_state["project"] = proj_name
            execution_state["status"] = "running"
            execution_state["logs"] = [f"[🚀 START FULL PIPELINE: {len(steps_config)} steps scheduled]\n\n"]
            execution_state["returncode"] = None
            execution_state["start_time"] = time.time()

        for idx, (step_name, cmd) in enumerate(steps_config, 1):
            with state_lock:
                if execution_state["status"] == "cancelled":
                    append_log(f"\n[!] Pipeline cancelled by user before step '{step_name}'.\n")
                    return
                execution_state["current_step"] = f"Step {idx}/{len(steps_config)}: {step_name}"
                append_log(f"\n==================================================\n")
                append_log(f"[▶ EXECUTING STEP {idx}/{len(steps_config)}: {step_name}]\n")
                append_log(f"[COMMAND] {cmd}\n")
                append_log(f"==================================================\n")

            ret = run_cmd_sync(cmd)

            with state_lock:
                if execution_state["status"] == "cancelled":
                    append_log(f"\n[!] Pipeline execution cancelled during step '{step_name}'.\n")
                    return

            if ret != 0:
                with state_lock:
                    execution_state["is_running"] = False
                    execution_state["returncode"] = ret
                    execution_state["status"] = "error"
                    append_log(f"\n[⛔ PIPELINE HALTED] Step '{step_name}' failed with exit code {ret}.\n")
                    append_log(f"[!] Stopping subsequent pipeline steps to prevent invalid assets.\n")
                return

            append_log(f"\n[✓] Step '{step_name}' completed successfully.\n")

        with state_lock:
            execution_state["is_running"] = False
            execution_state["returncode"] = 0
            execution_state["status"] = "success"
            execution_state["current_step"] = "Pipeline Finished"
            append_log(f"\n[🎉 SUCCESS] Entire Text2Video pipeline completed successfully!\n")

    t = threading.Thread(target=worker, daemon=True)
    t.start()


@app.route("/")
def index():
    return send_file(BASE_DIR / "index.html")


@app.route("/api/projects")
def list_projects():
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    projects_list = []
    
    for item in sorted(PROJECTS_DIR.iterdir(), key=os.path.getmtime, reverse=True):
        if item.is_dir() and not item.name.startswith("."):
            has_script = (item / "senario.txt").exists()
            has_audio = (item / "Senario.mp3").exists() or (item / "voice.mp3").exists()
            has_transcript = (item / "transcript.txt").exists()
            has_prompts = (item / "image_prompts.txt").exists()
            images_dir = item / "images"
            has_images = images_dir.exists() and len(list(images_dir.glob("*"))) > 0
            has_video = (item / "final_video.mp4").exists()

            stages_done = sum([has_script, has_audio, has_transcript, has_prompts, has_images, has_video])
            progress_pct = int((stages_done / 6) * 100)

            # Get image count and thumbnail if available
            image_count = len(list(images_dir.glob("*"))) if (images_dir.exists() and images_dir.is_dir()) else 0
            thumbnail_url = None
            if image_count > 0:
                first_img = next((img for img in sorted(images_dir.glob("*")) if img.suffix.lower() in [".jpg", ".jpeg", ".png", ".webp"]), None)
                if first_img:
                    thumbnail_url = f"/media/projects/{item.name}/images/{first_img.name}"

            projects_list.append({
                "name": item.name,
                "path": str(item),
                "mtime": item.stat().st_mtime,
                "has_script": has_script,
                "has_audio": has_audio,
                "has_transcript": has_transcript,
                "has_prompts": has_prompts,
                "has_images": has_images,
                "has_video": has_video,
                "image_count": image_count,
                "thumbnail_url": thumbnail_url,
                "progress": progress_pct
            })

    # Sort so 100% completed / ready projects are first, followed by newest
    projects_list.sort(key=lambda p: (p["progress"], p["mtime"]), reverse=True)

    return jsonify({"projects": projects_list})


@app.route("/api/project/<name>")
def get_project(name):
    proj_dir = PROJECTS_DIR / name
    if not proj_dir.exists():
        return jsonify({"error": "Project not found"}), 404

    script_content = ""
    script_file = proj_dir / "senario.txt"
    if script_file.exists():
        try:
            script_content = script_file.read_text(encoding="utf-8")
        except Exception:
            pass

    transcript_content = ""
    transcript_file = proj_dir / "transcript.txt"
    if transcript_file.exists():
        try:
            transcript_content = transcript_file.read_text(encoding="utf-8")
        except Exception:
            pass

    prompts_content = ""
    prompts_file = proj_dir / "image_prompts.txt"
    if prompts_file.exists():
        try:
            prompts_content = prompts_file.read_text(encoding="utf-8")
        except Exception:
            pass

    images_list = []
    images_dir = proj_dir / "images"
    if images_dir.exists() and images_dir.is_dir():
        for img in sorted(images_dir.glob("*")):
            if img.suffix.lower() in [".jpg", ".jpeg", ".png", ".webp"]:
                images_list.append({
                    "filename": img.name,
                    "url": f"/media/projects/{name}/images/{img.name}",
                    "size": img.stat().st_size
                })

    audio_url = None
    if (proj_dir / "Senario.mp3").exists():
        audio_url = f"/media/projects/{name}/Senario.mp3"
    elif (proj_dir / "voice.mp3").exists():
        audio_url = f"/media/projects/{name}/voice.mp3"

    video_url = None
    if (proj_dir / "final_video.mp4").exists():
        video_url = f"/media/projects/{name}/final_video.mp4"

    return jsonify({
        "name": name,
        "script": script_content,
        "transcript": transcript_content,
        "prompts": prompts_content,
        "images": images_list,
        "audio_url": audio_url,
        "video_url": video_url,
        "has_script": (proj_dir / "senario.txt").exists(),
        "has_audio": audio_url is not None,
        "has_transcript": (proj_dir / "transcript.txt").exists(),
        "has_prompts": (proj_dir / "image_prompts.txt").exists(),
        "has_images": len(images_list) > 0,
        "has_video": video_url is not None
    })


@app.route("/api/save-script", methods=["POST"])
def save_script():
    data = request.json or {}
    proj_name = data.get("project")
    script_text = data.get("script", "")
    if not proj_name:
        return jsonify({"error": "Missing project name"}), 400

    proj_dir = PROJECTS_DIR / proj_name
    proj_dir.mkdir(parents=True, exist_ok=True)
    (proj_dir / "senario.txt").write_text(script_text, encoding="utf-8")
    return jsonify({"success": True, "message": "Script saved successfully"})


@app.route("/api/save-prompts", methods=["POST"])
def save_prompts():
    data = request.json or {}
    proj_name = data.get("project")
    prompts_text = data.get("prompts", "")
    if not proj_name:
        return jsonify({"error": "Missing project name"}), 400

    proj_dir = PROJECTS_DIR / proj_name
    proj_dir.mkdir(parents=True, exist_ok=True)
    (proj_dir / "image_prompts.txt").write_text(prompts_text, encoding="utf-8")
    return jsonify({"success": True, "message": "Prompts saved successfully"})


@app.route("/api/create-project", methods=["POST"])
def create_project():
    data = request.json or {}
    name = data.get("name", "").strip()
    if not name:
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        name = f"Video_{timestamp}"

    # Sanitize project name
    safe_name = "".join([c if c.isalnum() or c in ("-", "_") else "_" for c in name]).strip("_")
    if not safe_name:
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        safe_name = f"Video_{timestamp}"

    proj_dir = PROJECTS_DIR / safe_name
    proj_dir.mkdir(parents=True, exist_ok=True)
    return jsonify({"success": True, "project": safe_name, "message": f"Created project '{safe_name}'"})


@app.route("/api/cancel-step", methods=["POST"])
def cancel_step():
    """Immediately terminates any currently running process group, cleans browser locks, and resets execution state."""
    global active_process, execution_state
    
    with active_process_lock:
        if active_process is not None:
            try:
                # Terminate the whole process group
                os.killpg(os.getpgid(active_process.pid), signal.SIGTERM)
                time.sleep(0.3)
                if active_process.poll() is None:
                    os.killpg(os.getpgid(active_process.pid), signal.SIGKILL)
            except Exception as e:
                append_log(f"[!] Error killing process group: {e}\n")
            active_process = None

    cleanup_browser2api_locks()

    with state_lock:
        execution_state["is_running"] = False
        execution_state["status"] = "cancelled"
        execution_state["returncode"] = -1
        append_log("\n[⛔ PROCESS CANCELLED] User aborted execution. System is back in Idle state.\n")

    return jsonify({"success": True, "message": "Execution cancelled successfully."})


@app.route("/api/restart-server", methods=["POST"])
def restart_server():
    """Gracefully restarts the Flask backend server."""
    global active_process
    with active_process_lock:
        if active_process is not None:
            try:
                os.killpg(os.getpgid(active_process.pid), signal.SIGKILL)
            except Exception:
                pass

    def deferred_restart():
        time.sleep(0.5)
        print("[!] Restarting Text2Video Server via API request...")
        os.execv(sys.executable, [sys.executable] + sys.argv)

    threading.Thread(target=deferred_restart, daemon=True).start()
    return jsonify({"success": True, "message": "Server is restarting..."})


def build_step_command(step: str, data: dict) -> str:
    data = data or {}
    profile = str(data.get("profile") or "Profile 1").strip()
    voice = str(data.get("voice") or "2styzLg7OSeuhPP6uQ26").strip()
    proj_name = str(data.get("project") or "").strip()

    if not proj_name:
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        proj_name = f"Video_{timestamp}"

    # Ensure project folder exists
    proj_dir = PROJECTS_DIR / proj_name
    proj_dir.mkdir(parents=True, exist_ok=True)

    proj_flag = f'--project "{proj_name}"'

    if step == "script":
        topic = str(data.get("topic") or "").strip()
        auto_followup = "--auto-followup" if data.get("auto_followup", True) else ""
        if topic:
            return f'python3 -u claude_prompt.py --profile "{profile}" {auto_followup} --topic "{topic}" {proj_flag}'
        else:
            return f'python3 -u claude_prompt.py --profile "{profile}" {auto_followup} {proj_flag}'

    elif step == "voice":
        input_file = data.get("input")
        output_file = data.get("output")
        input_flag = f'--input "{input_file}"' if input_file else ""
        output_flag = f'--output "{output_file}"' if output_file else ""

        use_api = data.get("use_elevenlabs_api") or data.get("use_api") or (data.get("voice_mode") == "api")
        api_key = data.get("elevenlabs_api_key") or data.get("api_key")
        model = data.get("voice_model") or data.get("model") or "eleven_multilingual_v2"
        stability = data.get("stability")
        similarity = data.get("similarity_boost")

        if use_api or api_key:
            api_flag = "--use-api"
            key_flag = f'--api-key "{api_key}"' if api_key else ""
            model_flag = f'--model "{model}"'
            stab_flag = f'--stability {stability}' if stability is not None else ""
            sim_flag = f'--similarity-boost {similarity}' if similarity is not None else ""
            return f'python3 -u elevenlabs_prompt.py {api_flag} {key_flag} {model_flag} {stab_flag} {sim_flag} --voice "{voice}" {input_flag} {output_flag} {proj_flag}'
        else:
            return f'python3 -u elevenlabs_prompt.py --profile "{profile}" --voice "{voice}" {input_flag} {output_flag} {proj_flag}'

    elif step == "transcribe":
        model = str(data.get("whisper_model") or data.get("model") or "base").strip()
        if model not in ["tiny", "base", "small", "medium", "large", "turbo"]:
            model = "base"
        audio = str(data.get("audio") or "").strip()
        out_trans = str(data.get("output_transcript") or "").strip()
        out_words = str(data.get("output_words") or "").strip()

        audio_flag = f'--audio "{audio}"' if audio else ""
        model_flag = f'--model "{model}"'
        trans_flag = f'--output-transcript "{out_trans}"' if out_trans else ""
        words_flag = f'--output-words "{out_words}"' if out_words else ""

        return f'python3 -u transcribe_audio.py {model_flag} {audio_flag} {trans_flag} {words_flag} {proj_flag}'

    elif step == "prompts":
        return f'python3 -u generate_image_prompts.py --profile "{profile}" {proj_flag}'

    elif step == "images":
        ref = str(data.get("reference") or "milo.jpeg").strip()
        model = str(data.get("image_model") or data.get("target_model") or data.get("model") or "nano-banana-2").strip()
        if model not in ["nano-banana-2", "nano-banana", "imagen-3", "imagen-3-fast"]:
            model = "nano-banana-2"
        delay = str(data.get("delay") or "8.0").strip()
        prompts_file = str(data.get("prompts_file") or "").strip()
        prompts_flag = f'--prompts "{prompts_file}"' if prompts_file else ""
        return f'python3 -u batch_generate_millo.py --profile "{profile}" --reference "{ref}" --model "{model}" --delay {delay} {prompts_flag} {proj_flag}'

    elif step == "video":
        add_captions = data.get("add_captions", True)
        font_name = str(data.get("font_name") or "Montserrat").strip()
        font_size = data.get("font_size")
        text_color = str(data.get("text_color") or "#FFFFFF").strip()
        highlight_color = str(data.get("highlight_color") or "#FFD60A").strip()
        outline_color = str(data.get("outline_color") or "#000000").strip()
        position = str(data.get("position") or "bottom").strip()

        captions_flag = "--add-captions" if add_captions else ""
        font_size_flag = f"--font-size {font_size}" if font_size else ""
        return (
            f'python3 -u make_final_video.py {proj_flag} {captions_flag} '
            f'--font-name "{font_name}" {font_size_flag} --text-color "{text_color}" '
            f'--highlight-color "{highlight_color}" --outline-color "{outline_color}" --position {position}'
        )

    raise ValueError(f"Unknown step name: {step}")


@app.route("/api/run-step", methods=["POST"])
def run_step():
    global execution_state
    with state_lock:
        if execution_state["is_running"]:
            return jsonify({"error": "Another process is currently running", "state": execution_state}), 400

    data = request.json or {}
    step = data.get("step")
    try:
        cmd = build_step_command(step, data)
    except ValueError as err:
        return jsonify({"error": str(err)}), 400

    run_cmd_async(cmd, step_name=step, proj_name=data.get("project"))
    return jsonify({"success": True, "message": f"Started step {step}", "cmd": cmd})


@app.route("/api/run-pipeline", methods=["POST"])
def run_pipeline():
    global execution_state
    with state_lock:
        if execution_state["is_running"]:
            return jsonify({"error": "Another process is currently running", "state": execution_state}), 400

    data = request.json or {}
    skip_images = data.get("skip_images", False)

    steps_config = [
        ("Script Generation", build_step_command("script", data)),
        ("Voiceover Synthesis", build_step_command("voice", data)),
        ("Whisper Transcription", build_step_command("transcribe", data)),
        ("Image Prompt Engineering", build_step_command("prompts", data)),
    ]

    if not skip_images:
        steps_config.append(("Batch Image Generation", build_step_command("images", data)))

    steps_config.append(("Final Video Assembly", build_step_command("video", data)))

    run_pipeline_sequence_async(steps_config, proj_name=data.get("project"))
    return jsonify({"success": True, "message": f"Started sequential pipeline with {len(steps_config)} steps"})


@app.route("/api/status")
def get_status():
    with state_lock:
        return jsonify({
            "is_running": execution_state["is_running"],
            "current_step": execution_state["current_step"],
            "project": execution_state["project"],
            "status": execution_state["status"],
            "logs": execution_state["logs"][-300:],
            "returncode": execution_state["returncode"],
            "start_time": execution_state["start_time"]
        })


@app.route("/media/<path:filename>")
def serve_media(filename):
    file_path = BASE_DIR / filename
    if not file_path.exists():
        return jsonify({"error": f"File not found: {filename}"}), 404
@app.route("/api/elevenlabs/voices", methods=["POST"])
def get_elevenlabs_voices():
    """Fetch available custom and library voices for an ElevenLabs API key."""
    import urllib.request
    import json
    data = request.json or {}
    api_key = data.get("api_key") or os.getenv("ELEVENLABS_API_KEY")
    if not api_key:
        return jsonify({"success": False, "error": "No ElevenLabs API key provided"}), 400

    try:
        req = urllib.request.Request(
            "https://api.elevenlabs.io/v1/voices",
            headers={"xi-api-key": api_key, "User-Agent": "Text2Video-Studio/1.0"}
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            voices = body.get("voices", [])
            formatted = [
                {
                    "voice_id": v.get("voice_id"),
                    "name": v.get("name"),
                    "category": v.get("category", "custom"),
                    "preview_url": v.get("preview_url")
                }
                for v in voices
            ]
            return jsonify({"success": True, "voices": formatted})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/history-topics", methods=["GET"])
def get_history_topics():
    """Return all previously generated topic titles from history_topics.txt."""
    history_file = BASE_DIR / "history_topics.txt"
    topics = []
    if history_file.exists():
        for line in history_file.read_text(encoding="utf-8").splitlines():
            line_clean = line.strip()
            if line_clean and line_clean not in topics:
                topics.append(line_clean)
    return jsonify({"success": True, "topics": topics})


if __name__ == "__main__":
    if "--check" in sys.argv:
        print("Flask app syntax check passed successfully.")
        sys.exit(0)
    print("Starting Text2Video Server on http://127.0.0.1:5000")
    app.run(host="0.0.0.0", port=5000, debug=True, threaded=True)
