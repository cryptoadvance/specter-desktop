import os
from ..specter_error import SpecterError


def download_file(specter, url, file_path, setup_status_name, setup_status_stage):
    response = specter.requests_session().get(url, stream=True)
    with open(file_path, "wb") as f:
        total_length = float(response.headers["content-length"])
        downloaded = 0.0
        old_progress = 0
        specter.update_setup_status(setup_status_name, setup_status_stage)
        for chunk in response.iter_content(chunk_size=4096):
            if specter.setup_status["stage"] == "start":
                raise SpecterError("File download canceled")
            downloaded += len(chunk)
            f.write(chunk)
            new_progress = int((downloaded / total_length) * 10000) / 100
            if new_progress > old_progress:
                if new_progress > 100:
                    new_progress = 100
                old_progress = new_progress
                specter.update_setup_download_progress(setup_status_name, new_progress)
