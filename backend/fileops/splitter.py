import os, math
from pathlib import Path

TEMP_DIR_PATH = Path(__file__).resolve().parent.parent / "temp"
DEFAULT_CHUNK_SIZE = 512 * 1024 * 1024

def split_file(file_path: str | Path, output_dir: str | Path = TEMP_DIR_PATH, chunk_size: int = DEFAULT_CHUNK_SIZE, chunk_prefix: str = None):
    file_path = Path(file_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if chunk_prefix is None: chunk_prefix = file_path.name
    file_size = file_path.stat().st_size

    total_chunks = math.ceil(file_size / chunk_size) if file_size > 0 else 1
    padding_width = len(str(total_chunks))
    
    with open(file_path, 'rb') as f:
        chunk_index = 0
        while True:
            chunk_data = f.read(chunk_size)
            if not chunk_data:
                break
            
            chunk_name = output_dir / f"{chunk_prefix}.part_{chunk_index:0{padding_width}d}"
            with open(chunk_name, 'wb') as chunk_file:
                chunk_file.write(chunk_data)
                
            chunk_index += 1
