import os


def download_file(specter, url, file_path, setup_status_name, setup_status_stage):
    response = specter.requests_session().get(url, stream=True)
    with open(file_path, "wb") as f:
        total_length = float(response.headers["content-length"])
        downloaded = 0.0
        old_progress = 0
        specter.config[f"{setup_status_name}_setup"]["stage"] = setup_status_stage
        specter._save()
        for chunk in response.iter_content(chunk_size=4096):
            downloaded += len(chunk)
            f.write(chunk)
            new_progress = int((downloaded / total_length) * 10000) / 100
            if new_progress > old_progress:
                if new_progress > 100:
                    new_progress = 100
                old_progress = new_progress
                specter.config[f"{setup_status_name}_setup"][
                    "stage_progress"
                ] = new_progress
                specter._save()
