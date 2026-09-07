import glob, shutil
from pathlib import Path

def merge_chunks(search_pattern: str, output_path: str | Path):
    output_path = Path(output_path)
    
    chunk_files = sorted([Path(p) for p in glob.glob(search_pattern)])
    
    if not chunk_files:
        raise FileNotFoundError(f"No chunk files found matching pattern: {search_pattern}")
        
    with open(output_path, 'wb') as outfile:
        for chunk_file in chunk_files:
            with open(chunk_file, 'rb') as infile:
                shutil.copyfileobj(infile, outfile, length = 1024 * 1024)

# merge_chunks(str(TEMP_DIR_PATH / "large_video.mp4.part_*"), TEMP_DIR_PATH / "restored_video.mp4")